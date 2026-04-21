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

	## Build waterBody → watershed lookup table for CSO choropleth mapping.
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

	## Build CSO waterBody → 303(d) waterbody name mapping.
	## Maps each CSO waterBody (ALL CAPS, from MAEEADP_CSO) to the corresponding
	## waterbody name as it appears in EPA_303d_Impairments.
	## Only manually verified, exact matches are included; ~30 of ~56 CSO waterbodies matched.
	## Unmatched CSO waterbodies are simply absent from this table.
	## Join path: MAEEADP_CSO.waterBody = CSO_303d_Mapping.csoWaterBody
	##   → CSO_303d_Mapping.waterbody303d = EPA_303d_Impairments.waterbody
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

	## Generate semantic context for AI Analysis page
	print('Generating semantic context for AI Analysis...')
	semantic_context = generate_semantic_context('AMEND.db')
	with open('../docs/assets/db_semantic_context.txt', 'w') as f:
		f.write(semantic_context)
	print('Semantic context written to docs/assets/db_semantic_context.txt')
