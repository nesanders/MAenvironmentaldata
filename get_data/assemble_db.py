import pandas as pd
import datetime
from sqlalchemy import create_engine
import os

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

## Temporary insertion for 2016 assuming no inflation
data_csv['SSAWages'] = pd.read_csv('../docs/data/SSAWages_2016-12-09.csv')
data_csv['SSAWages'] = data_csv['SSAWages'].append(data_csv['SSAWages'].iloc[-1])
data_csv['SSAWages'].Year.iloc[-1] = 2016

data_csv['AMEND_metadata'] = pd.Series({
	'Website':'https://nesanders.github.io/MAenvironmentaldata/index.html',
	'GitHub':'https://github.com/nesanders/MAenvironmentaldata',
	'db_generated':datetime.datetime.now(),
	})

for key in data_csv:
	data_csv[key].to_sql(key, disk_engine, if_exists='append')

os.system('gsutil cp AMEND.db gs://ns697-amend/amend.db')
