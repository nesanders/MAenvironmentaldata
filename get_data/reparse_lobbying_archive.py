"""Reparse the archived MA lobbying raw HTML into the full set of output CSVs.

The scraper (get_MA_lobbying.py --archive-raw) saves every Summary and
CompleteDisclosure page to GCS as batched tarballs (raw_html/*.tar.gz). This
driver downloads those batches one at a time (to keep local disk bounded),
extracts every field with the pure parsers in get_MA_lobbying, and writes the
authoritative CSVs. It exists so new fields can be derived from the corpus
without ever re-scraping the portal, and to (re)build the full history after a
scrape that only extracted some fields inline.

The links CSV (MA_lobbying_summary_links.csv) is the manifest: every summary_url
and disc_url maps to a sha1(url).html file in the archive, plus the entity_name
and year for that page.

Outputs (../docs/data/):
  MA_lobbying_employers.csv             comp per (entity, client, year)
  MA_lobbying_bills.csv                 bills lobbied
  MA_lobbying_campaign_contributions.csv lobbyist -> recipient contributions
  MA_lobbying_lobbyists.csv             lobbyist <-> entity employment + salary
  MA_lobbying_expenses.csv              itemized operating/MET/additional expenses
  MA_lobbying_client_purposes.csv       per-client annual amount + purpose text

Run from get_data/:
    python reparse_lobbying_archive.py [--limit-batches N] [--no-upload]
"""

import argparse
import csv
import hashlib
import os
import subprocess
import tarfile
import tempfile
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

import get_MA_lobbying as g

DATA_DIR = Path('../docs/data')
GCS_BUCKET = 'gs://openamend-data'
LINKS_PATH = DATA_DIR / 'MA_lobbying_summary_links.csv'


def _sha1(url: str) -> str:
    return hashlib.sha1(url.encode('utf-8')).hexdigest()


def _build_manifest(links: pd.DataFrame) -> dict:
    """sha1(url).html filename -> (entity_name, year, page_type)."""
    manifest = {}
    for _, row in links.iterrows():
        entity, year = row.get('entity_name'), row.get('year')
        su = row.get('summary_url')
        du = row.get('disc_url')
        if isinstance(su, str) and su:
            manifest[_sha1(su) + '.html'] = (entity, year, 'summary')
        if isinstance(du, str) and du:
            manifest[_sha1(du) + '.html'] = (entity, year, 'disclosure')
    return manifest


def _list_batches() -> list[str]:
    out = subprocess.run(
        ['gsutil', 'ls', f'{GCS_BUCKET}/raw_html/'],
        capture_output=True, text=True,
    ).stdout
    return sorted(line.strip() for line in out.splitlines() if line.strip().endswith('.tar.gz'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit-batches', type=int, default=None,
                    help='Process only the first N batches (for testing)')
    ap.add_argument('--no-upload', action='store_true', help='Skip GCS upload of CSVs')
    args = ap.parse_args()

    links = pd.read_csv(LINKS_PATH)
    manifest = _build_manifest(links)
    print(f'Manifest: {len(manifest):,} archived pages expected '
          f'(from {len(links):,} links rows)')

    batches = _list_batches()
    if args.limit_batches:
        batches = batches[:args.limit_batches]
    print(f'Processing {len(batches)} archive batch(es)')

    employers, bills, campaigns, edges, expenses, purposes = [], [], [], [], [], []
    seen_disc, seen_summ = set(), set()  # avoid double-processing duplicate pages
    n_pages = n_unmatched = 0

    for i, batch_uri in enumerate(batches, 1):
        with tempfile.TemporaryDirectory(dir='.') as tmp:
            tmp = Path(tmp)
            local_tar = tmp / 'batch.tar.gz'
            if os.system(f'gsutil -q cp {batch_uri} {local_tar}') != 0:
                print(f'  WARNING: failed to download {batch_uri}; skipping')
                continue
            with tarfile.open(local_tar) as tf:
                tf.extractall(tmp)
            local_tar.unlink()
            html_files = list(tmp.rglob('*.html'))
            for hf in html_files:
                meta = manifest.get(hf.name)
                if meta is None:
                    n_unmatched += 1
                    continue
                entity, year, ptype = meta
                year = int(year) if pd.notna(year) else None
                soup = BeautifulSoup(hf.read_text(encoding='utf-8'), 'html.parser')
                n_pages += 1

                if ptype == 'disclosure':
                    if hf.name in seen_disc:
                        continue
                    seen_disc.add(hf.name)
                    detail = g.parse_disclosure_detail(soup, year)
                    for c in detail['compensation']:
                        employers.append({'entity_name': entity, 'client_name': c['client_name'],
                                          'year': year, 'compensation': c['amount']})
                    for b in detail['bills']:
                        bills.append({'entity_name': entity, 'year': year, **b})
                    for cc in g.parse_campaign_contributions(soup):
                        campaigns.append({'entity_name': entity, 'year': year, **cc})
                    for ex in g.parse_expenses(soup):
                        expenses.append({'entity_name': entity, 'year': year, **ex})

                elif ptype == 'summary':
                    if hf.name in seen_summ:
                        continue
                    seen_summ.add(hf.name)
                    meta_s = g.parse_summary(soup)
                    reg_type = meta_s.get('reg_type')
                    for e in g.parse_employment_edges(soup):
                        # Fill the registrant side: entity pages list lobbyists,
                        # individual pages list employing entities.
                        if reg_type == 'Lobbyist Entity':
                            e['entity_name'] = entity
                        else:
                            e['lobbyist_name'] = entity
                        edges.append({'year': year, **e})
                    for cp in g.parse_client_purposes(soup):
                        purposes.append({'entity_name': entity, 'year': year, **cp})

        print(f'  [{i}/{len(batches)}] {n_pages:,} pages parsed '
              f'({len(employers):,} comp, {len(bills):,} bills, {len(campaigns):,} contrib, '
              f'{len(edges):,} edges, {len(expenses):,} exp)')

    if n_unmatched:
        print(f'NOTE: {n_unmatched:,} archived pages had no manifest match '
              '(stale links or search pages) — skipped')

    # ── Write CSVs (dedup where a natural key exists) ───────────────────────────
    def _write(rows, name, dedup=None, quote_all=False):
        df = pd.DataFrame(rows)
        if dedup and not df.empty:
            df = df.drop_duplicates(subset=dedup)
        df = df.reset_index(drop=True)
        path = DATA_DIR / name
        quoting = csv.QUOTE_NONNUMERIC if quote_all else csv.QUOTE_MINIMAL
        df.to_csv(path, quoting=quoting)
        print(f'  wrote {name}: {len(df):,} rows')
        return path

    print('\nWriting CSVs...')
    paths = [
        _write(employers, 'MA_lobbying_employers.csv', dedup=['entity_name', 'client_name', 'year']),
        _write(bills, 'MA_lobbying_bills.csv',
               dedup=['entity_name', 'client_name', 'bill_number', 'general_court'], quote_all=True),
        _write(campaigns, 'MA_lobbying_campaign_contributions.csv',
               dedup=['entity_name', 'year', 'lobbyist_name', 'recipient_name', 'date', 'amount']),
        _write(edges, 'MA_lobbying_lobbyists.csv', dedup=['lobbyist_name', 'entity_name', 'year']),
        _write(expenses, 'MA_lobbying_expenses.csv',
               dedup=['entity_name', 'year', 'expense_type', 'date', 'payee', 'amount']),
        _write(purposes, 'MA_lobbying_client_purposes.csv',
               dedup=['entity_name', 'client_name', 'year'], quote_all=True),
    ]

    if not args.no_upload:
        print('\nUploading CSVs to GCS...')
        for p in paths:
            if os.system(f'gsutil -q cp {p} {GCS_BUCKET}/{p.name}') == 0:
                print(f'  uploaded {p.name}')
            else:
                print(f'  WARNING: failed to upload {p.name}')


if __name__ == '__main__':
    main()
