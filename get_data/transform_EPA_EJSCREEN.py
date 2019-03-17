from __future__ import absolute_import
import pandas as pd
import numpy as np
import datetime

## Get dataset
# Remote
# df_ejs = pd.read_csv('ftp://newftp.epa.gov/EJSCREEN/2017/EJSCREEN_2017_USPR_Public.csv')
# Local
df_ejs = pd.read_csv('EJSCREEN_2017_USPR_Public.csv')

## Filter to state level
df_ejs_ma = df_ejs[df_ejs['STATE_NAME'] == "Massachusetts"]
## Write out
df_ejs_ma.to_csv('../docs/data/EPA_EJSCREEN_MA_2017.csv', index=0)


## Print a sample of the file as an example
df_ejs_ma.sample(n=10).to_csv('../docs/data/EPA_EJSCREEN_MA_2017_sample.csv', index=False)

## Report last update
with open('../docs/data/ts_update_EPA_EJSCREEN_MA_2017.yml', 'w') as f:
	f.write('updated: '+str(datetime.datetime.now()).split('.')[0]+'\n')
