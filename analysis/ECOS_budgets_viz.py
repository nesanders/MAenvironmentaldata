import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import chartjs
from scipy.stats import pearsonr

import matplotlib as mpl
color_cycle = [c['color'] for c in list(mpl.rcParams['axes.prop_cycle'])]

import locale
locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')

def safe_cast(x, to_type=int):
	y = []
	for xx in x:
		try:
			y += [to_type(xx)]
		except:
			pass
	return np.array(y)



## Load database
disk_engine = create_engine('sqlite:///../get_data/AMEND.db')

#############################
## Load data
#############################

## Get ECOS state budget data
s_data = pd.read_sql_query('SELECT * FROM ECOS_budgets', disk_engine)
ECOS_years = np.unique(safe_cast(s_data.Year.values)).astype(str)

## Get DEP funding data
f_data = pd.read_sql_query('SELECT * FROM MassBudget_summary', disk_engine)
f_data.index = f_data.Year

## Get DEP funding data
inf_data = pd.read_sql_query('SELECT * FROM SSAWages', disk_engine)
inf_data.index = inf_data.Year.astype(str)
inf_target = '2016'
## Restrict to relevant years and calculate correction factors
inf_data_sel = inf_data.ix[ECOS_years]
inf_data_sel['correct'] = inf_data_sel['AWI'].ix[inf_target] / inf_data_sel['AWI']

## Establish file to export facts
fact_file = '../docs/_data/facts_ECOSbudgets.yml'
with open(fact_file, 'w') as f: f.write('')


#############################
## Compare ECOS and DEP data
#############################


#############################
## Show total budget per year by state
#############################

sel = (s_data['BudgetDetail']=="Environmental Agency Budget") & s_data.Year.isin(ECOS_years.astype(str))
s_data_g = s_data[sel].groupby(['State'])
states = sorted(s_data_g.groups.keys())

## Establish chart
mychart = chartjs.chart("ECOS Budgets by State Per Year", "Line", 640, 480)
mychart.set_labels(ECOS_years)
for i,state in enumerate(states):
	vals = s_data_g.get_group(state).set_index('Year').ix[ECOS_years].value.astype(float) * inf_data_sel['correct'] / 1e6 
	mychart.add_dataset(
		vals, 
		state,
		backgroundColor="'"+(color_cycle*10)[i]+"'",
		stack="'annual'", yAxisID= "'y-axis-0'", fill = "false",
		hidden = 'false' if state in ['Massachusetts','New Hampshire','Vermont','Maine','Rhode Island'] else 'true')
mychart.set_params(JSinline = 0, ylabel = 'Reported Environmental Agency Budget (ECOS, $M)', xlabel='Year',
	scaleBeginAtZero=1)

mychart.jekyll_write('../docs/_includes/charts/ECOS_budget_peryear_bystate.html')




#############################
## Show per capita budget per year by state
#############################




#############################
## Show federal contribution per year by state
#############################


