"""Query the Combined Sewer Overflow (CSO) data from the EEA data portal.

Returns data on CSO discharge events and stores it as a CSV table.

We do this separately from `get_EEA_data_portal.py` because, while the CSO data is also
from the EEA Data Portal, it uses a distinct API endpoint (CSOAPI) with different
pagination and auth requirements.

Key implementation notes:
  - The CSOAPI requires a Referer header pointing to the portal page; bare requests
    return HTTP 500.  The REQ_HEADER below must be kept in sync with the portal URL.
  - The API is 1-indexed (pageNumber starts at 1, not 0).
  - Timestamps are ISO 8601 but may or may not include milliseconds; use format='ISO8601'.
  - The API returns a lowercase 'year' column; we drop it to avoid a case-insensitive
    name collision with our added 'Year' column when writing to SQLite.

Example API URL:
  https://eeaonline.eea.state.ma.us/dep/CSOAPI/api/Incident/GetIncidentsBySearchFields/
    ?ReporterClass=Verified%20Data%20Report&IncidentFromDate=01/01/2022
    &IncidentToDate=08/02/2023&RainfallDataFrom=1&pageNumber=2&pageSize=50

Outputs:
  ../docs/data/EEADP_CSO.csv         — full CSO incident table
  ../docs/data/EEADP_CSO_sample.csv  — 10-row random sample
  ../docs/data/ts_update_EEADP_CSO.yml — timestamp of last run
"""

import requests
from typing import Optional

import datetime
import pandas as pd

# The CSOAPI requires a Referer header matching the portal page; plain User-Agent requests return 500.
REQ_HEADER = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://eeaonline.eea.state.ma.us/portal/dep/cso-data-portal/',
    'Origin': 'https://eeaonline.eea.state.ma.us',
    'Accept': 'application/json, text/plain, */*',
}

API_BASE_URL = 'https://eeaonline.eea.state.ma.us/dep/CSOAPI/api/Incident/GetIncidentsBySearchFields/?pageSize=50&'

def update_query_time():
    """Update the yml file that indicates the time of last query.
    """
    with open('../docs/data/ts_update_EEADP_CSO.yml', 'w') as f:
        f.write('updated: '+str(datetime.datetime.now()).split('.')[0]+'\n')

def _query_page(page: int, query_params: Optional[dict[str, str]]=None) -> Optional[pd.DataFrame]:
    """Query for and return a single page of API results.

    If the resulting query is empty, return Non
    """
    print(f'Querying for page {page}')
    if query_params is None:
        query_params = {}
    query_params['pageNumber'] = page
    query_string = '&'.join(f'{key}={val}' for key, val in query_params.items())
    r = requests.get(API_BASE_URL + query_string, headers=REQ_HEADER)
    if len(r.json()['results']) > 0:
        return pd.concat([pd.Series(c) for c in r.json()['results']], axis=1).T
    else:
        return None

def run_query() -> pd.DataFrame:
    """Run a full query, paging through results and returning a combined DataFrame.
    """
    print('Running full query')
    page = 1  # CSOAPI is 1-indexed
    result_dfs = []
    while True:
        df = _query_page(page)
        if df is None:
            break
        result_dfs.append(df)
        page += 1
    return pd.concat(result_dfs)

def get_data() -> pd.DataFrame:
    """Query data from the data portal API and do any necessary post processing.
    """
    df = run_query()
    df['incidentDate'] = pd.to_datetime(df['incidentDate'], format='ISO8601')
    df['submittedDate'] = pd.to_datetime(df['submittedDate'], format='ISO8601')
    # API already returns a lowercase 'year' column; drop it before adding 'Year'
    # to avoid duplicate column names (case-insensitive collision in SQLite).
    df.drop(columns=[c for c in df.columns if c.lower() == 'year'], inplace=True)
    df['Year'] = df['incidentDate'].apply(lambda x: x.year)
    return df

def write_data(df: pd.DataFrame):
    """Write data to a local table for integration with AMEND.
    """
    print('Writing out queries data')
    df.to_csv('../docs/data/EEADP_CSO.csv', index=True)
    ## Print a sample of the file as an example
    df.sample(n=10).to_csv('../docs/data/EEADP_CSO_sample.csv', index=0)

def main():
    """Query and write all data.
    """
    all_data = get_data()
    write_data(all_data)
    update_query_time()

if __name__ == '__main__':
    main()
