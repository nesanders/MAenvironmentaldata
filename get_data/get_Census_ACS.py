import numpy as np
import pandas as pd
from census import Census
from us import states
import os
import datetime

def muni_formatter(x):
	"""
	Reformat Census place names as commo municipality names
	"""
	return x.split(', ')[0].replace(' CDP', '').replace(' city', '').replace(' town', '')


## Setup Census reader
with open('SECRET_Census_token', 'r') as f:
	api_key = f.read().strip()

census_year = 2014
c = Census(api_key, year=census_year) # census python package only supports up to 2014

## See API examples here - https://api.census.gov/data/2014/acs5/examples.html
## See question info e.g. here: https://factfinder.census.gov/faces/tableservices/jsf/pages/productview.xhtml?pid=ACS_15_5YR_B01003&prodType=table

population_data = \
c.acs5.get(('NAME', 'B01003_001E'),
		{
			'for': 'county subdivision:*', 
			'in': 'state:{}'.format(states.MA.fips),
		}
	)

d_population_data = pd.Series({muni_formatter(u['NAME']):int(u['B01003_001E']) for u in population_data}, name='population_acs52014')

## Can see some useful income variables here: https://uscensusbureau.github.io/citysdk/developers/aliases/
percapita_income_data = \
c.acs5.get(('NAME', 'B19301_001E'),
		{
			'for': 'county subdivision:*', 
			'in': 'state:{}'.format(states.MA.fips),
		}
	) # in 2013 inflation-adjusted dollars

d_income_data = pd.Series({muni_formatter(u['NAME']):float(u['B19301_001E']) if u['B19301_001E'] is not None else np.nan for u in percapita_income_data}, name='per_capita_income_acs52014')


d_s = [d_population_data, d_income_data]
df = pd.DataFrame(d_s).T
df['Subdivision'] = df.index


df.to_csv('../docs/data/Census_ACS_MA.csv', index=False)


## Report last update
with open('../docs/data/ts_update_census_acs.yml', 'w') as f:
	f.write('updated: '+str(datetime.datetime.now()).split('.')[0]+'\n'\
		 +'census_year: '+str(census_year)+'\n'
	)


