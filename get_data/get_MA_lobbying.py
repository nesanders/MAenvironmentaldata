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
import datetime
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

FIRST_YEAR = 2005
REQUEST_DELAY = 1.0  # seconds between requests

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (iPad; CPU OS 12_2 like Mac OS X) '
        'AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148'
    )
}

# General Court 183 started in 2005; each covers two calendar years.
FIRST_GENERAL_COURT = 183
FIRST_GC_START_YEAR = 2005


def _year_to_general_court(year: int) -> int:
    return FIRST_GENERAL_COURT + ((year - FIRST_GC_START_YEAR) // 2)


# ─── HTTP ──────────────────────────────────────────────────────────────────────

def _make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def _get(session, url, **kwargs) -> BeautifulSoup:
    time.sleep(REQUEST_DELAY)
    r = session.get(url, timeout=30, **kwargs)
    r.raise_for_status()
    return BeautifulSoup(r.text, 'html.parser')


def _post(session, url, data, timeout=120) -> BeautifulSoup:
    time.sleep(REQUEST_DELAY)
    r = session.post(url, data=data, timeout=timeout)
    r.raise_for_status()
    return BeautifulSoup(r.text, 'html.parser')


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
    """Fetch a Summary page and return registrant metadata + disclosure URLs.

    Returns dict with keys: entity_name, year, reg_type, disclosure_urls (list).
    """
    soup = _get(session, summary_url)

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
    """Parse a CompleteDisclosure page.

    Returns dict with:
      compensation: list of {client_name, amount}
      bills:        list of {client_name, chamber, bill_number, bill_title,
                              position, amount, general_court}
    """
    soup = _get(session, disc_url)
    compensation = []
    bills = []

    # Client compensation table
    comp_table = soup.find(
        'table',
        id=lambda x: x and 'grdvClientPaidToEntity' in (x or '')
    )
    if comp_table:
        for row in comp_table.find_all('tr', class_=lambda c: c and 'Grid' in c and 'Header' not in c):
            cells = [td.get_text(strip=True) for td in row.find_all('td')]
            if len(cells) >= 2:
                compensation.append({
                    'client_name': cells[0],
                    'amount': _parse_amount(cells[1]),
                })

    # Bill activity tables — one per client per reporting period
    # Table IDs: rptActivityNew2020_grdvActivitiesNew2020_{n}
    gc = _year_to_general_court(year)
    for act_table in soup.find_all(
        'table',
        id=lambda x: x and re.search(r'grdvActivitiesNew\d{4}_\d+', x or '')
    ):
        # Client name is in a span just before this table
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
            # Columns: House/Senate, Bill Number or Agency, Bill title, Position, Amount, Direct business
            if len(cells) >= 4:
                bills.append({
                    'client_name': client_name,
                    'chamber': cells[0],
                    'bill_number': cells[1],
                    'bill_title': cells[2] if len(cells) > 2 else '',
                    'position': cells[3] if len(cells) > 3 else '',
                    'amount': _parse_amount(cells[4]) if len(cells) > 4 else None,
                    'general_court': gc,
                })

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
    args = parser.parse_args()

    links_path     = DATA_DIR / 'MA_lobbying_summary_links.csv'
    employers_path = DATA_DIR / 'MA_lobbying_employers.csv'
    lobbyists_path = DATA_DIR / 'MA_lobbying_lobbyists.csv'
    bills_path     = DATA_DIR / 'MA_lobbying_bills.csv'

    # Load existing state
    existing_links = None
    existing_employers = existing_lobbyists = existing_bills = None
    try:
        existing_links     = pd.read_csv(links_path)
        existing_employers = pd.read_csv(employers_path, index_col=0)
        existing_lobbyists = pd.read_csv(lobbyists_path, index_col=0)
        existing_bills     = pd.read_csv(bills_path, index_col=0)
        print(f'Existing: {len(existing_links)} summary links, '
              f'{len(existing_employers)} employer rows')
    except FileNotFoundError:
        print('No existing data — running full fetch')

    existing_disc_urls: set[str] = set()
    if existing_links is not None and 'disc_url' in existing_links.columns:
        existing_disc_urls = set(existing_links['disc_url'].dropna())

    years = [args.year] if args.year else _years_to_check(existing_links)
    print(f'Checking years: {years}')

    session = _make_session()
    new_link_rows: list[dict] = []
    new_employer_rows: list[dict] = []
    new_lobbyist_rows: list[dict] = []
    new_bill_rows: list[dict] = []

    for year in years:
        print(f'\n--- {year} ---')
        summary_urls = fetch_summary_links(session, year)
        print(f'  {len(summary_urls)} registrants on portal')

        if args.limit:
            summary_urls = summary_urls[:args.limit]
        for i, summary_url in enumerate(summary_urls):
            meta = fetch_disclosure_links(session, summary_url)
            entity_name = meta['entity_name']
            reg_type = meta['reg_type']

            for disc_url in meta['disclosure_urls']:
                if disc_url in existing_disc_urls:
                    continue  # already fetched

                print(f'  [{i+1}/{len(summary_urls)}] {entity_name}: new disclosure')
                detail = fetch_disclosure_detail(session, disc_url, year)

                # Employer rows: one per (entity, client, year)
                for comp in detail['compensation']:
                    new_employer_rows.append({
                        'entity_name': entity_name,
                        'client_name': comp['client_name'],
                        'year': year,
                        'reg_type': reg_type,
                        'compensation': comp['amount'],
                    })

                # Bill rows
                for bill in detail['bills']:
                    new_bill_rows.append({
                        'entity_name': entity_name,
                        'client_name': bill['client_name'],
                        'year': year,
                        'general_court': bill['general_court'],
                        'chamber': bill['chamber'],
                        'bill_number': bill['bill_number'],
                        'bill_title': bill['bill_title'],
                        'position': bill['position'],
                        'amount': bill['amount'],
                    })

                new_link_rows.append({
                    'entity_name': entity_name,
                    'year': year,
                    'summary_url': summary_url,
                    'disc_url': disc_url,
                })
                existing_disc_urls.add(disc_url)

    if not new_link_rows and not new_employer_rows:
        print('\nNo new disclosures found — nothing to write.')
        return

    def _merge(existing, new_rows, dedup_keys):
        new_df = pd.DataFrame(new_rows)
        if new_df.empty:
            return existing if existing is not None else pd.DataFrame()
        new_df = new_df.drop_duplicates(subset=dedup_keys)
        if existing is None or existing.empty:
            return new_df
        return pd.concat([existing, new_df], ignore_index=True).drop_duplicates(
            subset=dedup_keys
        )

    links_df = _merge(existing_links, new_link_rows,
                      ['entity_name', 'year', 'disc_url'])
    employers_df = _merge(existing_employers, new_employer_rows,
                          ['entity_name', 'client_name', 'year'])
    bills_df = _merge(existing_bills, new_bill_rows,
                      ['entity_name', 'client_name', 'bill_number', 'general_court'])

    links_df.to_csv(links_path, index=False)
    employers_df.to_csv(employers_path)
    bills_df.to_csv(bills_path)
    # Lobbyist table not yet populated (requires lobbyist-level detail scraping;
    # entity pages list lobbyists but with less structured data — deferred)
    if new_lobbyist_rows:
        lobbyists_df = _merge(existing_lobbyists, new_lobbyist_rows,
                              ['lobbyist_name', 'entity_name', 'year'])
        lobbyists_df.to_csv(lobbyists_path)

    print(f'\nWrote {len(links_df)} link rows, {len(employers_df)} employer rows, '
          f'{len(bills_df)} bill rows')

    with open(DATA_DIR / 'ts_update_MA_lobbying.yml', 'w') as f:
        f.write('updated: ' + str(datetime.datetime.now()).split('.')[0] + '\n')


if __name__ == '__main__':
    main()
