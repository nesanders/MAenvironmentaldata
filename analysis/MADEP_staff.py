from __future__ import absolute_import
import pandas as pd
import numpy as np
#from matplotlib.ticker import FixedLocator, MaxNLocator,  MultipleLocator
#from matplotlib import pyplot as plt
#from matplotlib import cm
from sqlalchemy import create_engine
import chartjs
from scipy.stats import pearsonr

import matplotlib as mpl
color_cycle = [c['color'] for c in list(mpl.rcParams['axes.prop_cycle'])]


## Load database
disk_engine = create_engine('sqlite:///../get_data/AMEND.db')

## Get VisibleGovernment data
s_data = pd.read_sql_query('SELECT * FROM MADEP_staff', disk_engine)
years = s_data.CalendarYear.unique()

## Get wage adjustments
ssa_wage_df = pd.read_sql_query('SELECT * FROM SSAWages', disk_engine)
ssa_wage_df.index = ssa_wage_df.Year.astype(int)
wage_adjust = ssa_wage_df.ix[years].AWI.values / ssa_wage_df.ix[2015].AWI

## Get comptroller's data
s_data_soda = pd.read_sql_query('SELECT * FROM MADEP_staff_Comptroller', disk_engine)
s_data_j = pd.merge(s_data, s_data_soda, how='outer', 
	 left_on=['CalendarYear', 'name_first', 'name_last'], 
	 right_on=['year', 'name_first', 'name_last']
	 )
s_data_j['BoughtOut'] = s_data_j.pay_buyout_actual > 0


## Get funding data
f_data = pd.read_sql_query('SELECT * FROM MassBudget_summary', disk_engine)
f_data.index = f_data.Year


#############################
## Show overall employment
#############################

s_data_g = s_data.groupby(['CalendarYear']).count().Earnings
s_data_jg = s_data_j.groupby(['position_type', 'CalendarYear']).count().Earnings

## Establish chart
mychart = chartjs.chart("Overall DEP Staffing", "Bar", 640, 480)
mychart.set_labels(s_data_g.index.values.tolist())
fte_stack = s_data_jg.ix['Full Time Employee'].ix[years].fillna(0).values
mychart.add_dataset(fte_stack.tolist(), 
	"Full time DEP employees",
	backgroundColor="'rgba(50,50,200,0.8)'",
	stack="'annual'", yAxisID= "'y-axis-0'",)
mychart.add_dataset((s_data_g.values).tolist(), "Total DEP employment",
	backgroundColor="'rgba(50,50,50,0.5)'",
	stack="'annual'", yAxisID= "'y-axis-0'")
mychart.set_params(JSinline = 0, ylabel = 'Total employment', xlabel='Year',
	scaleBeginAtZero=1)

mychart.jekyll_write('../docs/_includes/charts/MADEP_staffing_overall.html')


#############################
## Show overall employment vs funding
#############################

## Establish chart
mychart = chartjs.chart("Overall DEP Staffing vs Funding", "Bar", 640, 480)
mychart.set_labels(s_data_g.index.values.tolist())
fte_stack = s_data_jg.ix['Full Time Employee'].ix[years].fillna(0).values
mychart.add_dataset((s_data_g.values).tolist(), "Total DEP employment",
	backgroundColor="'rgba(50,50,50,0.5)'",
	type="'line'", fill = "false",
	borderWidth = 2,
	stack="'annual'", yAxisID= "'y-axis-0'")
mychart.add_dataset((f_data['DEPAdministration_inf_float'].ix[years]/1e6).values.tolist(), "DEP administrative budget",
	borderColor = "'"+color_cycle[1]+"'", fill = "false",
	borderWidth = 2,
	stack="'annual'", type="'line'", yAxisID= "'y-axis-1'")
mychart.set_params(JSinline = 0, ylabel = 'Total employment', xlabel='Year',
	y2nd = 1, y2nd_title = 'Funding level ($M, 2016 dollars)',
	scaleBeginAtZero=0)

mychart.jekyll_write('../docs/_includes/charts/MADEP_staffing_overall_funding.html')



pr = pearsonr(s_data_g.values, (f_data['DEPAdministration_inf_float'].ix[years]/1e6).values)
with open('../docs/data/facts_DEPstaff.yml', 'w') as f:
	f.write('cor_staff_funding: %0.0f'%(pr[0]*100)+'\n')



#############################
## Buyout levels
#############################

## Establish chart
mychart = chartjs.chart("DEP buyouts", "Bar", 640, 480)
mychart.set_labels(s_data_g.index.values.tolist())
mychart.add_dataset(
	(s_data_j.groupby(['year']).pay_buyout_actual.sum().ix[years] * wage_adjust / 1e6).values, 
	"Buyout expenditures",
	backgroundColor="'rgba(50,50,50,0.5)'",
	type="'line'", fill = "false",
	borderWidth = 2,
	stack="'annual'", yAxisID= "'y-axis-0'")
mychart.add_dataset(
	(s_data_j.groupby(['year']).BoughtOut.sum().ix[years]).values, 
	"Staff Bought Out",
	borderColor = "'"+color_cycle[1]+"'", fill = "false",
	borderWidth = 2, steppedLine = 'true',
	stack="'annual'", type="'line'", yAxisID= "'y-axis-1'")
mychart.set_params(JSinline = 0, ylabel = 'Cost($M)', xlabel='Year',
	y2nd = 1, y2nd_title = 'Number of personnel',
	scaleBeginAtZero=1)

mychart.jekyll_write('../docs/_includes/charts/MADEP_staffing_buyout.html')


#############################
## Show average seniority per job type
#############################

s_data_gj = s_data.groupby(['JobType','CalendarYear'])
sel_titles = [['Environmental Analyst'], ['Environmental Engineer'], ['Program Coordinator'], ['Regional Planner', 'Planners'], ['Counsel']]

ys = []; cs = []
for i,jt in enumerate(sel_titles):
	ys += [np.zeros(len(years))]
	cs += [np.zeros(len(years))]
	try:
		ys[-1] += s_data_gj.Earnings.sum().ix[(jt[0])].ix[years].replace(np.nan, 0).values
		cs[-1] += s_data_gj.Earnings.count().ix[(jt[0])].ix[years].replace(np.nan, 0).values
	except pd.core.indexing.IndexingError:
		pass

## Establish chart
mychart = chartjs.chart("DEP wages over time", "Line", 640, 480)
mychart.set_labels(years.tolist())
mychart.set_params(JSinline = 0, ylabel = 'Average earnings per year ($k)', xlabel='Year')


## Run non-inflation loop separately so they are adjacent in legend
for i,jt in enumerate(sel_titles):
	mychart.add_dataset(
		(ys[i] / 1000. / cs[i].astype(float)).tolist(), 
		jt[0]+(' (absolute dollars)' if i==0 else ''),
		borderColor = "'"+color_cycle[i]+"'", fill = "false",
		hidden = "true",
		borderDash = '[10,15]', borderWidth = 0.5
		)


for i,jt in enumerate(sel_titles):
	mychart.add_dataset(
		(ys[i] / wage_adjust / 1000. / cs[i].astype(float)).tolist(), 
		jt[0]+(' (inflation adjusted)' if i==0 else ''),
		borderColor = "'"+color_cycle[i]+"'", fill = "false",
		borderWidth = 2
		)



## Write out
mychart.jekyll_write('../docs/_includes/charts/MADEP_staffing_wagehistory.html', full=0)




#############################
## Show average seniority per job type
#############################

s_data_gj = s_data.groupby(['JobType','CalendarYear'])
sel_titles = [['Environmental Analyst'], ['Environmental Engineer'], ['Program Coordinator'], ['Regional Planner', 'Planners'], ['Counsel']]

ys = []; cs = []
for i,jt in enumerate(sel_titles):
	ys += [np.zeros(len(years))]
	cs += [np.zeros(len(years))]
	try:
		ys[-1] += s_data_gj.Seniority.sum().ix[(jt[0])].ix[years].replace(np.nan, 0).values
		cs[-1] += s_data_gj.Earnings.count().ix[(jt[0])].ix[years].replace(np.nan, 0).values
	except pd.core.indexing.IndexingError:
		pass

## Establish chart
mychart = chartjs.chart("DEP seniority over time", "Line", 640, 480)
mychart.set_labels(years.tolist())
mychart.set_params(JSinline = 0, ylabel = 'Average seniority gain (yrs with DEP since 2004)', xlabel='Year')

for i,jt in enumerate(sel_titles):
	mychart.add_dataset(
		(ys[i] / cs[i].astype(float)).tolist() - (years - years[0]), 
		jt[0],
		borderColor = "'"+color_cycle[i]+"'", fill = "false",
		borderWidth = 2
		)

## Write out
mychart.jekyll_write('../docs/_includes/charts/MADEP_staffing_seniority.html', full=0)



#############################
## Show indexed position changes over time
#############################

sel_titles = [['Environmental Analyst'], ['Environmental Engineer'], ['Program Coordinator'], ['Regional Planner', 'Planners'], ['Accountant'], ['Counsel']]

## Total number of employees in major types
ys = []
for i,t in enumerate(sel_titles):
	ys += [s_data[s_data.JobType == t[0]].groupby('CalendarYear').Earnings.count().ix[years].values]

mychart = chartjs.chart("DEP role volume over time", "Line", 640, 480)
mychart.set_labels(years.tolist())
mychart.set_params(JSinline = 0, 
	ylabel = 'Total staff change since 2004 (%)', xlabel='Year')


## Run non-inflation loop separately so they are adjacent in legend
for i,t in enumerate(sel_titles):
	mychart.add_dataset(
		(100 * ys[i] / ys[i][0]).tolist(), 
		t[0],
		borderColor = "'"+color_cycle[i]+"'", fill = "false",
		borderWidth = 2
		)


## Write out
mychart.jekyll_write('../docs/_includes/charts/MADEP_staffing_rolevolume.html', full=0)

