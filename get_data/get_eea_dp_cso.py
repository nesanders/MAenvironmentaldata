"""Query the Combined Sewer Overflow (CSO) data from the EEA data portal.

Returns data on CSO discharge events and stores it as a CSV table.

We do this separately from `get_EEA_data_portal.py` because, while the CSO data is also
from the EEA Data Portal, it uses a distinct API endpoint (CSOAPI) with different
pagination and auth requirements.

Key implementation notes:
  - The CSOAPI requires a Referer header matching the portal page; bare requests
    return HTTP 500.  The REQ_HEADER below must be kept in sync with the portal URL.
  - The API is 1-indexed (pageNumber starts at 1, not 0).
  - Timestamps are ISO 8601 but may or may not include milliseconds; use format='ISO8601'.
  - The API returns a lowercase 'year' column; we drop it to avoid a case-insensitive
    name collision with our added 'Year' column when writing to SQLite.
  - Date-filtered queries (IncidentFromDate) work correctly when records exist, but
    the API returns HTTP 500 instead of an empty list when zero records match.  We
    treat a 500 on the first page of a filtered query as "no new records" and fall
    back to the existing cache unchanged.

Incremental fetching:
  When a cached CSV exists, we load it, find the max incidentDate, and fetch only
  records from that date onward (inclusive, to catch records that arrived after the
  last pull).  Cached rows on the boundary date are dropped before merging so there
  are no duplicates.  A full fetch is used when no cache exists.

Example API URL:
  https://eeaonline.eea.state.ma.us/dep/CSOAPI/api/Incident/GetIncidentsBySearchFields/
    ?IncidentFromDate=01/04/2026&pageNumber=1&pageSize=50

Outputs:
  ../docs/data/EEADP_CSO.csv         — full CSO incident table
  ../docs/data/EEADP_CSO_sample.csv  — 10-row random sample
  ../docs/data/ts_update_EEADP_CSO.yml — timestamp of last run
"""

import requests
import datetime
import pandas as pd

PORTAL_URL = 'https://eeaonline.eea.state.ma.us/portal/dep/cso-data-portal/'
API_BASE_URL = 'https://eeaonline.eea.state.ma.us/dep/CSOAPI/api/Incident/GetIncidentsBySearchFields/?pageSize=50&'

REQ_HEADER = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': PORTAL_URL,
    'Origin': 'https://eeaonline.eea.state.ma.us',
    'Accept': 'application/json, text/plain, */*',
}


def _make_session() -> requests.Session:
    return requests.Session()


def update_query_time():
    """Update the yml file that indicates the time of last query."""
    with open('../docs/data/ts_update_EEADP_CSO.yml', 'w') as f:
        f.write('updated: ' + str(datetime.datetime.now()).split('.')[0] + '\n')


def _query_page(session: requests.Session, page: int, query_params: dict[str, str] | None = None) -> pd.DataFrame | None:
    """Query for and return a single page of API results, or None if empty.

    Returns None both for a normal empty page (end of results) and for an HTTP 500,
    which the CSOAPI returns instead of an empty list when a filter matches no records.
    """
    print(f'Querying for page {page}')
    if query_params is None:
        query_params = {}
    query_params['pageNumber'] = page
    query_string = '&'.join(f'{key}={val}' for key, val in query_params.items())
    r = session.get(API_BASE_URL + query_string, headers=REQ_HEADER)
    if not r.ok or 'results' not in r.json():
        return None
    if len(r.json()['results']) > 0:
        return pd.concat([pd.Series(c) for c in r.json()['results']], axis=1).T
    else:
        return None


def run_query(session: requests.Session, from_date: str | None = None) -> pd.DataFrame:
    """Page through API results and return a combined DataFrame.

    from_date: optional MM/DD/YYYY string passed as IncidentFromDate.
    """
    if from_date:
        print(f'Running incremental query from {from_date}')
    else:
        print('Running full query')
    query_params: dict[str, str] = {}
    if from_date:
        query_params['IncidentFromDate'] = from_date
    page = 1  # CSOAPI is 1-indexed
    result_dfs = []
    while True:
        df = _query_page(session, page, query_params)
        if df is None:
            break
        result_dfs.append(df)
        page += 1
    if not result_dfs:
        return pd.DataFrame()
    return pd.concat(result_dfs)


def _parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    df['incidentDate'] = pd.to_datetime(df['incidentDate'], format='ISO8601')
    df['submittedDate'] = pd.to_datetime(df['submittedDate'], format='ISO8601')
    # API already returns a lowercase 'year' column; drop it before adding 'Year'
    # to avoid duplicate column names (case-insensitive collision in SQLite).
    df.drop(columns=[c for c in df.columns if c.lower() == 'year'], inplace=True)
    df['Year'] = df['incidentDate'].apply(lambda x: x.year)
    return df


def get_data() -> pd.DataFrame:
    """Fetch CSO data incrementally when a cached CSV exists, otherwise full fetch."""
    csv_path = '../docs/data/EEADP_CSO.csv'
    from_date: str | None = None
    existing: pd.DataFrame | None = None

    try:
        existing = pd.read_csv(csv_path, index_col=0)
        existing['incidentDate'] = pd.to_datetime(existing['incidentDate'], format='ISO8601')
        # submittedDate must also be parsed here (not just incidentDate): leaving it
        # as a raw string column means pd.concat([existing, new_df]) below produces
        # a mixed object column (raw CSV strings next to real Timestamps from
        # _parse_dates), which the write-side normalization can't safely re-parse.
        existing['submittedDate'] = pd.to_datetime(existing['submittedDate'], format='ISO8601')
        max_date = existing['incidentDate'].max()
        # The CSOAPI parses IncidentFromDate as DD/MM/YYYY (day-first), NOT the
        # US-style MM/DD/YYYY. Sending month-first silently filters from the wrong
        # month when the day is <= 12, and returns HTTP 500 (invalid month) when the
        # day is > 12 — which run_query() swallows as "no new records", silently
        # freezing the dataset (this stalled CSO updates at 2026-04-19 for months).
        from_date = max_date.strftime('%d/%m/%Y')
        # Drop cached rows on the boundary date — the API refetch will include them.
        existing = existing[existing['incidentDate'].dt.date < max_date.date()].copy()
        print(f'  Cached data through {max_date.date()}; fetching from {from_date} (inclusive)')
    except FileNotFoundError:
        print('  No cache found; running full query')

    session = _make_session()
    raw = run_query(session, from_date=from_date)

    if raw.empty:
        # API returned 500 (no-records) or genuinely empty; use cache as-is.
        print('  No new records returned; using existing cache unchanged.')
        if existing is not None:
            # Restore the boundary rows we dropped before returning
            full_existing = pd.read_csv('../docs/data/EEADP_CSO.csv', index_col=0)
            return full_existing
        # No cache and no data — nothing to write.
        raise RuntimeError('CSO API returned no data and no cache exists.')

    new_df = _parse_dates(raw)

    if existing is not None:
        df = pd.concat([existing, new_df], ignore_index=True)
    else:
        df = new_df

    return df


def write_data(df: pd.DataFrame):
    """Write data to a local table for integration with AMEND."""
    print('Writing out queried data')
    # incidentDate is always midnight in the API (time-of-day lives in the
    # separate incidentTime field); when an incremental batch of new rows is
    # ALL exactly midnight, pandas' to_csv formats that batch as bare
    # "YYYY-MM-DD" (no time) while older rows in the same file keep
    # "YYYY-MM-DD HH:MM:SS" — a genuinely mixed-format column that later
    # breaks a plain pd.to_datetime() re-parse (ValueError: time data
    # "YYYY-MM-DD" doesn't match format "%Y-%m-%d %H:%M:%S"). Format both
    # date columns to an explicit, uniform string before writing so every
    # row is unambiguous regardless of pandas' internal formatting.
    out = df.copy()
    for col in ('incidentDate', 'submittedDate'):
        # format='mixed': the incoming column may itself be a mix of raw CSV
        # strings and real Timestamp objects (e.g. if a caller skipped parsing
        # on load) — infer per-element rather than assuming one format.
        out[col] = pd.to_datetime(out[col], format='mixed').dt.strftime('%Y-%m-%d %H:%M:%S')
    out.to_csv('../docs/data/EEADP_CSO.csv', index=True)
    out.sample(n=10).to_csv('../docs/data/EEADP_CSO_sample.csv', index=False)


def main():
    all_data = get_data()
    write_data(all_data)
    update_query_time()


if __name__ == '__main__':
    main()
