"""Scrape MA Secretary of State lobbying disclosure portal.

Portal: https://www.sec.state.ma.us/LobbyistPublicSearch/

Page flow (all fetchable with plain requests + iPad User-Agent):
  1. Search POST → grdvSearchResultByTypeAndCategory table
       One row per lobbyist/entity; each row has a Summary.aspx link.
  2. Summary.aspx → registrant name/year/type + CompleteDisclosure links (2 per year, one per semi-annual period)
  3. CompleteDisclosure.aspx → per-client compensation + per-client bill activity tables

Data model: lobbyist entities report which clients they were paid by, and for
each client, which bills they lobbied (with chamber, bill number, title, position).

Incremental strategy (CSV-based, no file cache):
  - Summary links for past years already in MA_lobbying_summary_links.csv are skipped.
  - Current and prior year summary links are always re-fetched (new filers arrive
    semi-annually); only NEW summary links (not yet in the disclosure links CSV)
    get their detail pages fetched.
  - If no new links are found, exits early with no file writes.

Three normalized output CSVs:
  MA_lobbying_employers.csv   — one row per (entity_name, client_name, year):
                                entity type, compensation paid to entity
  MA_lobbying_lobbyists.csv   — one row per (lobbyist_name, entity_name, year):
                                individual lobbyists employed by entities
  MA_lobbying_bills.csv       — one row per (entity_name, client_name, bill_id, year):
                                bill number, chamber, title, position, amount

Run from the get_data/ directory:
    conda run -n amend_python python get_MA_lobbying.py [--year YEAR]

Outputs:
  ../docs/data/MA_lobbying_summary_links.csv  — persistent link registry
  ../docs/data/MA_lobbying_employers.csv
  ../docs/data/MA_lobbying_lobbyists.csv
  ../docs/data/MA_lobbying_bills.csv
  ../docs/data/ts_update_MA_lobbying.yml
"""

import argparse
import csv
import datetime
import hashlib
import os
import re
import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

# ─── Configuration ─────────────────────────────────────────────────────────────

BASE_URL = 'https://www.sec.state.ma.us/LobbyistPublicSearch/'
SEARCH_URL = BASE_URL + 'Default.aspx'
DATA_DIR = Path('../docs/data')

# GCS state files — the full CSVs are gitignored (too large); CI pulls them from
# GCS at startup so every run is incremental rather than doing a full historical fetch.
GCS_BUCKET        = 'gs://openamend-data'
GCS_STATE_FILES   = [
    'MA_lobbying_summary_links.csv',  # incremental state — must be synced
    'MA_lobbying_bills.csv',           # uploaded by assemble_db.py but pulled here
    'MA_lobbying_employers.csv',       # same
]

FIRST_YEAR = 2005
REQUEST_DELAY = 0.3  # seconds between requests (lowered from 1.0 — safe for this low-volume server)

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (iPad; CPU OS 12_2 like Mac OS X) '
        'AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148'
    )
}

# General Court 183 started in January 2003; each covers two calendar years.
# GC184 = 2005-2006, GC194 = 2025-2026, etc.
FIRST_GENERAL_COURT = 183
FIRST_GC_START_YEAR = 2003


def _year_to_general_court(year: int) -> int:
    return FIRST_GENERAL_COURT + ((year - FIRST_GC_START_YEAR) // 2)


# ─── Raw HTML archival (streamed in batches to keep local disk bounded) ────────
# When enabled (--archive-raw), every fetched Summary/CompleteDisclosure page is
# saved to MA_lobbying_raw_html/{sha1(url)}.html.  To avoid accumulating ~2 GB
# locally, pages are flushed in batches: once the local buffer exceeds
# RAW_BATCH_MAX_BYTES it is tarred, uploaded to GCS Archive as a numbered batch,
# and deleted locally.  Local usage therefore stays under ~RAW_BATCH_MAX_BYTES.
# The links CSV stores every summary_url/disc_url and doubles as the archive
# manifest: to reparse offline, download all raw_html/*.tar.gz, extract, then
# look up sha1(url).html.  Lets us extract new fields later without re-scraping.

RAW_HTML_DIR = Path('MA_lobbying_raw_html')
ARCHIVE_RAW = False                  # set by --archive-raw in main()
RAW_BATCH_MAX_BYTES = 150 * 1024 * 1024  # flush+upload batch at ~150 MB local
_raw_buffer_bytes = 0
_raw_batch_seq = 0
_raw_run_tag = datetime.datetime.now().strftime('%Y%m%dT%H%M%S')


def _raw_path(url: str) -> Path:
    return RAW_HTML_DIR / (hashlib.sha1(url.encode('utf-8')).hexdigest() + '.html')


def _flush_raw_batch() -> None:
    """Tar the local raw-HTML buffer, upload to GCS Archive, delete locally."""
    global _raw_buffer_bytes, _raw_batch_seq
    files = list(RAW_HTML_DIR.glob('*.html')) if RAW_HTML_DIR.exists() else []
    if not files:
        return
    _raw_batch_seq += 1
    tarball = f'raw_html_batch_{_raw_run_tag}_{_raw_batch_seq:04d}.tar.gz'
    if os.system(f'tar czf {tarball} -C {RAW_HTML_DIR.parent} {RAW_HTML_DIR.name}') == 0:
        dest = f'{GCS_BUCKET}/raw_html/{tarball}'
        if os.system(f'gsutil -q cp -s archive {tarball} {dest}') == 0:
            sz = Path(tarball).stat().st_size / 1e6
            print(f'    [raw archive] uploaded {tarball} ({len(files):,} pages, {sz:.0f} MB) -> Archive')
            for f in files:
                f.unlink()
        else:
            print(f'    WARNING: failed to upload {tarball}; keeping local pages')
    else:
        print('    WARNING: failed to tar raw HTML batch')
    if Path(tarball).exists():
        Path(tarball).unlink()
    _raw_buffer_bytes = 0


def _save_raw(url: str, html: str) -> None:
    global _raw_buffer_bytes
    if not ARCHIVE_RAW:
        return
    p = _raw_path(url)
    if p.exists():
        return  # already buffered this URL (pre-flush)
    RAW_HTML_DIR.mkdir(exist_ok=True)
    data = html.encode('utf-8')
    p.write_bytes(data)
    _raw_buffer_bytes += len(data)
    if _raw_buffer_bytes >= RAW_BATCH_MAX_BYTES:
        _flush_raw_batch()


# ─── HTTP ──────────────────────────────────────────────────────────────────────

def _make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def _get(session, url, retries=5, **kwargs) -> BeautifulSoup:
    for attempt in range(retries):
        time.sleep(REQUEST_DELAY * (2 ** attempt) if attempt else REQUEST_DELAY)
        try:
            r = session.get(url, timeout=60, **kwargs)
            r.raise_for_status()
            # Archive only content pages (Summary/CompleteDisclosure), not the
            # regenerable search page (which shares one URL across all years).
            if 'Summary.aspx' in url or 'CompleteDisclosure' in url:
                _save_raw(url, r.text)
            return BeautifulSoup(r.text, 'html.parser')
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            print(f'  GET timeout/connection error (attempt {attempt+1}/{retries}): {e}')
            if attempt == retries - 1:
                raise


def _post(session, url, data, timeout=180, retries=5) -> BeautifulSoup:
    for attempt in range(retries):
        time.sleep(REQUEST_DELAY * (2 ** attempt) if attempt else REQUEST_DELAY)
        try:
            r = session.post(url, data=data, timeout=timeout)
            r.raise_for_status()
            return BeautifulSoup(r.text, 'html.parser')
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            print(f'  POST timeout/connection error (attempt {attempt+1}/{retries}): {e}')
            if attempt == retries - 1:
                raise


# ─── Search page ───────────────────────────────────────────────────────────────

def _viewstate(soup: BeautifulSoup) -> dict:
    fields = {}
    for inp in soup.find_all('input', type='hidden'):
        fields[inp['name']] = inp.get('value', '')
    return fields


def fetch_summary_links(session, year: int) -> list[str]:
    """Return all Summary.aspx URLs for a given year (lobbyists + entities)."""
    soup = _get(session, SEARCH_URL)
    vs = _viewstate(soup)
    post_data = {
        **vs,
        '__EVENTTARGET': '',
        '__EVENTARGUMENT': '',
        'ctl00$ContentPlaceHolder1$Search': 'rdbSearchByType',
        'ctl00$ContentPlaceHolder1$ucSearchCriteriaByType$ddlYear': str(year),
        'ctl00$ContentPlaceHolder1$ucSearchCriteriaByType$txtN_ame': '',
        'ctl00$ContentPlaceHolder1$ucSearchCriteriaByType$lddSearchType$DropDown': '3',
        'ctl00$ContentPlaceHolder1$ucSearchCriteriaByType$drpType': 'L',  # Lobbyist or Lobbying Entity
        'ctl00$ContentPlaceHolder1$drpPageSize': '20000',
        'ctl00$ContentPlaceHolder1$btnSearch': 'Search',
    }
    soup2 = _post(session, SEARCH_URL, post_data)
    table = soup2.find(
        'table',
        id=lambda x: x and 'grdvSearchResultByTypeAndCategory' in x
    )
    if not table:
        return []
    return [
        BASE_URL + a['href']
        for a in table.find_all('a', href=True)
        if 'Summary.aspx' in a['href']
    ]


# ─── Summary page ──────────────────────────────────────────────────────────────

def fetch_disclosure_links(session, summary_url: str) -> dict:
    """Fetch a Summary page and return registrant metadata + disclosure URLs."""
    return parse_summary(_get(session, summary_url))


def parse_summary(soup: BeautifulSoup) -> dict:
    """Parse a Summary page (pure; no I/O — also used for offline archive reparse).

    Returns dict with keys: entity_name, year, reg_type, disclosure_urls (list).
    """
    def _text(sid):
        tag = soup.find(id=sid)
        return tag.get_text(strip=True) if tag else ''

    entity_name = _text('ContentPlaceHolder1_lblRegistrantName')
    year_text = _text('ContentPlaceHolder1_lblYear')
    reg_type = _text('ContentPlaceHolder1_lblRegType')
    try:
        year = int(year_text)
    except ValueError:
        year = None

    disc_urls = [
        BASE_URL + a['href'] if not a['href'].startswith('http') else a['href']
        for a in soup.find_all('a', href=True)
        if 'CompleteDisclosure' in a['href']
    ]
    return {
        'entity_name': entity_name,
        'year': year,
        'reg_type': reg_type,
        'disclosure_urls': disc_urls,
    }


# ─── CompleteDisclosure page ───────────────────────────────────────────────────

def _parse_amount(text: str) -> float | None:
    text = text.replace('$', '').replace(',', '').strip()
    try:
        return float(text)
    except ValueError:
        return None


def fetch_disclosure_detail(session, disc_url: str, year: int) -> dict:
    """Fetch + parse a CompleteDisclosure page."""
    return parse_disclosure_detail(_get(session, disc_url), year)


def parse_disclosure_detail(soup: BeautifulSoup, year: int) -> dict:
    """Parse a CompleteDisclosure page (pure; no I/O — also used for offline reparse).

    Four HTML format eras exist; per-client compensation lives in a different
    place in each. Detection is by table id (verified across 2007/2011/2016/2024):

    Modern (2019+): `grdvClientPaidToEntity` holds per-client compensation;
      bills in `grdvActivitiesNew{year}_{n}` (one table per client).

    Hybrid (2014–2018): NO grdvClientPaidToEntity. Bills in `grdvActivitiesNew_{n}`
      (no year suffix). Per-client compensation is in id-less Panel1 divs
      ("Total amount paid by client…: $X") indexed by the same {n} as the
      client-name span (`lblClientName_{n}`). A client either reports a Panel1
      total OR reports at activity level (amount column of its bill table) —
      so per-client comp = panel_total + activity_sum (one is always 0).
      Missing this path silently dropped ~99% of 2014–2018 compensation.

    Legacy (2009–2013): single `grdvActivities` table whose "Compensation
      received" column carries a PER-CLIENT total repeated on every bill row
      for that client (verified: identical value across a client's rows) —
      so dedupe distinct (client, amount) before summing, never sum raw rows.

    Legacy (2005–2008): `grdvActivities` has only 4 columns (Date | Bill+Title |
      Lobbyist | Client) with NO compensation column; fall back to the entity
      total in `grdvSalaryPaid` under the placeholder client `_total_salary_`.

    Returns dict with:
      compensation: list of {client_name, amount}
      bills:        list of {client_name, chamber, bill_number, bill_title,
                              position, amount, general_court}
    """
    compensation = []
    bills = []
    gc = _year_to_general_court(year)

    # ── Modern / Hybrid: per-client bill activity tables ───────────────────────
    # ID patterns: 2014–2018 → grdvActivitiesNew_{n} (no year);
    #              2019+      → grdvActivitiesNew{year}_{n}.
    comp_table = soup.find(
        'table',
        id=lambda x: x and 'grdvClientPaidToEntity' in (x or '')
    )
    if comp_table:
        # Modern: authoritative per-client compensation table.
        for row in comp_table.find_all('tr', class_=lambda c: c and 'Grid' in c and 'Header' not in c):
            cells = [td.get_text(strip=True) for td in row.find_all('td')]
            if len(cells) >= 2:
                compensation.append({
                    'client_name': cells[0],
                    'amount': _parse_amount(cells[1]),
                })

    activity_by_client = {}  # client_name -> summed activity-level amount (hybrid)
    for act_table in soup.find_all(
        'table',
        id=lambda x: x and re.search(r'grdvActivitiesNew(\d{4})?_\d+', x or '')
    ):
        client_span = act_table.find_previous(
            'span',
            id=lambda x: x and 'lblClientName' in (x or '')
        )
        client_name = client_span.get_text(strip=True) if client_span else ''

        for row in act_table.find_all(
            'tr',
            class_=lambda c: c and 'Grid' in c and 'Header' not in c
        ):
            cells = [td.get_text(strip=True) for td in row.find_all('td')]
            # Columns: House/Senate, Bill Number, Bill title, Position, Amount, Direct business
            if len(cells) >= 4:
                amt = _parse_amount(cells[4]) if len(cells) > 4 else None
                bills.append({
                    'client_name': client_name,
                    'chamber': cells[0],
                    'bill_number': cells[1],
                    'bill_title': cells[2] if len(cells) > 2 else '',
                    'position': cells[3] if len(cells) > 3 else '',
                    'amount': amt,
                    'general_court': gc,
                })
                if amt:
                    activity_by_client[client_name] = activity_by_client.get(client_name, 0.0) + amt

    # Hybrid (2014–2018): no modern comp table — reconstruct per-client comp from
    # the Panel1 "Total amount paid by client" divs, indexed by client-name span.
    if not comp_table and bills:
        client_by_idx = {
            sp.get('id').split('_')[-1]: sp.get_text(strip=True)
            for sp in soup.find_all('span', id=lambda x: x and 'lblClientName_' in (x or ''))
        }
        panel_by_client = {}
        for div in soup.find_all('div', id=lambda x: x and 'Panel1_' in (x or '')):
            idx = div.get('id').split('_')[-1]
            client_name = client_by_idx.get(idx)
            if not client_name:
                continue
            m = re.search(r'\$([\d,]+\.\d\d)', div.get_text(' ', strip=True))
            panel_by_client[client_name] = float(m.group(1).replace(',', '')) if m else 0.0
        # A client reports EITHER a Panel1 total OR activity-level amounts; summing
        # is safe because the unused source is 0.
        for client_name in set(panel_by_client) | set(activity_by_client):
            amt = panel_by_client.get(client_name, 0.0) + activity_by_client.get(client_name, 0.0)
            if amt:
                compensation.append({'client_name': client_name, 'amount': amt})

    if comp_table or bills:
        return {'compensation': compensation, 'bills': bills}

    # ── Legacy format (2005–2013): single grdvActivities table ─────────────────
    # Three known column layouts; registrant type (individual vs. entity), not
    # year, determines whether a "Lobbyist name" column is present:
    #   2005–2009 4-col:        Date | Bill+Title | Lobbyist | Client        (no comp)
    #   2010+ individual 5-col: Activity | Position | DirectBiz | Client | Compensation
    #   2010+ entity 6-col:     Activity | Lobbyist | Position | DirectBiz | Client | Compensation
    # The "Compensation received" column (2009–2013) is a PER-CLIENT total
    # repeated on every bill row for that client, so we dedupe distinct
    # (client, amount) pairs before summing — never sum the raw rows.
    act_table = soup.find(
        'table',
        id=lambda x: x and x.endswith('grdvActivities')
    )
    comp_col = None
    legacy_comp_pairs = set()  # distinct (client_name, amount) to avoid row multiplication
    if act_table:
        all_rows = act_table.find_all('tr')
        header_cells = [
            th.get_text(strip=True) for th in (
                all_rows[0].find_all(['th', 'td']) if all_rows else []
            )
        ]
        if header_cells and 'Activity' in header_cells[0]:
            # 6-col entity layout has "Lobbyist name" as the second header cell
            if len(header_cells) >= 2 and 'Lobbyist' in header_cells[1]:
                bill_col, position_col, client_col = 0, 2, 4
            else:
                bill_col, position_col, client_col = 0, 1, 3
        else:
            bill_col, position_col, client_col = 1, None, 3
        # "Compensation received" is the last column when present (2009–2013).
        if any('Compensation' in h for h in header_cells):
            comp_col = len(header_cells) - 1

        chamber_map = {'H': 'House Bill', 'S': 'Senate Bill',
                       'HD': 'House Docket', 'SD': 'Senate Docket'}
        for row in all_rows[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all('td')]
            if len(cells) <= max(bill_col, client_col):
                continue
            bill_cell = cells[bill_col]
            client_name = cells[client_col]
            position = cells[position_col] if position_col is not None else ''
            amt = (_parse_amount(cells[comp_col])
                   if comp_col is not None and len(cells) > comp_col else None)
            # Skip summary rows: legacy individual disclosures append a
            # "Total amount" row that repeats the per-client total — it is not a
            # real client and must not become a compensation pair or a fake row.
            if amt is not None and client_name not in ('Total amount', 'Total', ''):
                legacy_comp_pairs.add((client_name, amt))
            if not bill_cell or bill_cell in (
                'Activity or Bill No and Title', 'N/A', 'None', '', 'Total amount'
            ):
                continue
            # Bill token may be separated from its title by a space ("H73 Title")
            # or a semicolon ("H73; Title"); strip trailing punctuation before matching.
            parts = re.split(r'[;\s]', bill_cell, maxsplit=1)
            bill_no = parts[0].rstrip(';')
            bill_title = parts[1].strip() if len(parts) > 1 else ''
            m = re.match(r'^([A-Z]+)(\d+)$', bill_no)
            if not m:
                continue
            prefix, number = m.group(1), m.group(2)
            chamber = chamber_map.get(prefix, prefix)
            bills.append({
                'client_name': client_name,
                'chamber': chamber,
                'bill_number': number,
                'bill_title': bill_title,
                'position': position,
                'amount': amt,
                'general_court': gc,
            })

    # Compensation: prefer per-client totals from the activity table (2009–2013).
    # Fall back to grdvSalaryPaid (entity total under placeholder client) only
    # when no per-client compensation column exists (2005–2008).
    if comp_col is not None:
        per_client = {}
        for client_name, amt in legacy_comp_pairs:
            per_client[client_name] = per_client.get(client_name, 0.0) + amt
        for client_name, amt in per_client.items():
            if amt:
                compensation.append({'client_name': client_name, 'amount': amt})
    else:
        salary_table = soup.find(
            'table',
            id=lambda x: x and 'grdvSalaryPaid' in (x or '')
        )
        if salary_table:
            total = 0.0
            for row in salary_table.find_all('tr'):
                cells = [td.get_text(strip=True) for td in row.find_all('td')]
                if len(cells) >= 2:
                    amt = _parse_amount(cells[1])
                    if amt and 'Total' not in cells[0]:
                        total += amt
            if total:
                compensation.append({'client_name': '_total_salary_', 'amount': total})

    return {'compensation': compensation, 'bills': bills}


# ─── Incremental year selection ────────────────────────────────────────────────

def _years_to_check(existing_links: pd.DataFrame | None) -> list[int]:
    """Return years whose summary link list may have changed.

    Past years beyond current-1 are stable (filings are frozen after the year closes).
    Current and prior year are always re-checked for new filers.
    Any year with no links at all in the CSV is also included (missing years).
    """
    current_year = datetime.date.today().year
    all_years = list(range(FIRST_YEAR, current_year + 1))
    if existing_links is None or existing_links.empty:
        return all_years
    cached_years = set(existing_links['year'].dropna().astype(int))
    missing = sorted(set(all_years) - cached_years)
    always_check = {current_year, current_year - 1}
    return sorted(set(missing) | always_check)


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--year', type=int, default=None,
                        help='Fetch a single year only (for testing)')
    parser.add_argument('--limit', type=int, default=None,
                        help='Max registrants to fetch per year (for testing)')
    parser.add_argument('--archive-raw', action='store_true',
                        help='Save every fetched page HTML to MA_lobbying_raw_html/ '
                             'and upload a tarball to GCS Archive at end of run')
    args = parser.parse_args()

    global ARCHIVE_RAW
    ARCHIVE_RAW = args.archive_raw
    if ARCHIVE_RAW:
        print(f'Raw-HTML archival ENABLED -> {RAW_HTML_DIR}/')

    links_path     = DATA_DIR / 'MA_lobbying_summary_links.csv'
    employers_path = DATA_DIR / 'MA_lobbying_employers.csv'
    lobbyists_path = DATA_DIR / 'MA_lobbying_lobbyists.csv'
    bills_path     = DATA_DIR / 'MA_lobbying_bills.csv'

    # Pull state files from GCS if not present locally (e.g. fresh CI checkout).
    # Without this, every CI run starts from scratch and re-scrapes 22 years of history.
    for fname in GCS_STATE_FILES:
        local = DATA_DIR / fname
        if not local.exists():
            ret = os.system(f'gsutil -q cp {GCS_BUCKET}/{fname} {local} 2>/dev/null')
            if ret == 0:
                print(f'Restored {fname} from GCS ({local.stat().st_size // 1024:,} KB)')
            else:
                print(f'{fname} not in GCS yet — will do full fetch for missing years')

    # Load existing state — each file loaded independently so a missing optional
    # file (e.g. lobbyists, which isn't written until lobbyist data is scraped)
    # doesn't prevent resume from the others.
    def _load_csv(path, **kwargs):
        try:
            return pd.read_csv(path, **kwargs)
        except FileNotFoundError:
            return None

    existing_links     = _load_csv(links_path)
    existing_employers = _load_csv(employers_path, index_col=0)
    existing_bills     = _load_csv(bills_path, index_col=0)

    n_links = len(existing_links) if existing_links is not None else 0
    n_emp   = len(existing_employers) if existing_employers is not None else 0
    n_bills = len(existing_bills) if existing_bills is not None else 0
    if n_links or n_emp:
        print(f'Resuming: {n_links} summary links, {n_emp} employer rows, {n_bills} bill rows')
    else:
        print('No existing data — running full fetch')

    existing_disc_urls: set[str] = set()
    if existing_links is not None and 'disc_url' in existing_links.columns:
        existing_disc_urls = set(existing_links['disc_url'].dropna())

    years = [args.year] if args.year else _years_to_check(existing_links)
    print(f'Checking years: {years}')

    # Working copies of the DataFrames — mutated incrementally and flushed to disk
    # after every disclosure so any interrupt loses at most one disclosure's work.
    links_df     = existing_links     if existing_links     is not None else pd.DataFrame()
    employers_df = existing_employers if existing_employers is not None else pd.DataFrame()
    bills_df     = existing_bills     if existing_bills     is not None else pd.DataFrame()

    def _append(df: pd.DataFrame, new_rows: list[dict], dedup_keys: list[str]) -> pd.DataFrame:
        if not new_rows:
            return df
        new_df = pd.DataFrame(new_rows).drop_duplicates(subset=dedup_keys)
        if df.empty:
            return new_df
        return pd.concat([df, new_df], ignore_index=True).drop_duplicates(subset=dedup_keys)

    def _flush(n_new_disc: int) -> None:
        links_df.to_csv(links_path, index=False)
        employers_df.to_csv(employers_path)
        # QUOTE_NONNUMERIC ensures all string fields are quoted, preventing Jekyll's
        # CSV parser from choking on non-ASCII characters (e.g. smart quotes in titles).
        bills_df.to_csv(bills_path, quoting=csv.QUOTE_NONNUMERIC)
        print(f'    [flush] {len(links_df)} links, {len(employers_df)} employer rows, '
              f'{len(bills_df)} bill rows (+{n_new_disc} new disclosures this session)')

    def _upload_state() -> None:
        # Upload order matters: data files first, links file LAST.  The links
        # file is the skip-index — if a run dies between uploads, a stale links
        # file only means some disclosures get re-fetched next run (appends are
        # deduped).  Uploading links first could permanently lose bill/employer
        # rows: the index would say "fetched" while the data never made it out.
        for path, dest in ((bills_path, 'MA_lobbying_bills.csv'),
                           (employers_path, 'MA_lobbying_employers.csv'),
                           (links_path, 'MA_lobbying_summary_links.csv')):
            if path.exists():
                if os.system(f'gsutil -q cp {path} {GCS_BUCKET}/{dest}') != 0:
                    print(f'    WARNING: failed to upload {dest} to GCS')

    # ── Page-level skip logic ──────────────────────────────────────────────────
    # MA lobbying has two semi-annual disclosure periods per year:
    #   H1 (Jan–Jun): disclosures due ~Jul 15 of the same year
    #   H2 (Jul–Dec): disclosures due ~Jan 15 of the FOLLOWING year
    # Amendments are common (~11% of registrant-years have >2 disclosure URLs)
    # and cluster around those deadlines, so a disclosure-count cutoff cannot
    # work.  Instead, every summary page we visit is stamped with last_checked
    # in the links CSV (pages with no disclosures yet get a marker row with a
    # null disc_url).  A page is (re-)checked only while a filing window for
    # its year is active:
    #     window = [deadline - 14 days, deadline + GRACE_DAYS]
    # The `last_checked < window close` condition also forces exactly one
    # closing sweep after each window ends, then the page is skipped until the
    # year's next window (or forever, once both windows have closed).
    # Years are skipped wholesale before Jul 1 of that year — the H1 period
    # has not closed, so no disclosures can exist yet.
    GRACE_DAYS = 60
    today = datetime.date.today()

    if not links_df.empty and 'last_checked' not in links_df.columns:
        links_df['last_checked'] = pd.NA

    visited_summary: set[str] = set()
    last_checked: dict[str, datetime.date] = {}
    if not links_df.empty:
        visited_summary = set(links_df['summary_url'].dropna())
        _lc = pd.to_datetime(links_df['last_checked'], errors='coerce')
        for _url, _ts in zip(links_df['summary_url'], _lc):
            if pd.notna(_url) and pd.notna(_ts):
                _d = _ts.date()
                if _url not in last_checked or _d > last_checked[_url]:
                    last_checked[_url] = _d

    _EPOCH = datetime.date(1970, 1, 1)

    def _needs_check(url: str, year: int) -> bool:
        if url not in visited_summary:
            return True  # never seen this registrant-year — check once
        lc = last_checked.get(url, _EPOCH)
        for deadline in (datetime.date(year, 7, 15), datetime.date(year + 1, 1, 15)):
            window_open = deadline - datetime.timedelta(days=14)
            window_close = deadline + datetime.timedelta(days=GRACE_DAYS)
            if today >= window_open and lc < window_close:
                return True
        return False

    def _mark_checked(url: str, entity_name: str, year: int) -> None:
        nonlocal links_df
        visited_summary.add(url)
        last_checked[url] = today
        if not links_df.empty and links_df['summary_url'].eq(url).any():
            links_df.loc[links_df['summary_url'].eq(url), 'last_checked'] = today.isoformat()
        else:
            links_df = _append(links_df,
                               [{'entity_name': entity_name, 'year': year,
                                 'summary_url': url, 'disc_url': None,
                                 'last_checked': today.isoformat()}],
                               ['entity_name', 'year', 'summary_url', 'disc_url'])

    session = _make_session()
    total_new_disc = 0
    pages_checked = 0

    for year in years:
        print(f'\n--- {year} ---')
        if today < datetime.date(year, 7, 1):
            print(f'  H1 {year} period has not closed (disclosures due ~Jul 15) — skipping year')
            continue

        summary_urls = fetch_summary_links(session, year)
        to_check = [u for u in summary_urls if _needs_check(u, year)]
        print(f'  {len(summary_urls)} registrants on portal; '
              f'{len(summary_urls) - len(to_check)} skipped (no open filing window), '
              f'{len(to_check)} to check')

        if args.limit:
            to_check = to_check[:args.limit]

        year_new = 0
        for i, summary_url in enumerate(to_check):
            meta = fetch_disclosure_links(session, summary_url)
            entity_name = meta['entity_name']
            reg_type = meta['reg_type']

            for disc_url in meta['disclosure_urls']:
                if disc_url in existing_disc_urls:
                    continue  # already fetched

                detail = fetch_disclosure_detail(session, disc_url, year)

                new_employer_rows = [
                    {
                        'entity_name': entity_name,
                        'client_name': comp['client_name'],
                        'year': year,
                        'reg_type': reg_type,
                        'compensation': comp['amount'],
                    }
                    for comp in detail['compensation']
                ]
                new_bill_rows = [
                    {
                        'entity_name': entity_name,
                        'client_name': bill['client_name'],
                        'year': year,
                        'general_court': bill['general_court'],
                        'chamber': bill['chamber'],
                        'bill_number': bill['bill_number'],
                        'bill_title': bill['bill_title'],
                        'position': bill['position'],
                        'amount': bill['amount'],
                    }
                    for bill in detail['bills']
                ]

                employers_df = _append(employers_df, new_employer_rows,
                                       ['entity_name', 'client_name', 'year'])
                bills_df     = _append(bills_df, new_bill_rows,
                                       ['entity_name', 'client_name', 'bill_number', 'general_court'])
                # Drop any visited-marker row for this page before adding the real link
                if not links_df.empty:
                    links_df = links_df[~(links_df['summary_url'].eq(summary_url)
                                          & links_df['disc_url'].isna())]
                links_df     = _append(links_df,
                                       [{'entity_name': entity_name, 'year': year,
                                         'summary_url': summary_url, 'disc_url': disc_url,
                                         'last_checked': today.isoformat()}],
                                       ['entity_name', 'year', 'summary_url', 'disc_url'])

                existing_disc_urls.add(disc_url)
                total_new_disc += 1
                year_new += 1

                # Flush to disk after every disclosure — fully resumable on interrupt
                _flush(total_new_disc)

            _mark_checked(summary_url, entity_name, year)
            pages_checked += 1
            # Periodic state sync so a timed-out CI run still makes durable
            # progress — the next run resumes where this one died.
            if pages_checked % 200 == 0:
                _flush(total_new_disc)
                _upload_state()

            if (i + 1) % 50 == 0 or (i + 1) == len(to_check):
                print(f'  [{i+1}/{len(to_check)}] {year_new} new disclosures so far this year')

        print(f'  {year} done: {year_new} new disclosures')

    # Final state sync — also persists last_checked stamps and visited markers
    # from runs that found no new disclosures.
    if pages_checked or total_new_disc:
        _flush(total_new_disc)
        _upload_state()
        print(f'State synced to GCS ({pages_checked} pages checked this run)')

    # Flush the final partial raw-HTML batch (uploads + deletes local pages).
    if ARCHIVE_RAW:
        _flush_raw_batch()

    if total_new_disc == 0:
        print('\nNo new disclosures found.')
        return

    print(f'\nFinal totals: {len(links_df)} links, {len(employers_df)} employer rows, '
          f'{len(bills_df)} bill rows')

    with open(DATA_DIR / 'ts_update_MA_lobbying.yml', 'w') as f:
        f.write('updated: ' + str(datetime.datetime.now()).split('.')[0] + '\n')


if __name__ == '__main__':
    main()
