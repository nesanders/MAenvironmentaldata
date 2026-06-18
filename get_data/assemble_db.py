"""Assemble all downloaded CSVs into a SQLite database and upload it to Google Cloud Storage.

Run this after all data-fetch scripts (get_*.py) have completed successfully.
Typical invocation is via the GitHub Actions workflow, but can also be run locally
from the get_data/ directory.

SSAWages handling: the SSA average wage index file is static and updated manually
(source: https://www.ssa.gov/oact/cola/awidevelop.html).  This script automatically
extends it with placeholder rows (zero growth) for any years that appear in the staff
data but not yet in the SSA CSV, so the database assembles without errors even if the
SSA file lags behind.

Outputs:
  AMEND.db                          — SQLite database (local, then uploaded to GCS)
  gs://openamend-data/amend.db      — GCS copy, served to the web app
  ../docs/assets/db_semantic_context.txt — LLM schema context for the AI Analysis page
"""

import argparse
import pandas as pd
import datetime
from sqlalchemy import create_engine
import os
from generate_semantic_context import generate_semantic_context

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('--no-upload', action='store_true',
	                    help='Skip GCS upload steps (for local testing)')
	args = parser.parse_args()

	## Establish database
	os.system('mv AMEND.db backup_AMEND.db')
	disk_engine = create_engine('sqlite:///AMEND.db')

	## Load datasets
	data_csv = {}
	data_csv['EPARegion1_permits'] = pd.read_csv('../docs/data/EPARegion1_NPDES_permit_data.csv')
	data_csv['MADEP_enforcement'] = pd.read_csv('../docs/data/MADEP_enforcement_actions.csv')
	data_csv['MADEP_staff'] = pd.read_csv('../docs/data/MADEP_staff.csv')
	data_csv['MassBudget_infadjusted'] = pd.read_csv('../docs/data/MassBudget_environmental_infadjusted.csv')
	data_csv['MassBudget_noinfadjusted'] = pd.read_csv('../docs/data/MassBudget_environmental_noinfadjusted.csv')
	data_csv['MassBudget_summary'] = pd.read_csv('../docs/data/MassBudget_environmental_summary.csv')
	data_csv['MADEP_staff_Comptroller'] = pd.read_csv('../docs/data/MADEP_staff_SODA.csv')
	data_csv['Census_ACS'] = pd.read_csv('../docs/data/Census_ACS_MA.csv')
	data_csv['Census_statepop'] = pd.read_csv('../docs/data/Census_statepop.csv')
	data_csv['ECOS_budgets'] = pd.read_csv('../docs/data/ECOS_budget_history.csv')
	data_csv['NECIR_CSO_2011'] = pd.read_csv('../docs/data/NECIR_CSO_2011.csv')

	data_csv['MAEEADP_DrinkingWater'] = pd.read_csv('../docs/data/EEADP_drinkingWater_annual.csv')
	#../docs/data/EEADP_drinkingWater_head.csv ## Don't include Drinking Water head file
	data_csv['MAEEADP_Enforcement'] = pd.read_csv('../docs/data/EEADP_enforcement.csv')
	data_csv['MAEEADP_Facility'] = pd.read_csv('../docs/data/EEADP_facility.csv')
	data_csv['MAEEADP_Inspection'] = pd.read_csv('../docs/data/EEADP_inspection.csv')
	data_csv['MAEEADP_Permit'] = pd.read_csv('../docs/data/EEADP_permit.csv')
	data_csv['EPA_EJSCREEN_2017'] = pd.read_csv('../docs/data/EPA_EJSCREEN_MA_2017.csv')
	data_csv['EPA_EJSCREEN_2023'] = pd.read_csv('../docs/data/EPA_EJSCREEN_MA_2023.csv')
	data_csv['MAEEADP_CSO'] = pd.read_csv('../docs/data/EEADP_CSO.csv')
	## Fill in missing outfall lat/lon from the state permittee-and-outfall list
	## (only ~9% of EEA API records include coordinates; the xlsx has the rest)
	df_outfall_coords = pd.read_excel('../docs/data/ma_permittee-and-outfall-lists.xlsx', 'CSO Outfalls') \
		.set_index('Outfall ID')[['Lat', 'Long']]
	missing_coords = data_csv['MAEEADP_CSO']['latitude'].isnull()
	outfall_ids = data_csv['MAEEADP_CSO'].loc[missing_coords, 'outfallId']
	coords = df_outfall_coords.reindex(outfall_ids)
	data_csv['MAEEADP_CSO'].loc[missing_coords, 'latitude'] = coords['Lat'].values
	data_csv['MAEEADP_CSO'].loc[missing_coords, 'longitude'] = coords['Long'].values
	n_filled = (~data_csv['MAEEADP_CSO']['latitude'].isnull()).sum()
	print(f'MAEEADP_CSO: {n_filled}/{len(data_csv["MAEEADP_CSO"])} rows now have coordinates')
	## Add correctly-spelled alias alongside the source typo; cast Year to INTEGER
	data_csv['MAEEADP_CSO']['volumeOfEvent'] = data_csv['MAEEADP_CSO']['volumnOfEvent']
	data_csv['MAEEADP_CSO']['Year'] = data_csv['MAEEADP_CSO']['Year'].astype('Int64')
	data_csv['MA_precipitation_daily'] = pd.read_csv('../docs/data/MA_precipitation_daily.csv')

	## Load SSAWages (auto-updated via get_SSAWages.py when available).
	## If SSA source is blocked, use cached version; assemble_db will extend with
	## placeholder rows for any years between SSA data and staff data.
	try:
		data_csv['SSAWages'] = pd.read_csv('../docs/data/SSAWages.csv')
	except FileNotFoundError:
		# Fallback to dated version if current version not available
		data_csv['SSAWages'] = pd.read_csv('../docs/data/SSAWages_2023-02-03.csv')
	last_staff_year = int(pd.read_csv('../docs/data/MADEP_staff_SODA.csv')['year'].max())
	last_ssa_year = int(data_csv['SSAWages']['Year'].max())
	for yr in range(last_ssa_year + 1, last_staff_year + 1):
		# Extend with placeholder row (zero growth) for missing years
		new_row = data_csv['SSAWages'].iloc[-1:].copy()
		new_row.iloc[0, 0] = yr  # Update year column
		new_row.iloc[0, 2:] = 0  # Zero-fill growth columns
		data_csv['SSAWages'] = pd.concat([data_csv['SSAWages'], new_row], ignore_index=True)

	## Build waterBody -> watershed lookup table for CSO choropleth mapping.
	## GeoJSON watershed polygon names (short, ALL CAPS) are from docs/assets/ma_watersheds.geojson.
	## Mapping reviewed and approved 2026-04-10.
	_CSO_WATERSHED_MAP = {
		'ABANDONED FALULAH CANAL':                          'NASHUA',
		'ACUSHNET RIVER':                                   'BUZZARDS BAY',
		'ALEWIFE BROOK':                                    'MYSTIC',
		'ASSABET RIVER':                                    'CONCORD',
		'BEAVER BROOK':                                     'MERRIMACK',
		'BIRCH BROOK @ HEYWOOD ST':                         'NASHUA',
		'BLACKSTONE RIVER':                                 'BLACKSTONE',
		'BOSTON INNER HARBOR':                              'MYSTIC',
		'CHARLES RIVER':                                    'CHARLES',
		'CHARLES RIVER BASIN':                              'CHARLES',
		'CHELSEA RIVER':                                    'MYSTIC',
		'CHICOPEE R.':                                      'CHICOPEE',
		'CLARK COVE':                                       'BUZZARDS BAY',
		'CONCORD RIVER':                                    'CONCORD',
		'CONNECTICUT R.':                                   'CONNECTICUT',
		'CONNECTICUT RIVER':                                'CONNECTICUT',
		'DEERFIELD RIVER':                                  'DEERFIELD',
		'DINGLE BK TO CONNECTICUT R.':                      'CONNECTICUT',
		'FORT POINT CHANNEL':                               'CHARLES',
		'FRENCH STREAM':                                    'FRENCH',
		'GREENWOOD CREEK':                                  'IPSWICH',
		'HARBOR COVE':                                      'NORTH COAST',
		'HOUSATONIC RIVER':                                 'HOUSATONIC',
		'INNER HARBOR':                                     'MYSTIC',
		'INNER NEW BEDFORD HARBOR':                         'BUZZARDS BAY',
		'LITTLE MYSTIC CHANNEL':                            'MYSTIC',
		'LITTLE RIVER':                                     'MERRIMACK',
		'LYNN HARBOR':                                      'NORTH COAST',
		'MASSACHUSETTS BAY':                                'NORTH COAST',
		'MERIMACK RIVER':                                   'MERRIMACK',
		'MERRIMACK RIVER':                                  'MERRIMACK',
		'MILL BROOK TO BLACKSTONE RIVER':                   'BLACKSTONE',
		'MILL R.':                                          'CONNECTICUT',
		'MOUNT HOPE BAY':                                   'MT HOPE BAY',
		'MUDDY RIVER':                                      'CHARLES',
		'MYSTIC RIVER':                                     'MYSTIC',
		'NAHANT BAY':                                       'NORTH COAST',
		'NASHUA RIVER':                                     'NASHUA',
		'NORTH NASHUA RIVER':                               'NASHUA',
		'OUTER NEW BEDFORD HARBOR':                         'BUZZARDS BAY',
		'Other':                                            None,
		'POWER CANAL CONNECTICUT RIVER':                    'CONNECTICUT',
		'PUNCH BROOK CULVERT @ BOULDER DRIVE VIA PUTNAM ST.': 'NASHUA',
		'PUNCH BROOK CULVERT @ MAIN ST.':                   'NASHUA',
		'PUNCH BROOK CULVERT@BOULDER ST VIA MAIN ST':       'NASHUA',
		'QUEQUECHAN RIVER':                                 'TAUNTON',
		'QUINEBAUG RIVER':                                  'QUINEBAUG',
		'RESERVED CHANNEL':                                 'MYSTIC',
		'SALEM SOUND':                                      'NORTH COAST',
		'SAUGUS RIVER':                                     'NORTH COAST',
		'SPICKETT HARBOR':                                  'MERRIMACK',
		'TAUNTON RIVER':                                    'TAUNTON',
		'TEN MILE RIVER':                                   'TEN MILE',
		'TIDAL CREEK TO HERRING RIVER':                     'CAPE COD',
		'WARE RIVER':                                       'CHICOPEE',
		'WILLIMANSETT BK':                                  'CHICOPEE',
	}
	data_csv['CSO_WatershedMapping'] = pd.DataFrame(
		list(_CSO_WATERSHED_MAP.items()), columns=['waterBody', 'watershed']
	)

	## Load 303(d) Integrated List of Waters (all available cycles).
	data_csv['EPA_303d_Impairments'] = pd.read_csv('../docs/data/EPA_303d_impairments.csv',
	                                               low_memory=False)

	## Build CSO waterBody -> 303(d) waterbody name mapping.
	## Maps each CSO waterBody (ALL CAPS, from MAEEADP_CSO) to the corresponding
	## waterbody name as it appears in EPA_303d_Impairments.
	## Only manually verified, exact matches are included; ~30 of ~56 CSO waterbodies matched.
	## Unmatched CSO waterbodies are simply absent from this table.
	## Join path: MAEEADP_CSO.waterBody = CSO_303d_Mapping.csoWaterBody
	##   -> CSO_303d_Mapping.waterbody303d = EPA_303d_Impairments.waterbody
	## Note: one 303d waterbody name may correspond to multiple assessment units (AUs).
	## Reviewed and approved 2026-04-12.
	_CSO_303d_MAP = {
		'ACUSHNET RIVER':             'Acushnet River',
		'ALEWIFE BROOK':              'Alewife Brook',
		'ASSABET RIVER':              'Assabet River',
		'BEAVER BROOK':               'Beaver Brook',
		'BLACKSTONE RIVER':           'Blackstone River',
		'BOSTON INNER HARBOR':        'Boston Inner Harbor',
		'CHARLES RIVER':              'Charles River',
		'CHARLES RIVER BASIN':        'Charles River',      # CSO alias for same body
		'CHELSEA RIVER':              'Chelsea River',
		'CHICOPEE R.':                'Chicopee River',
		'CONCORD RIVER':              'Concord River',
		'CONNECTICUT R.':             'Connecticut River',
		'CONNECTICUT RIVER':          'Connecticut River',
		'DEERFIELD RIVER':            'Deerfield River',
		'FRENCH STREAM':              'French Stream',
		'HOUSATONIC RIVER':           'Housatonic River',
		'INNER NEW BEDFORD HARBOR':   'New Bedford Inner Harbor',
		'LITTLE RIVER':               'Little River',
		'LYNN HARBOR':                'Lynn Harbor',
		'MERIMACK RIVER':             'Merrimack River',    # CSO typo for Merrimack
		'MERRIMACK RIVER':            'Merrimack River',
		'MOUNT HOPE BAY':             'Mount Hope Bay',
		'MUDDY RIVER':                'Muddy River',
		'MYSTIC RIVER':               'Mystic River',
		'NAHANT BAY':                 'Nahant Bay',
		'NASHUA RIVER':               'Nashua River',
		'NORTH NASHUA RIVER':         'North Nashua River',
		'OUTER NEW BEDFORD HARBOR':   'Outer New Bedford Harbor',
		'QUEQUECHAN RIVER':           'Quequechan River',
		'QUINEBAUG RIVER':            'Quinebaug River',
		'SALEM SOUND':                'Salem Sound',
		'SAUGUS RIVER':               'Saugus River',
		'TAUNTON RIVER':              'Taunton River',
		'TEN MILE RIVER':             'Ten Mile River',
		'WARE RIVER':                 'Ware River',
		'CLARK COVE':                 'Clarks Cove',            # New Bedford; spelling variant
		'FORT POINT CHANNEL':         'Boston Inner Harbor',    # BWSC tidal inlet to inner harbor
		'MILL R.':                    'Mill River',             # Springfield W&S; Connecticut watershed
		'RESERVED CHANNEL':           'Boston Inner Harbor',    # BWSC South Boston tidal channel
	}
	data_csv['CSO_303d_Mapping'] = pd.DataFrame(
		list(_CSO_303d_MAP.items()), columns=['csoWaterBody', 'waterbody303d']
	)

	## MS4 Annual Reports — flat table + exploded TMDL table
	import json, re as _re

	_ms4_raw = pd.read_csv('../docs/data/MS4_extracted.csv')

	# report_year: fill nulls from filename suffix (e.g. palmer-ma-ar20.pdf -> 2020)
	_YEAR_RE = _re.compile(r'ar(\d{2})\.pdf$', _re.IGNORECASE)
	def _year_from_url(url, existing):
		if pd.notna(existing):
			return existing
		m = _YEAR_RE.search(str(url))
		if m:
			suffix = int(m.group(1))
			return 2000 + suffix if suffix >= 19 else 2100 + suffix
		return existing
	_ms4_raw['report_year'] = _ms4_raw.apply(
		lambda r: _year_from_url(r['source_url'], r['report_year']), axis=1
	)

	# permit_year imputation: report_year -> permit year
	# FY2019–2025 = permit years 1–7 of the original MA MS4 General Permit (first cycle).
	# FY2026 = permit year 1 of the renewed permit (second cycle, effective 2023).
	_REPORT_TO_PERMIT_YEAR = {2019: 1, 2020: 2, 2021: 3, 2022: 4, 2023: 5, 2024: 6, 2025: 7, 2026: 1}
	_ms4_raw['permit_year_imputed'] = _ms4_raw['permit_year'].isna()
	_ms4_raw['permit_year'] = _ms4_raw.apply(
		lambda r: _REPORT_TO_PERMIT_YEAR.get(int(r['report_year']), r['permit_year'])
		          if pd.isna(r['permit_year']) and pd.notna(r['report_year']) else r['permit_year'],
		axis=1
	)

	# Municipality normalization: strip "Town of"/"City of" prefix, uppercase
	def _normalize_muni(name):
		if not isinstance(name, str):
			return None
		name = _re.sub(r'^(Town|City|President and Fellows) of\s+', '', name, flags=_re.IGNORECASE)
		return name.strip().upper()

	_ms4_raw['municipality_normalized'] = _ms4_raw['municipality'].apply(_normalize_muni)

	# Forward-impute mapping completion: cap at historical maximum per municipality.
	# Raw values are non-monotonic because methodology changes (e.g. switching from
	# % pipe-miles to % outfalls) cause spurious drops, not actual unmapping.
	_ms4_raw = _ms4_raw.sort_values(['municipality_normalized', 'report_year'])
	def _running_max_ffill(s):
		# For each row: use running max of all non-null values seen so far.
		# Forward-fills across years where the municipality did not report,
		# so a municipality that reached 100% in 2020 stays at 100% in 2021
		# even if they left the field blank that year.
		result = s.copy()
		running_max = None
		for idx in s.index:
			val = s[idx]
			if pd.notna(val):
				running_max = val if running_max is None else max(running_max, val)
			if running_max is not None:
				result[idx] = running_max
		return result
	_ms4_raw['system_mapping_pct_display'] = (
		_ms4_raw.groupby('municipality_normalized')['system_mapping_pct_complete']
		.transform(_running_max_ffill)
	)

	# Drop the JSON column before loading flat table
	_tmdl_json = _ms4_raw['tmdl_waterbodies_json'].copy()
	data_csv['MS4_AnnualReports'] = _ms4_raw.drop(columns=['tmdl_waterbodies_json'])

	# Explode TMDL waterbodies into one row per (municipality, report_year, waterbody, pollutant)
	_tmdl_rows = []
	for (src_url, muni, muni_norm, yr), tmdl_str in zip(
		_ms4_raw[['source_url', 'municipality', 'municipality_normalized', 'report_year']].itertuples(index=False),
		_tmdl_json
	):
		try:
			entries = json.loads(tmdl_str) if isinstance(tmdl_str, str) else []
		except (json.JSONDecodeError, TypeError):
			entries = []
		for entry in entries:
			_tmdl_rows.append({
				'source_url': src_url,
				'municipality': muni,
				'municipality_normalized': muni_norm,
				'report_year': yr,
				'waterbody': entry.get('waterbody'),
				'pollutant': entry.get('pollutant'),
				'reduction_achieved_lbs_per_year': entry.get('reduction_achieved_lbs_per_year'),
				'wasteload_allocation_lbs_per_year': entry.get('wasteload_allocation_lbs_per_year'),
				'reduction_achieved_pct': entry.get('reduction_achieved_pct'),
				'wasteload_allocation_pct': entry.get('wasteload_allocation_pct'),
				'source_page': entry.get('source_page'),
			})
	_ms4_tmdl = pd.DataFrame(_tmdl_rows)
	# Normalize pollutant names: title-case, strip leading "Total ", fix misspelling
	def _norm_pollutant(p):
		if not isinstance(p, str):
			return p
		p = p.strip().title()
		p = _re.sub(r'^Total\s+', '', p, flags=_re.IGNORECASE)
		p = p.replace('Phosphorous', 'Phosphorus')
		return p
	_ms4_tmdl['pollutant'] = _ms4_tmdl['pollutant'].apply(_norm_pollutant)
	data_csv['MS4_TMDL'] = _ms4_tmdl
	print(f'MS4: {len(data_csv["MS4_AnnualReports"])} reports, {len(data_csv["MS4_TMDL"])} TMDL entries')

	## MA Lobbying and Legislature data (loaded only if available; not yet in CI)

	# Entity name normalization — applied at DB assembly time so raw portal names
	# are preserved in GCS CSVs while the DB exposes cleaned columns for analysis.
	#
	# Design:
	# 1. Strip d/b/a suffix first (before any other transforms) so the trade name
	#    doesn't bleed into the canonical form.
	# 2. Normalize hyphens -> spaces before punctuation removal, so "LAN-TEL" and
	#    "LAN TEL" collapse to the same key.
	# 3. Replace punctuation with a space (not '') so adjacent tokens don't
	#    concatenate (e.g. ",INC" -> " INC" -> caught by whole-word removal).
	# 4. Remove legal entity type words with whole-word regex so "INCORPORATED"
	#    and "CORP" are caught in addition to "LLC"/"INC".
	# 5. Remove "THE" as a whole word anywhere (leading or trailing) rather than
	#    just the prefix "THE ".
	import re as _re
	_ENTITY_DBA_RE = _re.compile(
		r'\s+D\s*/+B\s*/+A?\s+.*|\s+DBA\s+.*', _re.IGNORECASE)
	_ENTITY_LEGAL_RE = _re.compile(
		r'\b(LLC|LLP|INC|INCORPORATED|CORPORATION|CORP|LTD|LIMITED|PC|PLLC)\b')
	_ENTITY_ARTICLE_RE = _re.compile(r'\bTHE\b')
	_ENTITY_MISC = [
		'LAW OFFICE OF', 'AND ASSOCIATES', '& ASSOCIATES', 'AND ASSOC',
		'ATTORNEY AT LAW', 'ATTORNEY@LAW', 'ATTORNET AT LAW', 'AND PARTNERS',
		'PUBLIC POLICY GROUP', 'LEGISLATIVE SERVICES', 'POLICY GROUP',
		'ASSOCIATES', 'COUNSELLORS AT LAW',
	]

	def _normalize_entity(x):
		if not isinstance(x, str):
			return x
		x = x.upper()
		x = _ENTITY_DBA_RE.sub('', x)             # strip d/b/a trade-name suffix
		x = x.replace('-', ' ')                    # hyphen -> space
		for ch in (',', '.', "'", '\u2018', '\u2019', '(', ')'):
			x = x.replace(ch, ' ')                # punctuation -> space (not '')
		x = _ENTITY_LEGAL_RE.sub(' ', x)           # remove entity-type words
		x = _ENTITY_ARTICLE_RE.sub(' ', x)         # remove THE (anywhere)
		x = x.replace('&', 'AND')
		x = x.replace('ASSICIATES', 'ASSOCIATES')  # legacy typo fix
		for token in _ENTITY_MISC:
			x = x.replace(token, ' ')
		x = _re.sub(r'\s+', ' ', x).strip()
		return x

	_lobbying_employers_path = '../docs/data/MA_lobbying_employers.csv'
	_lobbying_lobbyists_path = '../docs/data/MA_lobbying_lobbyists.csv'
	_lobbying_bills_path = '../docs/data/MA_lobbying_bills.csv'
	_legislature_bills_path = '../docs/data/MA_legislature_bills.csv'
	# New fields from the raw-HTML archive (reparse_lobbying_archive.py)
	_lobbying_campaign_path = '../docs/data/MA_lobbying_campaign_contributions.csv'
	_lobbying_expenses_path = '../docs/data/MA_lobbying_expenses.csv'
	_lobbying_purposes_path = '../docs/data/MA_lobbying_client_purposes.csv'

	if os.path.exists(_lobbying_employers_path):
		# Compensation metric (how to total "lobbying spend"):
		# Total spend = SUM of `compensation` across ALL rows (both reg_types,
		# 'Lobbyist Entity' and 'Lobbyist'). Do NOT deduplicate and do NOT drop
		# either reg_type. Per the MA Secretary of the Commonwealth's filing rule,
		# each client payment is reported exactly once — by the entity OR by the
		# individual lobbyist, never both:
		#
		#   "Compensation paid by the client should be reported either as an amount
		#    received by the lobbyist entity, or as an amount received by the
		#    individual lobbyist. The same payment should not be reported in both
		#    sections."
		#   — MA SoC, Lobbyist Registration & Reporting System, Entity Disclosure
		#     Reporting User Guide, Form 2 (Activities and Bill Numbers), p.8, Dec 2021:
		#     https://www.sec.state.ma.us/lobbyistweb/readme/OnlineHelp/2010/08_DiscEntityDec2020.pdf
		#     (overview: https://www.sec.state.ma.us/divisions/lobbyist/lobbyist.htm ;
		#      statute M.G.L. c.3 ss.39-50: https://www.sec.state.ma.us/lobbyistweb/ReadMe/MALobbyingLaw.pdf )
		#
		# So the data is already deduplicated by filers; summing all rows is correct.
		# We verified empirically (June 2026, full 2005-2025 corpus): of the rare
		# cases where an entity AND one of its own lobbyists report the same client
		# in the same year, only 15 rows / ~$0.3M (0.03%) have MATCHING amounts (a
		# possible same-payment double-report); 61 rows / ~$9.0M have DIFFERENT
		# amounts, i.e. legitimately distinct payments for the same client (which the
		# rule explicitly permits). Subtracting them would erase real money, so we do
		# not. The reg_type column is retained for breakdowns, not for filtering totals.
		# NOTE: chamber='Executive' / agency-name rows in MA_Lobbying_Bills are
		# executive/regulatory lobbying, not legislative bills — count distinct bill_id
		# for "bills lobbied", not raw activity rows.
		_emp = pd.read_csv(_lobbying_employers_path, index_col=0)
		_emp['entity_name_norm'] = _emp['entity_name'].map(_normalize_entity)
		_emp['client_name_norm'] = _emp['client_name'].map(_normalize_entity)
		data_csv['MA_Lobbying_Employers'] = _emp
		print(f"MA_Lobbying_Employers: {len(data_csv['MA_Lobbying_Employers'])} rows")
	if os.path.exists(_lobbying_lobbyists_path):
		# Lobbyist <-> employing-entity mapping + salary (from summary pages).
		_lobby = pd.read_csv(_lobbying_lobbyists_path, index_col=0)
		if 'entity_name' in _lobby.columns:
			_lobby['entity_name_norm'] = _lobby['entity_name'].map(_normalize_entity)
		data_csv['MA_Lobbying_Lobbyists'] = _lobby
		print(f"MA_Lobbying_Lobbyists: {len(data_csv['MA_Lobbying_Lobbyists'])} rows")
	if os.path.exists(_lobbying_campaign_path):
		# Lobbyist -> political recipient contributions (date, recipient, office, amount).
		_cc = pd.read_csv(_lobbying_campaign_path, index_col=0)
		if 'entity_name' in _cc.columns:
			_cc['entity_name_norm'] = _cc['entity_name'].map(_normalize_entity)
		data_csv['MA_Lobbying_CampaignContributions'] = _cc
		print(f"MA_Lobbying_CampaignContributions: {len(data_csv['MA_Lobbying_CampaignContributions'])} rows")
	if os.path.exists(_lobbying_expenses_path):
		# Itemized operating / meals-entertainment-travel / additional expenses.
		_ex = pd.read_csv(_lobbying_expenses_path, index_col=0)
		if 'entity_name' in _ex.columns:
			_ex['entity_name_norm'] = _ex['entity_name'].map(_normalize_entity)
		data_csv['MA_Lobbying_Expenses'] = _ex
		print(f"MA_Lobbying_Expenses: {len(data_csv['MA_Lobbying_Expenses'])} rows")
	if os.path.exists(_lobbying_purposes_path):
		# Per-client annual amount + free-text purpose-of-employment description.
		_cp = pd.read_csv(_lobbying_purposes_path, index_col=0, engine='python')
		for _c in ('entity_name', 'client_name'):
			if _c in _cp.columns:
				_cp[f'{_c}_norm'] = _cp[_c].map(_normalize_entity)
		data_csv['MA_Lobbying_ClientPurposes'] = _cp
		print(f"MA_Lobbying_ClientPurposes: {len(data_csv['MA_Lobbying_ClientPurposes'])} rows")
	if os.path.exists(_lobbying_bills_path):
		_lb = pd.read_csv(_lobbying_bills_path, index_col=0, low_memory=False)
		_lb['entity_name_norm'] = _lb['entity_name'].map(_normalize_entity)
		_lb['client_name_norm'] = _lb['client_name'].map(_normalize_entity)
		_lb['bill_number'] = pd.to_numeric(_lb['bill_number'], errors='coerce').astype('Int64')
		if 'general_court' in _lb.columns:
			_lb['general_court'] = pd.to_numeric(_lb['general_court'], errors='coerce').astype('Int64')
		# Deduplicate: null-bill rows ("no specific bills") are sometimes scraped
		# multiple times from the SoS portal across filing periods.  Drop exact
		# duplicates on the logical key; keep the row with the highest amount so
		# no spend is lost when two copies carry different values.
		_lb_key = ['entity_name', 'client_name', 'year', 'general_court',
		           'bill_number', 'position']
		_lb_before = len(_lb)
		_lb = (_lb.sort_values('amount', ascending=False, na_position='last')
		          .drop_duplicates(subset=_lb_key, keep='first')
		          .reset_index(drop=True))
		if len(_lb) < _lb_before:
			print(f"  Deduplicated MA_Lobbying_Bills: {_lb_before} -> {len(_lb)} rows "
			      f"({_lb_before - len(_lb)} duplicates removed)")
		# Derive bill_prefix and bill_id from chamber + bill_number so downstream
		# SQL can join to MA_Lobbying_Bills_Scored on (bill_id, general_court)
		# instead of the ambiguous (bill_number, general_court) which collapses
		# distinct H and S bills that share the same integer.
		_chamber_to_prefix = {
			'House Bill': 'H', 'HB': 'H',
			'Senate Bill': 'S', 'SB': 'S',
			'House Docket': 'HD',
			'Senate Docket': 'SD',
		}
		_lb['bill_prefix'] = _lb['chamber'].map(_chamber_to_prefix)
		_lb['bill_id'] = _lb.apply(
			lambda r: f"{r['bill_prefix']}{int(r['bill_number'])}"
			          if pd.notna(r.get('bill_prefix')) and pd.notna(r.get('bill_number'))
			          else None,
			axis=1,
		)
		data_csv['MA_Lobbying_Bills'] = _lb
		print(f"MA_Lobbying_Bills: {len(data_csv['MA_Lobbying_Bills'])} rows")
	if os.path.exists(_legislature_bills_path):
		_leg_bills = pd.read_csv(_legislature_bills_path, index_col=0)
		_leg_bills['bill_number'] = pd.to_numeric(_leg_bills['bill_number'], errors='coerce').astype('Int64')
		if 'general_court' in _leg_bills.columns:
			_leg_bills['general_court'] = pd.to_numeric(_leg_bills['general_court'], errors='coerce').astype('Int64')
		if 'passed' in _leg_bills.columns:
			_leg_bills['passed'] = _leg_bills['passed'].astype('Int64')
		data_csv['MA_Legislature_Bills'] = _leg_bills
		print(f"MA_Legislature_Bills: {len(data_csv['MA_Legislature_Bills'])} rows")

	_scored_bills_path = '../docs/data/MA_lobbying_bills_scored.csv'
	if os.path.exists(_scored_bills_path):
		_scored = pd.read_csv(_scored_bills_path, index_col=0, engine='python')
		_scored['bill_number'] = pd.to_numeric(_scored['bill_number'], errors='coerce').astype('Int64')
		if 'general_court' in _scored.columns:
			_gc = pd.to_numeric(_scored['general_court'], errors='coerce')
			# Clamp out-of-range values (e.g. similarity scores in malformed rows) to NaN
			_gc = _gc.where((_gc >= 180) & (_gc <= 210))
			_scored['general_court'] = _gc.astype('Int64')
		if 'is_environmental' in _scored.columns:
			_scored['is_environmental'] = pd.to_numeric(_scored['is_environmental'].map(
			{'True': 1, 'False': 0, True: 1, False: 0}).fillna(_scored['is_environmental']),
			errors='coerce').astype('Int64')
		if 'cluster_id' in _scored.columns:
			_scored['cluster_id'] = pd.to_numeric(_scored['cluster_id'], errors='coerce').astype('Int64')
		# Deduplicate: multiple filers sometimes reference the same bill with
		# slightly different bill_title strings, producing duplicate scored rows.
		# Deduplicate on (bill_id, general_court) when bill_id is present — this
		# preserves distinct H and S bills that share the same integer bill_number
		# (e.g. H331 and S331 in GC188 are completely different bills).  For rows
		# without a bill_id (legacy SoS data pre-~2013), fall back to deduplicating
		# on (bill_number, general_court) within that subset only.
		# Sort so the row with the highest env_relevance_score is kept; prefer rows
		# with a valid bill_id as a secondary sort within each group.
		_scored_before = len(_scored)
		_scored = _scored.assign(_has_bill_id=_scored['bill_id'].notna().astype(int))
		_scored = _scored.sort_values(['env_relevance_score', '_has_bill_id'],
		                              ascending=[False, False], na_position='last')
		# Rows that have a bill_id: deduplicate on (bill_id, general_court)
		_has_id = _scored['bill_id'].notna()
		_scored_with_id = (_scored[_has_id]
		                   .drop_duplicates(subset=['bill_id', 'general_court'], keep='first'))
		# Rows without a bill_id: deduplicate on (bill_number, general_court)
		_scored_no_id = (_scored[~_has_id]
		                 .drop_duplicates(subset=['bill_number', 'general_court'], keep='first'))
		_scored = (pd.concat([_scored_with_id, _scored_no_id], ignore_index=True)
		             .drop(columns=['_has_bill_id'])
		             .reset_index(drop=True))
		if len(_scored) < _scored_before:
			print(f"  Deduplicated MA_Lobbying_Bills_Scored: {_scored_before} -> {len(_scored)} rows "
			      f"({_scored_before - len(_scored)} duplicates removed)")
		# Replace concatenated multi-bill title blobs with the authoritative title
		# from MA_Legislature_Bills wherever the join on (bill_id, general_court)
		# succeeds.  The SoS portal sometimes stores all bills a filer registered
		# in one text block; the Legislature API always has a clean single title.
		if 'MA_Legislature_Bills' in data_csv and 'bill_id' in _scored.columns:
			_leg_titles = (data_csv['MA_Legislature_Bills']
			               [['bill_id', 'general_court', 'title']]
			               .dropna(subset=['bill_id', 'title'])
			               .drop_duplicates(subset=['bill_id', 'general_court']))
			_leg_titles = _leg_titles.rename(columns={'title': '_leg_title'})
			_scored = _scored.merge(_leg_titles, on=['bill_id', 'general_court'], how='left')
			_long_mask = _scored['bill_title'].str.len().fillna(0) > 300
			_fixed = (_long_mask & _scored['_leg_title'].notna()).sum()
			_scored.loc[_long_mask & _scored['_leg_title'].notna(), 'bill_title'] = \
				_scored.loc[_long_mask & _scored['_leg_title'].notna(), '_leg_title']
			_scored = _scored.drop(columns=['_leg_title'])
			if _fixed:
				print(f"  Replaced {_fixed} concatenated bill titles with Legislature API titles")
		data_csv['MA_Lobbying_Bills_Scored'] = _scored
		print(f"MA_Lobbying_Bills_Scored: {len(data_csv['MA_Lobbying_Bills_Scored'])} rows")

	_cluster_labels_path = '../docs/data/MA_bill_cluster_labels.csv'
	if os.path.exists(_cluster_labels_path):
		data_csv['MA_Bill_Cluster_Labels'] = pd.read_csv(_cluster_labels_path, engine='python')
		print(f"MA_Bill_Cluster_Labels: {len(data_csv['MA_Bill_Cluster_Labels'])} rows")

	data_csv['AMEND_metadata'] = pd.Series({
		'Website':'https://nesanders.github.io/MAenvironmentaldata/index.html',
		'GitHub':'https://github.com/nesanders/MAenvironmentaldata',
		'db_generated':datetime.datetime.now(),
		})

	for key in data_csv:
		print(f'Writing database table {key}')
		data_csv[key].to_sql(name=key, con=disk_engine, if_exists='append')

	if not args.no_upload:
		# Upload uncompressed DB (for CI scripts and assemble_db.py compatibility)
		os.system('gsutil cp AMEND.db gs://openamend-data/amend.db')

		# Upload gzip-compressed DB for browser delivery (~26 MB vs ~85 MB = ~70% egress savings).
		# Cache-Control: no-transform prevents GCS decompressive transcoding so browsers
		# receive the compressed bytes (and auto-decompress via Content-Encoding: gzip).
		print('Compressing AMEND.db for browser delivery...')
		os.system('gzip -c AMEND.db > amend.db.gz')
		os.system(
			'gsutil '
			'-h "Content-Encoding:gzip" '
			'-h "Content-Type:application/octet-stream" '
			'-h "Cache-Control:no-transform,public,max-age=86400" '
			'cp amend.db.gz gs://openamend-data/amend.db.gz'
		)
		os.system('rm amend.db.gz')
		print('Compressed DB uploaded to gs://openamend-data/amend.db.gz')

		# Upload large lobbying CSVs to GCS (excluded from git due to size)
		_gcs_lobbying_files = [
			'../docs/data/MA_lobbying_bills.csv',
			'../docs/data/MA_lobbying_employers.csv',
			'../docs/data/MA_lobbying_bills_scored.csv',
			'../docs/data/MA_legislature_bills.csv',
		]
		for _f in _gcs_lobbying_files:
			if os.path.exists(_f):
				_gcs_name = os.path.basename(_f)
				os.system(f'gsutil cp {_f} gs://openamend-data/{_gcs_name}')
				print(f'Uploaded {_gcs_name} to GCS')

	## Write sample CSVs for large lobbying files (full CSVs are in GCS, not git)
	_lobbying_samples = {
		'MA_lobbying_bills':        (data_csv['MA_Lobbying_Bills'],         True),
		'MA_lobbying_employers':    (data_csv['MA_Lobbying_Employers'],      True),
		'MA_lobbying_summary_links': (pd.read_csv('../docs/data/MA_lobbying_summary_links.csv') if os.path.exists('../docs/data/MA_lobbying_summary_links.csv') else pd.DataFrame(), False),
		'MA_lobbying_bills_scored': (data_csv['MA_Lobbying_Bills_Scored'],   True),
		'MA_legislature_bills':     (data_csv['MA_Legislature_Bills'],       True),
	}
	# New archive-derived tables (full CSVs gitignored; commit samples for schema/preview)
	for _key, _tbl in (
		('MA_lobbying_lobbyists',              'MA_Lobbying_Lobbyists'),
		('MA_lobbying_campaign_contributions', 'MA_Lobbying_CampaignContributions'),
		('MA_lobbying_expenses',               'MA_Lobbying_Expenses'),
		('MA_lobbying_client_purposes',        'MA_Lobbying_ClientPurposes'),
	):
		if _tbl in data_csv:
			_lobbying_samples[_key] = (data_csv[_tbl], True)
	for fname, (df, has_index) in _lobbying_samples.items():
		if df.empty:
			continue
		out = f'../docs/data/{fname}_sample.csv'
		df.head(100).to_csv(out, index=has_index)
		print(f'Wrote sample: {out}')

	## Generate semantic context for AI Analysis page
	print('Generating semantic context for AI Analysis...')
	semantic_context = generate_semantic_context('AMEND.db')
	with open('../docs/assets/db_semantic_context.txt', 'w') as f:
		f.write(semantic_context)
	print('Semantic context written to docs/assets/db_semantic_context.txt')
