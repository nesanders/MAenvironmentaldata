"""Fetch bill metadata from the MA Legislature OpenAPI for bills appearing in lobbying data.

API docs: https://malegislature.gov/api/swagger

Fetches only bills that appear in MA_lobbying_bills.csv (scoped to keep the request
volume bounded). For each unique (bill_number, general_court) pair, retrieves:
  - Bill title / docket title
  - Primary sponsor name and chamber
  - Committee referral
  - Current status / final disposition
  - Derived `passed` boolean (True if bill was enacted/signed)

Also fetches the list of General Court sessions to resolve session numbers to year ranges.

Caches raw JSON responses under MA_legislature_cache/ for incremental re-runs.

Run from the get_data/ directory after get_MA_lobbying.py:
    conda run -n amend_python python get_MA_legislature_bills.py

Outputs:
  ../docs/data/MA_legislature_bills.csv
  ../docs/data/ts_update_MA_legislature.yml
"""

import datetime
import json
import time
from pathlib import Path

import pandas as pd
import requests

# ─── Configuration ─────────────────────────────────────────────────────────────

API_BASE = 'https://malegislature.gov/api'
CACHE_DIR = Path('MA_legislature_cache')
DATA_DIR = Path('../docs/data')

REQUEST_DELAY = 0.5  # seconds between API requests

REQ_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept': 'application/json',
}

# Statuses that indicate a bill was enacted/signed into law.
PASSED_STATUSES = {
    'Signed by the Governor',
    'Enacted',
    'Approved by the Governor',
    'Chaptered',
    'Filed with the Secretary of State',
}

# ─── Caching helpers ───────────────────────────────────────────────────────────

def _cache_path(key: str) -> Path:
    return CACHE_DIR / f'{key}.json'


def _load_cache(key: str) -> dict | list | None:
    p = _cache_path(key)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            return None
    return None


def _save_cache(key: str, data: dict | list) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    _cache_path(key).write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')


# ─── API helpers ───────────────────────────────────────────────────────────────

def _make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(REQ_HEADERS)
    return s


def _get_json(session: requests.Session, path: str, cache_key: str | None = None
              ) -> dict | list | None:
    """Fetch a JSON endpoint with caching. Returns None on non-2xx or parse error."""
    if cache_key:
        cached = _load_cache(cache_key)
        if cached is not None:
            return cached
    time.sleep(REQUEST_DELAY)
    url = f'{API_BASE}/{path.lstrip("/")}'
    try:
        r = session.get(url, timeout=30)
    except requests.RequestException as e:
        print(f'  Request error for {url}: {e}')
        return None
    if not r.ok:
        print(f'  HTTP {r.status_code} for {url}')
        return None
    try:
        data = r.json()
    except ValueError:
        print(f'  JSON parse error for {url}')
        return None
    if cache_key:
        _save_cache(cache_key, data)
    return data


# ─── General Court index ───────────────────────────────────────────────────────

def fetch_general_courts(session: requests.Session) -> pd.DataFrame:
    """Return a DataFrame of General Court sessions with their year ranges."""
    data = _get_json(session, '/GeneralCourts', cache_key='general_courts')
    if not data:
        return pd.DataFrame()
    rows = []
    for gc in (data if isinstance(data, list) else data.get('GeneralCourts', [])):
        gc_num = gc.get('GeneralCourtNumber') or gc.get('generalCourtNumber')
        name = gc.get('Name') or gc.get('name', '')
        # Extract year range from name like "193rd General Court (2023-2024)"
        import re
        year_match = re.search(r'\((\d{4})-(\d{4})\)', name)
        start_year = int(year_match.group(1)) if year_match else None
        end_year = int(year_match.group(2)) if year_match else None
        rows.append({
            'general_court': gc_num,
            'session_name': name,
            'start_year': start_year,
            'end_year': end_year,
        })
    return pd.DataFrame(rows)


# ─── Bill metadata fetch ────────────────────────────────────────────────────────

def _parse_bill(data: dict, bill_number: str, general_court: int) -> dict:
    """Extract structured fields from a bill API response object."""
    # The API may return either camelCase or PascalCase fields depending on version
    def _get(*keys):
        for k in keys:
            v = data.get(k)
            if v is not None:
                return v
        return None

    title = _get('Title', 'title', 'DocketTitle', 'docketTitle', 'BillDescription') or ''

    # Sponsor: may be a nested object or string
    sponsor_raw = _get('Sponsor', 'sponsor', 'PrimarySponsor', 'primarySponsor')
    if isinstance(sponsor_raw, dict):
        sponsor_name = (sponsor_raw.get('Name') or sponsor_raw.get('name') or
                        sponsor_raw.get('FullName') or sponsor_raw.get('fullName') or '')
        sponsor_chamber = sponsor_raw.get('Branch') or sponsor_raw.get('branch') or ''
    elif isinstance(sponsor_raw, str):
        sponsor_name = sponsor_raw
        sponsor_chamber = ''
    else:
        sponsor_name = ''
        sponsor_chamber = ''

    # Committee
    committee_raw = _get('Committee', 'committee', 'CommitteeReferral', 'committeeReferral')
    if isinstance(committee_raw, dict):
        committee = committee_raw.get('Name') or committee_raw.get('name') or ''
    elif isinstance(committee_raw, str):
        committee = committee_raw
    else:
        committee = ''

    # Status / disposition
    status = _get('BillHistory', 'billHistory', 'CurrentStatus', 'currentStatus',
                  'Status', 'status')
    if isinstance(status, list) and status:
        # BillHistory is a list; most recent entry is last
        latest = status[-1]
        status_text = (latest.get('StatusDescription') or latest.get('statusDescription') or
                       latest.get('Status') or latest.get('status') or '')
    elif isinstance(status, dict):
        status_text = (status.get('Description') or status.get('description') or
                       status.get('Status') or status.get('status') or '')
    elif isinstance(status, str):
        status_text = status
    else:
        status_text = ''

    passed = any(s in status_text for s in PASSED_STATUSES)

    return {
        'bill_number': bill_number,
        'general_court': general_court,
        'title': title,
        'sponsor_name': sponsor_name,
        'sponsor_chamber': sponsor_chamber,
        'committee': committee,
        'status': status_text,
        'passed': passed,
    }


def fetch_bill(session: requests.Session, bill_number: str, general_court: int) -> dict | None:
    """Fetch metadata for a single bill. Returns None if not found or on error."""
    # Normalize bill number for API: "H.1234" → "H1234", "S.5678" → "S5678"
    import re
    bill_id = re.sub(r'[.\s]', '', bill_number).upper()
    cache_key = f'bill_{general_court}_{bill_id}'
    data = _get_json(session, f'/GeneralCourts/{general_court}/Bills/{bill_id}',
                     cache_key=cache_key)
    if not data:
        return None
    return _parse_bill(data, bill_number, general_court)


# ─── Main ───────────────────────────────────────────────────────────────────────

def main():
    bills_lobby_path = DATA_DIR / 'MA_lobbying_bills.csv'
    if not bills_lobby_path.exists():
        print(f'ERROR: {bills_lobby_path} not found. Run get_MA_lobbying.py first.')
        return

    lobby_bills = pd.read_csv(bills_lobby_path, index_col=0)
    unique_bills = (
        lobby_bills[['bill_number', 'general_court']]
        .dropna()
        .drop_duplicates()
    )
    print(f'Found {len(unique_bills)} unique (bill, session) pairs to look up')

    # Load existing cache to skip already-fetched bills
    legislature_path = DATA_DIR / 'MA_legislature_bills.csv'
    existing: pd.DataFrame | None = None
    try:
        existing = pd.read_csv(legislature_path, index_col=0)
        already_fetched = set(
            zip(existing['bill_number'].astype(str), existing['general_court'].astype(int))
        )
        print(f'  {len(existing)} bills already in cache')
    except FileNotFoundError:
        already_fetched = set()

    session = _make_session()

    # Fetch General Court index
    gc_df = fetch_general_courts(session)
    if not gc_df.empty:
        gc_path = DATA_DIR / 'MA_general_courts.csv'
        gc_df.to_csv(gc_path)
        print(f'Wrote General Court index ({len(gc_df)} sessions) to {gc_path}')

    # Fetch bill metadata for new bills only
    new_rows = []
    to_fetch = [
        row for _, row in unique_bills.iterrows()
        if (str(row['bill_number']), int(row['general_court'])) not in already_fetched
    ]
    print(f'Fetching metadata for {len(to_fetch)} new bills...')

    for i, row in enumerate(to_fetch):
        bn = str(row['bill_number'])
        gc = int(row['general_court'])
        if (i + 1) % 50 == 0:
            print(f'  {i + 1}/{len(to_fetch)}...')
        result = fetch_bill(session, bn, gc)
        if result:
            new_rows.append(result)
        else:
            # Record a stub so we don't retry on every run
            new_rows.append({
                'bill_number': bn,
                'general_court': gc,
                'title': '',
                'sponsor_name': '',
                'sponsor_chamber': '',
                'committee': '',
                'status': '',
                'passed': False,
            })

    new_df = pd.DataFrame(new_rows)
    if existing is not None and not existing.empty:
        combined = pd.concat([existing, new_df], ignore_index=True).drop_duplicates(
            subset=['bill_number', 'general_court']
        )
    else:
        combined = new_df

    combined.to_csv(legislature_path)
    print(f'Wrote {len(combined)} bill records to {legislature_path}')

    with open(DATA_DIR / 'ts_update_MA_legislature.yml', 'w') as f:
        f.write('updated: ' + str(datetime.datetime.now()).split('.')[0] + '\n')


if __name__ == '__main__':
    main()
