"""Fetch US Census state population estimates 2000-2024.

Combines three published vintages from the Census Bureau:
- 2000-2009: intercensal estimates (st-est00int-01.csv)
- 2010-2019: vintage-2019 estimates (nst-est2019-01.xlsx)
- 2020-2024: vintage-2024 estimates (NST-EST2024-POP.xlsx)

Where vintages overlap we prefer the later vintage.
"""
from __future__ import absolute_import
import datetime
import os
import numpy as np
import pandas as pd

URLS = {
	'st-est00int-01.csv': 'https://www2.census.gov/programs-surveys/popest/tables/2000-2010/intercensal/state/st-est00int-01.csv',
	'nst-est2019-01.xlsx': 'https://www2.census.gov/programs-surveys/popest/tables/2010-2019/state/totals/nst-est2019-01.xlsx',
	'NST-EST2024-POP.xlsx': 'https://www2.census.gov/programs-surveys/popest/tables/2020-2024/state/totals/NST-EST2024-POP.xlsx',
}

for fname, url in URLS.items():
	if os.path.exists(fname):
		os.remove(fname)
	os.system(f'wget -q "{url}" -O "{fname}"')

data_2000 = pd.read_csv('st-est00int-01.csv', skiprows=3)
data_2010 = pd.read_excel('nst-est2019-01.xlsx', skiprows=3)
data_2020 = pd.read_excel('NST-EST2024-POP.xlsx', skiprows=3)

data_2000_c = (
	data_2000[np.arange(2000, 2010).astype(str)]
	.set_index(data_2000.iloc[:, 0].str.replace('.', '', regex=False))
	.dropna()
	.apply(lambda x: x.apply(lambda y: y.replace(',', '')))
	.astype(float)
)

data_2010_c = (
	data_2010[np.arange(2010, 2020)]
	.set_index(data_2010.iloc[:, 0].str.replace('.', '', regex=False))
	.dropna()
)

data_2020_c = (
	data_2020[np.arange(2020, 2025)]
	.set_index(data_2020.iloc[:, 0].str.replace('.', '', regex=False))
	.dropna()
)

data_merge = data_2000_c.join(data_2010_c, how='inner').join(data_2020_c, how='inner')
data_merge.columns = data_merge.columns.astype(str)
data_merge['State'] = data_merge.index

data_merge.to_csv('../docs/data/Census_statepop.csv', index=False)

with open('../docs/data/ts_update_statepop.yml', 'w') as f:
	f.write('updated: ' + str(datetime.datetime.now()).split('.')[0] + '\n')
