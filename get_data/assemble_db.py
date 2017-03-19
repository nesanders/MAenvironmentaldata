import pandas as pd
import datetime
from sqlalchemy import create_engine
import os

## Establish database
os.system('mv MERDR.db backup_MERDR.db')
disk_engine = create_engine('sqlite:///MERDR.db')

## Load datasets
data_csv = {}
data_csv['EPARegion1_permits'] = pd.read_csv('../docs/_data/EPARegion1_NPDES_permit_data.csv')
data_csv['MADEP_enforcement'] = pd.read_csv('../docs/_data/MADEP_enforcement_actions.csv')
data_csv['MADEP_staff'] = pd.read_csv('../docs/_data/MADEP_staff.csv')
data_csv['MassBudget_infadjusted'] = pd.read_csv('../docs/_data/MassBudget_environmental_infadjusted.csv')
data_csv['MassBudget_noinfadjusted'] = pd.read_csv('../docs/_data/MassBudget_environmental_noinfadjusted.csv')
data_csv['MassBudget_summary'] = pd.read_csv('../docs/_data/MassBudget_environmental_summary.csv')

## Temporary insertion for 2016 assuming no inflation
data_csv['SSAWages'] = pd.read_csv('../docs/_data/SSAWages_2016-12-09.csv')
data_csv['SSAWages'] = data_csv['SSAWages'].append(data_csv['SSAWages'].iloc[-1])
data_csv['SSAWages'].Year.iloc[-1] = 2016

data_csv['MERDR_metadata'] = pd.Series({
	'Website':'https://nesanders.github.io/MAenvironmentaldata/index.html',
	'GitHub':'https://github.com/nesanders/MAenvironmentaldata',
	'db_generated':datetime.datetime.now(),
	})

for key in data_csv:
	data_csv[key].to_sql(key, disk_engine, if_exists='append')

os.system('gsutil cp MERDR.db gs://ns697-merdr/merdr.db')
