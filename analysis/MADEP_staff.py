import pandas as pd
import numpy as np
#from matplotlib.ticker import FixedLocator, MaxNLocator,  MultipleLocator
#from matplotlib import pyplot as plt
#from matplotlib import cm
from sqlalchemy import create_engine
import chartjs

import matplotlib as mpl
color_cycle = [c['color'] for c in list(mpl.rcParams['axes.prop_cycle'])]


## Load database
disk_engine = create_engine('sqlite:///../get_data/MERDR.db')

s_data = pd.read_sql_query('SELECT * FROM MADEP_staff', disk_engine)

ssa_wage_df = pd.read_sql_query('SELECT * FROM SSAWages', disk_engine)
ssa_wage_df.index = ssa_wage_df.Year.astype(int)

years = s_data.CalendarYear.unique()


#############################
## Show average seniority per job type
#############################
s_data_gj = s_data.groupby(['JobType','CalendarYear'])
sel_titles = [['Environmental Analyst'], ['Environmental Engineer'], ['Program Coordinator'], ['Regional Planner', 'Planners'], ['Counsel']]
wage_adjust = ssa_wage_df.ix[years].AWI.values / ssa_wage_df.ix[2015].AWI

#fig, axgrid = plt.subplots(int(np.ceil(len(sel_titles)/3.)), 3, sharex='all', sharey='all', figsize=(8, 8))
#axs = axgrid.flatten()
ys = []; cs = []
for i,jt in enumerate(sel_titles):
	ys += [np.zeros(len(years))]
	cs += [np.zeros(len(years))]
	try:
		ys[-1] += s_data_gj.Earnings.sum().ix[(jt[0])].ix[years].replace(np.nan, 0).values
		cs[-1] += s_data_gj.Earnings.count().ix[(jt[0])].ix[years].replace(np.nan, 0).values
	except pd.core.indexing.IndexingError:
		pass
	#axs[i].plot(years, y / wage_adjust / 1000. / c.astype(float), lw=2, color='k', marker='o', label='2015 adjusted dollars')
	#axs[i].plot(years, y / 1000. / c.astype(float), lw=1, color='.5', ls='dashed', label='Absolute dollars')
	#axs[i].set_title(jt[0], fontsize=9)
	#axs[i].xaxis.set_major_locator(MultipleLocator(4))
	#axs[i].xaxis.set_minor_locator(MultipleLocator(1))

#for k in range(i + 1, len(axs)):
	#axs[k].set_visible(0)

#axs[i].set_xlim(2003, 2017)
#axs[i].legend(prop={'size':10}, loc='center left', bbox_to_anchor=(1, 0.5), title='Level')
#plt.figtext(0.05, 0.5, 'Average earnings per year ($k)', rotation='vertical', va='center')
#plt.legend()

#plt.savefig('../docs/assets/figures/MADEP_staff_earnings_by_role.png', dpi=150)

## Establish chart
mychart = chartjs.chart("DEP seniority over time", "Line", 640, 480)
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
#with open('../docs/_includes/charts/MADEP_staffing_wagehistory.html', 'w') as f:
	#f.write("{% raw  %}\n")
	#out = mychart.make_chart_full_html().split('\n')
	#out = [o for o in out if '<h2>' not in o and 'doctype html' not in o]
	#out = '\n'.join(out)
	#f.write(out)
	#f.write("{% endraw  %}\n")
	






#############################
## Show indexed position changes over time
#############################

sel_titles = [['Environmental Analyst'], ['Environmental Engineer'], ['Program Coordinator'], ['Regional Planner', 'Planners'], ['Accountant'], ['Counsel']]

## Total number of employees in major types
#fig, ax = plt.subplots(1, figsize=(6,5))
ys = []
for i,t in enumerate(sel_titles):
	ys += [s_data[s_data.JobType == t[0]].groupby('CalendarYear').Earnings.count().ix[years].values]
	#plt.plot(years, 100 * y / y[0], lw = 2, label = t[0], color = cm.Paired(float(i) / len(sel_titles)))

#ax.xaxis.set_major_locator(MultipleLocator(4))
#ax.xaxis.set_minor_locator(MultipleLocator(1))
#plt.legend(prop={'size':9}, loc=3)
#plt.ylabel('Total staff change since 2004 (%)')

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

