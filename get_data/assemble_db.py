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

import pandas as pd
import datetime
from sqlalchemy import create_engine
import os
from generate_semantic_context import generate_semantic_context

if __name__ == '__main__':
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

	data_csv['AMEND_metadata'] = pd.Series({
		'Website':'https://nesanders.github.io/MAenvironmentaldata/index.html',
		'GitHub':'https://github.com/nesanders/MAenvironmentaldata',
		'db_generated':datetime.datetime.now(),
		})

	for key in data_csv:
		print(f'Writing database table {key}')
		data_csv[key].to_sql(name=key, con=disk_engine, if_exists='append')

	os.system('gsutil cp AMEND.db gs://openamend-data/amend.db')

	## Generate semantic context for AI Analysis page
	print('Generating semantic context for AI Analysis...')
	semantic_context = generate_semantic_context('AMEND.db')
	with open('../docs/assets/db_semantic_context.txt', 'w') as f:
		f.write(semantic_context)
	print('Semantic context written to docs/assets/db_semantic_context.txt')
