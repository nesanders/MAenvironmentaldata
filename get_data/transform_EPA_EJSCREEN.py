"""This script downloads EPA EJSCREEN data from the EPA ftp site, filters it to MA census
block groups, and saves it to a local file.
"""

import datetime
from pathlib import Path

import numpy as np
import pandas as pd

DATASET_URLS = {
	2017: 'ftp://gaftp.epa.gov/EJScreen/2017/EJSCREEN_2017_USPR_Public.csv',
	2023: 'ftp://gaftp.epa.gov/EJScreen/2023/2.22_September_UseMe/EJSCREEN_2023_BG_StatePct_with_AS_CNMI_GU_VI.csv.zip'
}


if __name__ == '__main__':
	for year, file_url in DATASET_URLS.items():
		
		print(f'Working on year {year}')
		
		local_name = file_url.split('/')[-1]
		## Get dataset
		if not Path(local_name).exists():
			# Remote - only need to download once
			df_ejs = pd.read_csv(file_url, encoding='latin-1')
			df_ejs.to_csv(local_name)
		else:
			# Local
			df_ejs = pd.read_csv(local_name, encoding='latin-1')

		## Filter to state level
		df_ejs_ma = df_ejs[df_ejs['STATE_NAME'] == "Massachusetts"]
		
		## Standardize on the variable name 'MINORPCT' versus 'PEOPCOLORPCT'
		df_ejs_ma.rename(columns={'PEOPCOLORPCT': 'MINORPCT'}, inplace=True)
		
		## Write out
		df_ejs_ma.to_csv(f'../docs/data/EPA_EJSCREEN_MA_{year}.csv', index=0)

		## Print a sample of the file as an example
		df_ejs_ma.sample(n=10).to_csv(f'../docs/data/EPA_EJSCREEN_MA_{year}_sample.csv', index=False)

		## Report last update
		with open(f'../docs/data/ts_update_EPA_EJSCREEN_MA_{year}.yml', 'w') as f:
			f.write('updated: '+str(datetime.datetime.now()).split('.')[0]+'\n')
