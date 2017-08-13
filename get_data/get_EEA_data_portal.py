"""
This script queries the MA Energy and Environemtal Affairs Data Portal, publicly viewable at:
http://eeaonline.eea.state.ma.us/portal#!/home


"""

import os
import datetime
import requests
import pandas as pd
import numpy as np

##########################
## API parameters
##########################

API_root = 'http://eeaonline.eea.state.ma.us/EEA/DataLake/V1.0/DataLakeAPI/'
API_tables = ['permit', 'facility', 'inspection', 'enforcement', 'drinkingWater']


##########################
## Function definitions
##########################

def query_iterate(table_name, req_size = 100000, verbose = True):
	"""
	Query the EEA data portal to retrieve the entirety of a data table.
	
	Returns 
	
	Args:
		table_name (str): EEA data portal table to query
		req_size (int): Request chunksize
		verbose (bool): Print chunk position while iterating
	
	Returns:
		df: Pandas DataFrame with table contents
	"""
	# Get total table size
	try:
		r = requests.get(API_root + table_name + '?_end=1&_start=0')
		table_size = r.json()['TotalCount']
	except ValueError: 
		raise ValueError("EEA Data Portal request returned error " + str(r.status_code) + '; perhaps table name is not valid\n\nFull response message:\n' + r.text)

	# Iterate through requests
	if (table_size < req_size):
		req_bins = [0, table_size]
	else:
		max_bin = table_size + req_size
		req_bins = np.arange(0, max_bin, req_size)
	dfs = []
	for i in range(len(req_bins) - 1):
		# Log output
		if verbose: print table_name + ': request ' + str(i + 1) + ' of ' + str(len(req_bins) - 1)
		# Make request
		url = API_root + table_name + '?_end=' + str(req_bins[i+1]) + '&_start='+str(req_bins[i])
		r = requests.get(url)
		# Add chunk contents to dataframe list
		dfs += [pd.DataFrame(r.json()['Items'])]

	# Concatenate chunks
	df = pd.concat(dfs)
	
	return df


##########################
## Get data
##########################

## Query data for each table
table_data = {}
for tab in API_tables:
	table_data[tab] = query_iterate(tab)
	
	## Write out, but treat large tables separately
	## Only one table (drinkingWater) is >10MB as of 08/2017, so we handle this as a special case.
	## Could also use `size_MB = os.path.getsize('../docs/data/EEADP_' + tab + '.csv')/1024/1024` to get file size
	
	## Print the header of the file as an example
	table_data[tab].sample(n=10).to_csv('../docs/data/EEADP_' + tab + '_sample.csv', index=0)
	
	if tab != 'drinkingWater': 
		table_data[tab].to_csv('../docs/data/EEADP_' + tab + '.csv', index=0)
	else:
		## Send to Google object store
		table_data[tab].to_csv('EEADP_' + tab + '.csv', index=0)
		os.system('gsutil cp EEADP_' + tab + '.csv gs://ns697-amend/EEADP_' + tab + '.csv')
		
		## Include some special summary statistics tables
		## ---		
		## Most recent report for each chemical for each site
		## This still ends up being ~20% of the original size, so larger than desired
		#table_data[tab].sort_values('CollectedDate', inplace=True)
		#df_dw_last = table_data[tab].groupby(['ChemicalName','PWSName','LocationName']).last()
		
		# Tests per year per PWS per contaminant group per raw/finished
		## This still ends up being ~40% of the original size, so larger than desired
		table_data[tab]['CollectedDate'] = pd.to_datetime(table_data[tab]['CollectedDate'], errors='coerce')
		table_data[tab]['Year'] = table_data[tab]['CollectedDate'].apply(lambda x: x.year)
		df_dw_annual_group = table_data[tab].groupby(['Year','PWSName', 'ContaminantGroup','RaworFinished']).agg({'Result': pd.Series.count})
		df_dw_annual_group.to_csv('../docs/data/EEADP_' + tab + '_annual.csv', index=1)
		## Print the header of the file as an example
		df_dw_annual_group.sample(n=10).to_csv('../docs/data/EEADP_' + tab + '_annual_sample.csv', index=1)
		

		## Tests per year per PWS per chemical per raw/finished
		### This still ends up being ~40% of the original size, so larger than desired
		#df_dw_annual = table_data[tab].groupby(['Year','PWSName', 'ChemicalName','RaworFinished']).agg({'ContaminantGroup': lambda x: x.iloc[0], 'Result': pd.Series.count})
		


##########################
## Archive PDF help files
##########################

os.system('wget http://eeaonline.eea.state.ma.us/Portal/documents/General%20Query%20Search%20FAQs.pdf')
os.system('mv "General Query Search FAQs.pdf" ../docs/assets/PDFs/EEADP_FAQ.pdf')
os.system('wget http://eeaonline.eea.state.ma.us/Portal/documents/Terms%20and%20Definitions%20for%20EEA.pdf')
os.system('mv "Terms and Definitions for EEA.pdf" ../docs/assets/PDFs/EEADP_Definitions.pdf')


##########################
## Report last update
##########################

with open('../docs/data/ts_update_EEADP.yml', 'w') as f:
	f.write('updated: '+str(datetime.datetime.now()).split('.')[0]+'\n')

