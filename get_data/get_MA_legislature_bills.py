"""Fetch bill metadata from the MA Legislature OpenAPI for bills appearing in lobbying data.

API docs: https://malegislature.gov/api/swagger

The API uses /Documents/{billId} (not /Bills/). Bill IDs require a chamber prefix:
  House Bill / House Docket  → H{number}  (e.g. H4999)
  Senate Bill / Senate Docket → S{number} (e.g. S607)
  Executive → skipped (no legislature bill ID)

Status is fetched via a separate /DocumentHistoryActions call; the `Action` field
of the last entry is used to derive the `passed` boolean.

Fetches only bills that appear in MA_lobbying_bills.csv (scoped to keep the request
volume bounded). For each unique (bill_id, general_court) pair, retrieves:
  - Bill title
  - Primary sponsor name
  - Current status / final disposition
  - Derived `passed` boolean (True if bill was enacted/signed)

Caches raw JSON responses under MA_legislature_cache/ for incremental re-runs.

Run from the get_data/ directory after get_MA_lobbying.py:
    /path/to/python -u get_MA_legislature_bills.py

Outputs:
  ../docs/data/MA_legislature_bills.csv
  ../docs/data/ts_update_MA_legislature.yml
"""

import csv
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

# Action text fragments that indicate a bill was enacted/signed into law.
PASSED_ACTIONS = {
    'Signed by the Governor',
    'Enacted',
    'Approved by the Governor',
    'Chaptered',
    'Filed with the Secretary of State',
}

# Chamber values in lobbying data → API bill ID prefix
CHAMBER_PREFIX = {
    'House Bill': 'H',
    'HB': 'H',           # legacy abbreviation
    'House Docket': 'HD',
    'Senate Bill': 'S',
    'SB': 'S',           # legacy abbreviation
    'Senate Docket': 'SD',
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


def _get_json(session: requests.Session, url: str, cache_key: str | None = None
              ) -> dict | list | None:
    """Fetch a JSON endpoint with optional caching. Returns None on error."""
    if cache_key:
        cached = _load_cache(cache_key)
        if cached is not None:
            return cached
    time.sleep(REQUEST_DELAY)
    try:
        r = session.get(url, timeout=30)
    except requests.RequestException as e:
        print(f'  Request error for {url}: {e}')
        return None
    if not r.ok:
        return None
    try:
        data = r.json()
    except ValueError:
        return None
    if cache_key:
        _save_cache(cache_key, data)
    return data


# ─── Bill ID construction ──────────────────────────────────────────────────────

def _bill_id(bill_number, chamber: str) -> str | None:
    """Construct the API bill ID from a bare number and chamber string.

    Returns None for chamber types with no legislature bill (e.g. Executive)
    or for non-numeric bill_number values (parser artefacts like 'N', '4134HD4547').
    """
    prefix = CHAMBER_PREFIX.get(chamber)
    if prefix is None:
        return None
    try:
        return f'{prefix}{int(bill_number)}'
    except (ValueError, TypeError):
        return None


# ─── Bill metadata fetch ────────────────────────────────────────────────────────

def fetch_bill(session: requests.Session, bill_id: str, general_court: int) -> dict | None:
    """Fetch metadata for a single bill. Returns None if not found or on error."""
    cache_key = f'bill_{general_court}_{bill_id}'
    url = f'{API_BASE}/GeneralCourts/{general_court}/Documents/{bill_id}'
    data = _get_json(session, url, cache_key=cache_key)
    if not data or not isinstance(data, dict):
        return None

    title = data.get('Title') or ''

    sponsor_raw = data.get('PrimarySponsor')
    if isinstance(sponsor_raw, dict):
        sponsor_name = sponsor_raw.get('Name') or ''
    else:
        sponsor_name = ''

    # BillHistory is a URL — fetch it separately for the latest action/status
    history_url = data.get('BillHistory')
    passed = False
    status_text = ''
    if history_url and isinstance(history_url, str) and history_url.startswith('http'):
        history_cache_key = f'history_{general_court}_{bill_id}'
        history = _get_json(session, history_url, cache_key=history_cache_key)
        if isinstance(history, list) and history:
            latest = history[-1]
            status_text = latest.get('Action') or ''
            passed = any(s in status_text for s in PASSED_ACTIONS)

    # Extract bare bill number and prefix for joining back to lobbying data
    import re
    m = re.match(r'^([A-Z]+)(\d+)$', bill_id)
    prefix = m.group(1) if m else ''
    bare_number = int(m.group(2)) if m else None

    return {
        'bill_id': bill_id,
        'bill_number': bare_number,
        'bill_prefix': prefix,
        'general_court': general_court,
        'title': title,
        'sponsor_name': sponsor_name,
        'status': status_text,
        'passed': passed,
    }


# ─── Main ───────────────────────────────────────────────────────────────────────

def main():
    bills_lobby_path = DATA_DIR / 'MA_lobbying_bills.csv'
    if not bills_lobby_path.exists():
        print(f'ERROR: {bills_lobby_path} not found. Run get_MA_lobbying.py first.')
        return

    lobby_bills = pd.read_csv(bills_lobby_path, index_col=0)

    # Build unique (bill_id, general_court) pairs, skipping non-legislature chambers
    unique_bills = (
        lobby_bills[['bill_number', 'chamber', 'general_court']]
        .dropna(subset=['bill_number', 'general_court'])
        .drop_duplicates()
    )
    unique_bills['bill_id'] = unique_bills.apply(
        lambda r: _bill_id(r['bill_number'], r['chamber']), axis=1
    )
    unique_bills = unique_bills.dropna(subset=['bill_id'])
    unique_bills = unique_bills[['bill_id', 'general_court']].drop_duplicates()
    print(f'Found {len(unique_bills)} unique (bill_id, session) pairs to look up')

    # Load existing cache to skip already-fetched bills
    legislature_path = DATA_DIR / 'MA_legislature_bills.csv'
    existing: pd.DataFrame | None = None
    already_fetched: set = set()
    try:
        existing = pd.read_csv(legislature_path, index_col=0)
        already_fetched = set(
            zip(existing['bill_id'].astype(str), existing['general_court'].astype(int))
        )
        print(f'  {len(existing)} bills already fetched')
    except FileNotFoundError:
        pass

    to_fetch = [
        row for _, row in unique_bills.iterrows()
        if (str(row['bill_id']), int(row['general_court'])) not in already_fetched
    ]
    print(f'Fetching metadata for {len(to_fetch)} new bills...')

    session = _make_session()
    # Work against the combined DataFrame so flushes are always complete snapshots
    combined = existing.copy() if existing is not None and not existing.empty else pd.DataFrame()
    FLUSH_EVERY = 50

    def _flush(n_done: int) -> None:
        combined.to_csv(legislature_path, quoting=csv.QUOTE_NONNUMERIC)
        print(f'  [{n_done}/{len(to_fetch)}] flushed {len(combined)} bill records')

    for i, row in enumerate(to_fetch):
        bid = str(row['bill_id'])
        gc = int(row['general_court'])
        result = fetch_bill(session, bid, gc)
        new_row = result if result else {
            'bill_id': bid,
            'general_court': gc,
            'bill_number': None,
            'bill_prefix': '',
            'title': '',
            'sponsor_name': '',
            'status': '',
            'passed': False,
        }
        new_df = pd.DataFrame([new_row])
        if combined.empty:
            combined = new_df
        else:
            combined = pd.concat([combined, new_df], ignore_index=True).drop_duplicates(
                subset=['bill_id', 'general_court']
            )

        if (i + 1) % FLUSH_EVERY == 0 or (i + 1) == len(to_fetch):
            _flush(i + 1)

    if combined.empty:
        print('No new bills to write.')
        return

    print(f'Wrote {len(combined)} bill records to {legislature_path}')

    with open(DATA_DIR / 'ts_update_MA_legislature.yml', 'w') as f:
        f.write('updated: ' + str(datetime.datetime.now()).split('.')[0] + '\n')


if __name__ == '__main__':
    main()
