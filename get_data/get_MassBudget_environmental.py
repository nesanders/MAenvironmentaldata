"""Download Environmental agency budget data from the MassBudget website.
"""

import requests
import datetime
import os
import pandas as pd
from io import StringIO

## Download "All Line Items" spreasdsheet linked here: http://massbudget.org/browser/subcat.php?id=Environment&inflation=cpi#line_items
MASSBUDGET_URL = 'https://massbudget.org/wp-content/themes/astra-child/browser-assets/spreadsheet.php?id=Environment&inflation=cpi&level=subcat'


def fix_commas(df: pd.DataFrame) -> None:
	"""Convert string-with-comma-separator numbers in a DataFrame to floats in place.
	"""
	for col in df.columns:
		if df[col].dtype == 'O':
			try:
				df[col+'_float'] = df[col].apply(lambda x: float(str(x).replace(',','')))
				print("Fixed commas for "+col)
			except:
				print("Wrong type: "+col)
	df.rename(columns = {c:c.replace(' ','_') for c in df.columns if ' ' in c}, inplace=1)


if __name__ == '__main__':
	mb_csv = requests.get(MASSBUDGET_URL).content.decode('utf-8')
	## File has a summary table and two separate line-item level tables

	#########################
	## Table 1
	#########################

	df_summary = pd.read_csv(StringIO(mb_csv.split('\n\n')[1]))
	df_summary.rename(columns={
			'Unnamed: 0':'FiscalYear', 
			'adjusted for inflation (CPI)': 'TotalBudget_inf', 
			'NOT adjusted for inflation':'TotalBudget_noinf'
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
	
	sel_dep_inf = df_inf.LineItemName=='Department of Environmental Protection Administration'
	df_summary['DEPAdministration_inf'] = df_inf[sel_dep_inf].T.loc[df_summary['FiscalYear']].squeeze().values
	sel_dep_noinf = df_noinf.LineItemName=='Department of Environmental Protection Administration'
	df_summary['DEPAdministration_noinf'] = df_noinf[sel_dep_noinf].T.loc[df_summary['FiscalYear']].squeeze().values


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

