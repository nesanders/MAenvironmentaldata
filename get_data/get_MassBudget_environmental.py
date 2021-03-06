from __future__ import absolute_import
from __future__ import print_function
import requests
import datetime
import os
import pandas as pd
from io import StringIO

## Download "All Line Items" spreasdsheet linked here: http://massbudget.org/browser/subcat.php?id=Environment&inflation=cpi#line_items
massbudget_spreadsheet_link = 'http://massbudget.org/browser/spreadsheet.php?id=Environment&inflation=cpi&level=subcat'

mb_csv = requests.get(massbudget_spreadsheet_link).content.decode('utf-8')
## File has a summary table and two separate line-item level tables


def fix_commas(df):
	for col in df.columns:
		if df[col].dtype == 'O':
			try:
				df[col+'_float'] = df[col].apply(lambda x: float(str(x).replace(',','')))
				print("Fixed commas for "+col)
			except:
				print("Wrong type: "+col)
	df.rename(columns = {c:c.replace(' ','_') for c in df.columns if ' ' in c}, inplace=1)


#########################
## Table 1
#########################

df_summary = pd.read_csv(StringIO(mb_csv.split('\n\n')[1]))
df_summary.rename(columns={
		'Unnamed: 0':'FiscalYear', 'adjusted for inflation (CPI)':'TotalBudget_inf', 'NOT adjusted for inflation':'TotalBudget_noinf'
	}, inplace=1)

df_summary['Year'] = 2000+df_summary.FiscalYear.apply(lambda x: int(x.split()[0][-2:]))
df_summary['GovernorsBudget'] = df_summary.FiscalYear.apply(lambda x: 1 if 'Gov' in x else 0)


#########################
## Table 2
#########################

df_inf = pd.read_csv(StringIO('\n'.join(mb_csv.split('\n\n')[2].split('\n')[2:])))
df_inf.rename(columns={
		'Unnamed: 0':'LineItem', 'Unnamed: 1':'LineItemName'
	}, inplace=1)



#########################
## Table 3
#########################

df_noinf = pd.read_csv(StringIO('\n'.join(mb_csv.split('\n\n')[3].split('\n')[2:])))
df_noinf.rename(columns={
		'Unnamed: 0':'LineItem', 'Unnamed: 1':'LineItemName'
	}, inplace=1)


#########################
## Add to summary table
#########################

df_summary['DEPAdministration_inf'] = df_inf[df_inf.LineItemName=='Department of Environmental Protection Administration'].T.ix[df_summary.FiscalYear].values
df_summary['DEPAdministration_noinf'] = df_noinf[df_noinf.LineItemName=='Department of Environmental Protection Administration'].T.ix[df_summary.FiscalYear].values


#########################
## Write out data
#########################

fix_commas(df_summary)
df_summary.to_csv('../docs/data/MassBudget_environmental_summary.csv', index=0, encoding='ascii')

fix_commas(df_inf)
df_inf.to_csv('../docs/data/MassBudget_environmental_infadjusted.csv', index=0, encoding='ascii')

fix_commas(df_noinf)
df_noinf.to_csv('../docs/data/MassBudget_environmental_noinfadjusted.csv', index=0, encoding='ascii')



## Report last update
with open('../docs/data/ts_update_MassBudget_environmental.yml', 'w') as f:
	f.write('updated: '+str(datetime.datetime.now()).split('.')[0]+'\n')

