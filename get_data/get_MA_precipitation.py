"""Fetch daily precipitation data for Massachusetts from NOAA's ACIS web service.

Stores one row per calendar day: the average precipitation (inches) across all MA
GHCN/COOP stations that reported on that day.  Keeping daily granularity allows
downstream analysis to apply any aggregation or threshold (e.g. annual totals,
heavy-rain-day counts, event-level correlations) without re-fetching data.

ACIS (Applied Climate Information System) is operated by the NOAA Regional Climate Centers
and requires no API key for basic data access.
Documentation: https://www.rcc-acis.org/docs_webservices.html

Fetching is done year-by-year to keep individual requests to a manageable size
(~658 stations × 365 days per chunk).

Outputs:
  ../docs/data/MA_precipitation_daily.csv  — daily precip averages (START_YEAR–present)
  ../docs/data/ts_update_MA_precipitation.yml — timestamp of last run
"""

import datetime
import requests
import pandas as pd
import numpy as np

ACIS_URL = 'https://data.rcc-acis.org/MultiStnData'
START_YEAR = 2000        # Historical context back to 2000


def fetch_daily_precip_year(year: int) -> pd.DataFrame:
    """Query ACIS for all MA stations for a single calendar year.

    Returns a DataFrame with one row per day: date, precip_in_avg (station average),
    n_stations (number of stations reporting that day).
    """
    sdate = f'{year}-01-01'
    edate = f'{year}-12-31'
    resp = requests.post(ACIS_URL, json={
        'state': 'MA',
        'sdate': sdate,
        'edate': edate,
        'elems': [{'name': 'pcpn', 'interval': 'dly'}],
        'meta': 'name',
    }, timeout=120)
    resp.raise_for_status()
    stations = resp.json()['data']

    dates = pd.date_range(sdate, edate, freq='D')
    matrix = pd.DataFrame(index=dates, dtype=float)

    for stn in stations:
        name = stn['meta']['name']
        rows = stn['data']
        if len(rows) != len(dates):
            continue
        vals = []
        for v in rows:
            raw = v[0]
            if raw in ('M', 'T', '', None):
                vals.append(np.nan)
            else:
                try:
                    vals.append(float(raw))
                except ValueError:
                    vals.append(np.nan)
        matrix[name] = vals

    result = pd.DataFrame({
        'date': dates.strftime('%Y-%m-%d'),
        'precip_in_avg': matrix.mean(axis=1).values,
        'n_stations': matrix.notna().sum(axis=1).values,
    })
    return result


def main():
    current_year = datetime.datetime.now().year
    all_years = list(range(START_YEAR, current_year + 1))

    rows = []
    for year in all_years:
        print(f'  Fetching {year}...', end=' ', flush=True)
        try:
            df_year = fetch_daily_precip_year(year)
            rows.append(df_year)
            print(f'{len(df_year)} days, avg stations: {df_year["n_stations"].mean():.0f}')
        except Exception as e:
            print(f'FAILED: {e}')

    df = pd.concat(rows, ignore_index=True)

    out_path = '../docs/data/MA_precipitation_daily.csv'
    df.to_csv(out_path, index=False)
    print(f'\nWrote {len(df)} rows to {out_path}')

    with open('../docs/data/ts_update_MA_precipitation.yml', 'w') as f:
        f.write('updated: ' + str(datetime.datetime.now()).split('.')[0] + '\n')


if __name__ == '__main__':
    print(f'Fetching MA daily precipitation {START_YEAR}–present from ACIS...')
    main()
