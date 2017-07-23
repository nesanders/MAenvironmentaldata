import numpy as np
import pandas as pd
import os, datetime

## Download data files
os.system('wget https://www2.census.gov/programs-surveys/popest/tables/2000-2010/intercensal/state/st-est00int-01.csv')
os.system('wget https://www2.census.gov/programs-surveys/popest/tables/2010-2016/state/totals/nst-est2016-01.xlsx')

## Read in files
data_2000 = pd.read_csv('st-est00int-01.csv', skiprows=3)
data_2010 = pd.read_excel('nst-est2016-01.xlsx', skiprows=3)

## Clean files
data_2000_c = data_2000[np.arange(2000,2010).astype(str)].set_index(data_2000.iloc[:,0].str.replace('.','')).dropna().apply(lambda x: x.apply(lambda y: y.replace(',',''))).astype(float)

data_2010_c = data_2010[np.arange(2010,2017)].set_index(data_2010.iloc[:,0].str.replace('.','')).dropna()

## Merge files
data_merge = pd.merge(data_2000_c, data_2010_c, left_index=True, right_index=True)
data_merge['State'] = data_merge.index

## Write out
data_merge.to_csv('../docs/data/Census_statepop.csv', index=0)
os.system('cp ../docs/data/Census_statepop.csv ../docs/_data/Census_statepop.csv')


## Report last update
with open('../docs/_data/ts_update_statepop.yml', 'w') as f:
	f.write('updated: '+str(datetime.datetime.now()).split('.')[0]+'\n' )


