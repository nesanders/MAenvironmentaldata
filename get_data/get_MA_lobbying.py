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


def _get(session, url, retries=5, **kwargs) -> BeautifulSoup:
    for attempt in range(retries):
        time.sleep(REQUEST_DELAY * (2 ** attempt) if attempt else REQUEST_DELAY)
        try:
            r = session.get(url, timeout=60, **kwargs)
            r.raise_for_status()
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

    Two HTML formats exist depending on the filing year:

    Modern (≥~2013): per-client compensation in grdvClientPaidToEntity;
      per-client bill tables as grdvActivitiesNew{year}_{n}.

    Legacy (<~2013): total salary paid in grdvSalaryPaid (no client breakdown);
      all bill activity in a single grdvActivities table with columns:
      Date | Bill No+Title | Lobbyist name | Client represented.

    Returns dict with:
      compensation: list of {client_name, amount}
      bills:        list of {client_name, chamber, bill_number, bill_title,
                              position, amount, general_court}
    """
    soup = _get(session, disc_url)
    compensation = []
    bills = []
    gc = _year_to_general_court(year)

    # ── Modern format ─────────────────────────────────────────────────────────
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
    for act_table in soup.find_all(
        'table',
        id=lambda x: x and re.search(r'grdvActivitiesNew\d{4}_\d+', x or '')
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
                bills.append({
                    'client_name': client_name,
                    'chamber': cells[0],
                    'bill_number': cells[1],
                    'bill_title': cells[2] if len(cells) > 2 else '',
                    'position': cells[3] if len(cells) > 3 else '',
                    'amount': _parse_amount(cells[4]) if len(cells) > 4 else None,
                    'general_court': gc,
                })

    if comp_table or bills:
        return {'compensation': compensation, 'bills': bills}

    # ── Legacy format ─────────────────────────────────────────────────────────
    # Compensation: grdvSalaryPaid has total salary paid to lobbyists, not per
    # client. Sum to a single entity-level row using a placeholder client name.
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

    # Bills: single grdvActivities table — columns: Date | Bill+Title | Lobbyist | Client
    act_table = soup.find(
        'table',
        id=lambda x: x and x.endswith('grdvActivities')
    )
    if act_table:
        for row in act_table.find_all('tr'):
            cells = [td.get_text(strip=True) for td in row.find_all('td')]
            # Skip header and empty rows; need at least Date + Bill + Client
            if len(cells) < 3:
                continue
            bill_cell = cells[1]   # e.g. "H1166" or "H1166 An Act..."
            client_name = cells[3] if len(cells) > 3 else ''
            if not bill_cell or bill_cell in ('Activity or Bill No and Title', 'N/A', ''):
                continue
            # Split bill number from title (bill number is the first token)
            parts = bill_cell.split(None, 1)
            bill_no = parts[0]
            bill_title = parts[1] if len(parts) > 1 else ''
            # Derive chamber from bill number prefix
            chamber_map = {'H': 'House Bill', 'S': 'Senate Bill',
                           'HD': 'House Docket', 'SD': 'Senate Docket'}
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
                'position': '',
                'amount': None,
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

    session = _make_session()
    total_new_disc = 0

    for year in years:
        print(f'\n--- {year} ---')
        summary_urls = fetch_summary_links(session, year)
        print(f'  {len(summary_urls)} registrants on portal')

        if args.limit:
            summary_urls = summary_urls[:args.limit]

        year_new = 0
        for i, summary_url in enumerate(summary_urls):
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
                links_df     = _append(links_df,
                                       [{'entity_name': entity_name, 'year': year,
                                         'summary_url': summary_url, 'disc_url': disc_url}],
                                       ['entity_name', 'year', 'disc_url'])

                existing_disc_urls.add(disc_url)
                total_new_disc += 1
                year_new += 1

                # Flush to disk after every disclosure — fully resumable on interrupt
                _flush(total_new_disc)

            if (i + 1) % 50 == 0 or (i + 1) == len(summary_urls):
                print(f'  [{i+1}/{len(summary_urls)}] {year_new} new disclosures so far this year')

        print(f'  {year} done: {year_new} new disclosures')

    if total_new_disc == 0:
        print('\nNo new disclosures found — nothing to write.')
        return

    print(f'\nFinal totals: {len(links_df)} links, {len(employers_df)} employer rows, '
          f'{len(bills_df)} bill rows')

    with open(DATA_DIR / 'ts_update_MA_lobbying.yml', 'w') as f:
        f.write('updated: ' + str(datetime.datetime.now()).split('.')[0] + '\n')


if __name__ == '__main__':
    main()
