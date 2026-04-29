"""Query the MA EEA Enterprise Data Portal for permit, facility, inspection, enforcement,
and drinking-water records.

Portal home: http://eeaonline.eea.state.ma.us/portal#!/home

Queries five tables via the DataLake REST API using paginated GET requests.  Results are
written to CSV files under docs/data/.  The large drinkingWater table (>200 MB) is also
uploaded to GCS; an annualized summary is kept locally.

HTTP requests use a session with automatic retries (5 attempts, exponential backoff) to
tolerate transient 5xx / 429 errors from the portal.  Note: 500 is excluded from the
retry list because the API returns 500 to signal "no records match filter" rather than
as a genuine server error — retrying would just waste time.

CSO data is handled separately in get_eea_dp_cso.py because it uses a different API.

Incremental fetching
--------------------
Three tables support date-range filtering via query parameters discovered in April 2026:
  - drinkingWater:  FromCollectedDate=YYYY-MM-DD  (date col: CollectedDate)
  - inspection:     FromInspectionDate=YYYY-MM-DD (date col: InspectionDate)
  - enforcement:    FromEnforcementDate=YYYY-MM-DD (date col: EnforcementDate)

For these tables we load the existing local CSV (or GCS copy for drinkingWater), find
the max date, and fetch only records from that date onward (inclusive, to catch records
submitted after the previous pull).  Rows on the boundary date are dropped from the
cache before merging to avoid duplicates.  A full fetch is used when no cache exists.

The API returns HTTP 500 instead of an empty list when a date filter matches zero records.
We treat a non-OK response on the initial TotalCount request as "no new records" and
fall back to the existing cache unchanged.

permit and facility have no discovered date filter and are always fetched in full.

drinkingWater GCS flow
----------------------
Because the full drinkingWater CSV lives only in GCS (too large to commit), the incremental
flow is: gsutil cp (download) → append new rows → gsutil cp (re-upload).  If the download
fails (first run or GCS unavailable), we fall back to a full API fetch.

Outputs (per table, e.g. 'permit'):
  ../docs/data/EEADP_permit.csv         — full table
  ../docs/data/EEADP_permit_sample.csv  — 10-row sample
  gs://openamend-data/EEADP_drinkingWater.csv — full drinking water table (GCS only)
  ../docs/data/EEADP_drinkingWater_annual.csv — annualized summary
  ../docs/data/ts_update_EEADP.yml      — timestamp of last run
"""

import os
import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd
import numpy as np

##########################
## API parameters
##########################

API_ROOT = 'http://eeaonline.eea.state.ma.us/EEA/DataLake/V1.0/DataLakeAPI/'
API_TABLES = ['permit', 'facility', 'inspection', 'enforcement', 'drinkingWater']

# Tables with date-filter support: {table: (filter_param, date_col_in_csv)}
INCREMENTAL_TABLES = {
	'inspection':   ('FromInspectionDate',  'InspectionDate'),
	'enforcement':  ('FromEnforcementDate', 'EnforcementDate'),
	'drinkingWater': ('FromCollectedDate',  'CollectedDate'),
}

##########################
## Function definitions
##########################

REQ_HEADER = {
	'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36',
	'Referer': 'https://eeaonline.eea.state.ma.us/Portal/',
}

def _make_session() -> requests.Session:
	"""Return a requests Session with automatic retries on transient errors.

	500 is intentionally excluded from status_forcelist: this API returns 500
	to mean "no records match filter", so retrying wastes time.
	"""
	session = requests.Session()
	retry = Retry(
		total=5,
		backoff_factor=2,
		status_forcelist=[429, 502, 503, 504],
	)
	session.mount('http://', HTTPAdapter(max_retries=retry))
	session.mount('https://', HTTPAdapter(max_retries=retry))
	return session


def _get_max_date(csv_path: str, date_col: str) -> str | None:
	"""Return the max date in date_col of csv_path as YYYY-MM-DD, or None."""
	try:
		df = pd.read_csv(csv_path, usecols=[date_col])
		max_val = pd.to_datetime(df[date_col], errors='coerce').max()
		if pd.isna(max_val):
			return None
		return max_val.strftime('%Y-%m-%d')
	except (FileNotFoundError, ValueError, KeyError):
		return None


def query_iterate(table_name: str, req_size: int = 100000, verbose: bool = True,
				  filter_param: str | None = None, filter_val: str | None = None) -> pd.DataFrame:
	"""Query the EEA DataLake API, returning the full (or date-filtered) table.

	Args:
		table_name:   DataLake table name (e.g. 'drinkingWater')
		req_size:     Rows per paginated request
		verbose:      Print progress
		filter_param: Optional date-filter query param name (e.g. 'FromCollectedDate')
		filter_val:   Optional date-filter value in YYYY-MM-DD format

	Returns:
		DataFrame of matching rows, or empty DataFrame when filter matches nothing.
	"""
	session = _make_session()

	filter_qs = f'&{filter_param}={filter_val}' if filter_param and filter_val else ''
	mode = f'filtered {filter_param}={filter_val}' if filter_qs else 'full'
	print(f'{table_name}: {mode} fetch')

	# Get total row count (with filter applied).
	size_url = API_ROOT + table_name + '?_end=1&_start=0' + filter_qs
	r = session.get(size_url, headers=REQ_HEADER, timeout=120)
	if not r.ok or 'TotalCount' not in r.json():
		# API returns 500 with no 'TotalCount' when filter matches zero records.
		print(f'  {table_name}: no records match filter (HTTP {r.status_code}); returning empty')
		return pd.DataFrame()

	table_size = r.json()['TotalCount']
	if table_size == 0:
		return pd.DataFrame()
	print(f'  {table_name}: {table_size:,} rows to fetch')

	if table_size < req_size:
		req_bins = [0, table_size]
	else:
		req_bins = list(np.arange(0, table_size + req_size, req_size))

	dfs = []
	for i in range(len(req_bins) - 1):
		if verbose:
			print(f'{table_name}: request {i + 1} of {len(req_bins) - 1}')
		url = (API_ROOT + table_name
			   + f'?_end={req_bins[i+1]}&_start={req_bins[i]}' + filter_qs)
		r = session.get(url, headers=REQ_HEADER, timeout=180)
		r.raise_for_status()
		dfs.append(pd.DataFrame(r.json()['Items']))

	return pd.concat(dfs, ignore_index=True)


def fetch_incremental(table_name: str, csv_path: str, filter_param: str,
					  date_col: str) -> tuple[pd.DataFrame, bool]:
	"""Load cached CSV and fetch only records newer than the max cached date.

	Returns (dataframe, is_incremental).  is_incremental=False means we fell
	back to a full fetch because no cache was available.
	"""
	max_date = _get_max_date(csv_path, date_col)
	if max_date is None:
		print(f'  {table_name}: no cache found; running full fetch')
		return query_iterate(table_name), False

	print(f'  {table_name}: cache through {max_date}; fetching from {max_date} (inclusive)')
	new_data = query_iterate(table_name, filter_param=filter_param, filter_val=max_date)

	existing = pd.read_csv(csv_path)
	# Drop boundary-date rows from cache — they're included in the fresh fetch.
	existing[date_col] = pd.to_datetime(existing[date_col], errors='coerce')
	cutoff = pd.to_datetime(max_date).date()
	existing = existing[existing[date_col].dt.date < cutoff]

	if new_data.empty:
		print(f'  {table_name}: no new records; using cache as-is')
		return pd.read_csv(csv_path), True

	combined = pd.concat([existing, new_data], ignore_index=True)
	print(f'  {table_name}: appended {len(new_data):,} new rows (total {len(combined):,})')
	return combined, True


def main():
	"""Query for data, persist it, and report the update."""

	table_data = {}

	# --- permit and facility: always full fetch (no date filter available) ---
	for tab in ['permit', 'facility']:
		table_data[tab] = query_iterate(tab)

	# --- inspection and enforcement: incremental via date filter ---
	for tab in ['inspection', 'enforcement']:
		filter_param, date_col = INCREMENTAL_TABLES[tab]
		csv_path = f'../docs/data/EEADP_{tab}.csv'
		table_data[tab], _ = fetch_incremental(tab, csv_path, filter_param, date_col)

	# --- drinkingWater: incremental via GCS cache + date filter ---
	filter_param, date_col = INCREMENTAL_TABLES['drinkingWater']
	dw_local = 'EEADP_drinkingWater.csv'
	gcs_path = f'gs://openamend-data/{dw_local}'

	print('drinkingWater: downloading existing data from GCS...')
	gcs_rc = os.system(f'gsutil cp {gcs_path} {dw_local}')
	if gcs_rc == 0 and os.path.exists(dw_local):
		table_data['drinkingWater'], _ = fetch_incremental(
			'drinkingWater', dw_local, filter_param, date_col)
	else:
		print('  drinkingWater: GCS download failed; running full fetch')
		table_data['drinkingWater'] = query_iterate('drinkingWater')

	# --- Write outputs ---
	for tab in API_TABLES:
		df = table_data[tab]
		df.sample(n=min(10, len(df))).to_csv(f'../docs/data/EEADP_{tab}_sample.csv', index=False)

		if tab != 'drinkingWater':
			df.to_csv(f'../docs/data/EEADP_{tab}.csv', index=False)
		else:
			df.to_csv(dw_local, encoding='utf-8', index=False)
			os.system(f'gsutil cp {dw_local} {gcs_path}')

			# Annualized summary
			df['CollectedDate'] = pd.to_datetime(df['CollectedDate'], errors='coerce')
			df['Year'] = df['CollectedDate'].dt.year
			df_annual = df.groupby(['Year', 'PWSName', 'ContaminantGroup', 'RaworFinished']).agg(
				{'Result': pd.Series.count})
			df_annual.to_csv('../docs/data/EEADP_drinkingWater_annual.csv', index=True)
			df_annual.sample(n=min(10, len(df_annual))).to_csv(
				'../docs/data/EEADP_drinkingWater_annual_sample.csv', index=True)

	# Archive PDF help files
	os.system('wget http://eeaonline.eea.state.ma.us/Portal/documents/General%20Query%20Search%20FAQs.pdf')
	os.system('mv "General Query Search FAQs.pdf" ../docs/assets/PDFs/EEADP_FAQ.pdf')
	os.system('wget http://eeaonline.eea.state.ma.us/Portal/documents/Terms%20and%20Definitions%20for%20EEA.pdf')
	os.system('mv "Terms and Definitions for EEA.pdf" ../docs/assets/PDFs/EEADP_Definitions.pdf')

	with open('../docs/data/ts_update_EEADP.yml', 'w') as f:
		f.write('updated: ' + str(datetime.datetime.now()).split('.')[0] + '\n')


if __name__ == '__main__':
	main()
