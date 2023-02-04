"""Query the Combined Sewer Overflow (CSO) data from the EEA data portal to return data on CSO discharge events,
and store that data in a table.

We do this separately from the `get_EEA_data_portal.py` script because, while the CSO data is also from the Data Portal,
the API is somewhat different.

This is an example query to the data portal API:
https://eeaonline.eea.state.ma.us/dep/CSOAPI/api/Incident/GetIncidentsBySearchFields/?ReporterClass=Verified%20Data%20Report&IncidentFromDate=01/01/2022&IncidentToDate=08/02/2023&RainfallDataFrom=1&pageNumber=2&pageSize=50&
"""

import json
import requests
from typing import Optional

import datetime
import pandas as pd

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
    r = requests.get(API_BASE_URL + query_string)
    if len(r.json()['results']) > 0:
        return pd.concat([pd.Series(c) for c in r.json()['results']], axis=1).T
    else:
        return None

def run_query() -> pd.DataFrame:
    """Run a full query, paging through results and returning a combined DataFrame.
    """
    print('Running full query')
    page = 0
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
    df['incidentDate'] = pd.to_datetime(df['incidentDate'])
    df['submittedDate'] = pd.to_datetime(df['submittedDate'])
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
