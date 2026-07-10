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
    edate = min(
        datetime.date(year, 12, 31),
        datetime.date.today(),
    ).strftime('%Y-%m-%d')
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
    columns = {}

    for stn in stations:
        name = stn['meta']['name']
        rows = stn['data']
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
        # Align to the full date range regardless of how many rows ACIS returned.
        # A station with a partial response (e.g. 364 of 365 days) contributes its
        # valid days rather than being dropped entirely.
        stn_index = pd.date_range(sdate, periods=len(vals), freq='D')
        stn_series = pd.Series(vals, index=stn_index).reindex(dates)
        columns[name] = stn_series.values

    matrix = pd.DataFrame(columns, index=dates, dtype=float)

    result = pd.DataFrame({
        'date': dates.strftime('%Y-%m-%d'),
        'precip_in_avg': matrix.mean(axis=1).values,
        'n_stations': matrix.notna().sum(axis=1).values,
    })
    return result


def main():
    current_year = datetime.datetime.now().year
    out_path = '../docs/data/MA_precipitation_daily.csv'

    # Load cached data to determine the earliest year that needs re-fetching.
    # We always re-fetch the most recently cached year because it may be incomplete
    # (partial calendar year at the time of the previous run).
    try:
        existing = pd.read_csv(out_path)
        existing['date'] = pd.to_datetime(existing['date'])
        max_cached_year = existing['date'].dt.year.max()
        fetch_from_year = max_cached_year  # re-fetch last year in case it was partial
        print(f'  Found cached data through {max_cached_year}; fetching {fetch_from_year}–{current_year}')
    except FileNotFoundError:
        existing = None
        fetch_from_year = START_YEAR
        print(f'  No cache found; fetching {START_YEAR}–{current_year}')

    fetch_years = list(range(fetch_from_year, current_year + 1))

    rows = []
    for year in fetch_years:
        print(f'  Fetching {year}...', end=' ', flush=True)
        try:
            df_year = fetch_daily_precip_year(year)
            rows.append(df_year)
            print(f'{len(df_year)} days, avg stations: {df_year["n_stations"].mean():.0f}')
        except Exception as e:
            print(f'FAILED: {e}')

    new_data = pd.concat(rows, ignore_index=True)

    if existing is not None:
        # Drop cached rows for years being re-fetched, then append fresh data.
        retained = existing[existing['date'].dt.year < fetch_from_year].copy()
        retained['date'] = retained['date'].dt.strftime('%Y-%m-%d')
        df = pd.concat([retained, new_data], ignore_index=True)
    else:
        df = new_data

    # Never persist days with zero reporting stations. Such rows carry no signal
    # (precip_in_avg is NaN) and are almost always trailing/future placeholders
    # left over from an earlier full-calendar-year fetch (e.g. a run that wrote
    # Jan 1–Dec 31 and padded every day after the last real observation with
    # n_stations=0). Dropping them keeps the row count monotonic across weekly
    # runs and prevents the validate_data row-count regression that this causes.
    before = len(df)
    df = df[df['n_stations'] > 0].copy()
    if len(df) < before:
        print(f'  Dropped {before - len(df)} empty (0-station) day rows')

    df.to_csv(out_path, index=False)
    print(f'\nWrote {len(df)} rows to {out_path} ({len(new_data)} newly fetched)')

    with open('../docs/data/ts_update_MA_precipitation.yml', 'w') as f:
        f.write('updated: ' + str(datetime.datetime.now()).split('.')[0] + '\n')


if __name__ == '__main__':
    print(f'Fetching MA daily precipitation {START_YEAR}–present from ACIS...')
    main()
