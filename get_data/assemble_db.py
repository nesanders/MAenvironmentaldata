"""This script is meant to be run after all relevant data has been downloaded locally with
the various get*.py scripts, and then assembles that data into a SQlite database and
persists it to Google Cloud.
"""

import pandas as pd
import datetime
from sqlalchemy import create_engine
import os

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

	## Temporary insertion for 2022 assuming no inflation
	data_csv['SSAWages'] = pd.read_csv('../docs/data/SSAWages_2023-02-03.csv')
	for yr in [2022]:
		data_csv['SSAWages'] = data_csv['SSAWages']._append(data_csv['SSAWages'].iloc[-1])
		data_csv['SSAWages'].iloc[-1, 0] = yr
		data_csv['SSAWages'].iloc[-1, 2:] = 0

	data_csv['AMEND_metadata'] = pd.Series({
		'Website':'https://nesanders.github.io/MAenvironmentaldata/index.html',
		'GitHub':'https://github.com/nesanders/MAenvironmentaldata',
		'db_generated':datetime.datetime.now(),
		})

	for key in data_csv:
		print(f'Writing database table {key}')
		data_csv[key].to_sql(name=key, con=disk_engine, if_exists='append')

	os.system('gsutil cp AMEND.db gs://ns697-amend/amend.db')
