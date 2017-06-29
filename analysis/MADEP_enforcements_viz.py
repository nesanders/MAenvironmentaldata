import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import chartjs
from scipy.stats import pearsonr

import matplotlib as mpl
color_cycle = [c['color'] for c in list(mpl.rcParams['axes.prop_cycle'])]

import locale
locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
 
## Load database
disk_engine = create_engine('sqlite:///../get_data/MERDR.db')


## Get MADEP website enforcement data
s_data = pd.read_sql_query('SELECT * FROM MADEP_enforcement', disk_engine)
years = s_data.Year.unique()

## Get funding data
f_data = pd.read_sql_query('SELECT * FROM MassBudget_summary', disk_engine)
f_data.index = f_data.Year

## Establish file to export facts
fact_file = '../docs/_data/facts_DEPenforce.yml'
with open(fact_file, 'w') as f: f.write('')


#############################
## Show total enforcements per year
#############################

s_data_g = s_data.groupby(['Year']).count().ix[:,1]

## Establish chart
mychart = chartjs.chart("Overall DEP Enforcement", "Bar", 640, 480)
mychart.set_labels(s_data_g.index.values.tolist())
mychart.add_dataset(s_data_g.values.tolist(), 
	"Number of enforcements",
	backgroundColor="'rgba(50,50,200,0.8)'",
	stack="'annual'", yAxisID= "'y-axis-0'",)
mychart.set_params(JSinline = 0, ylabel = 'Total reported enforcement actions', xlabel='Year',
	scaleBeginAtZero=1)

mychart.jekyll_write('../docs/_includes/charts/MADEP_enforcement_overall.html')



#############################
## Show total penalties per year
#############################

s_data_g = s_data.groupby(['Year']).sum()

## Establish chart
mychart = chartjs.chart("Overall DEP Enforcement Penalties ($M)", "Bar", 640, 480)
mychart.set_labels(s_data_g.index.values.tolist())
mychart.add_dataset((s_data_g.Fine/1e6).tolist(), 
	"Reported penalties",
	backgroundColor="'rgba(50,50,200,0.8)'",
	stack="'annual'", yAxisID= "'y-axis-0'",)
mychart.set_params(JSinline = 0, ylabel = 'Sum of reported penalties ($M)', xlabel='Year',
	scaleBeginAtZero=1)

mychart.jekyll_write('../docs/_includes/charts/MADEP_enforcement_fines_overall.html')


s_data_g_na = s_data.dropna().groupby(['Year']).Fine

## Establish stacked chart
mychart = chartjs.chart("Individual DEP Enforcement Penalties ($M)", "Bar", 640, 480)
mychart.set_labels(s_data_g.index.values.tolist())
## Output one series for each penalty
max_counts = s_data.groupby(['Year']).count().Fine.max()
rgba_list = [
	'rgba(166,206,227)',
	'rgba(31,120,180)',
	'rgba(178,223,138)',
	'rgba(51,160,44)'
	]
for i in range(max_counts):
	get_sorted_i = lambda x: 0 if (i > len(x) - 1) else sorted(x.values)[::-1][i]
	mychart.add_dataset((s_data_g_na.apply(get_sorted_i)/1e6).tolist(), 
		"Rank among largest reported penalties of the year: "+str(i),
		backgroundColor="'"+rgba_list[np.mod(i, len(rgba_list))]+"'",)
mychart.set_params(JSinline = 0, ylabel = 'Sum of reported penalties ($M)', xlabel='Year',
	scaleBeginAtZero=1, stacked=1, legend=0)

mychart.jekyll_write('../docs/_includes/charts/MADEP_enforcement_fines_overall_stacked.html')



#############################
## Show enforcements per year versus budget
#############################

s_data_g = s_data.groupby(['Year']).count().ix[:,1]

## Establish chart
mychart = chartjs.chart("DEP Enforcements versus budget", "Line", 640, 480)
mychart.set_labels(s_data_g.index.values.tolist())
mychart.add_dataset(s_data_g.values.tolist(), "Number of enforcements",
	backgroundColor="'rgba(50,50,50,0.5)'",
	type="'line'", fill = "false",
	borderWidth = 2,
	stack="'annual'", yAxisID= "'y-axis-0'")
mychart.add_dataset((f_data['DEPAdministration_inf_float'].ix[years]/1e6).values.tolist(), "DEP administrative budget",
	borderColor = "'"+color_cycle[1]+"'", fill = "false",
	borderWidth = 2,
	stack="'annual'", type="'line'", yAxisID= "'y-axis-1'")
mychart.set_params(JSinline = 0, ylabel = 'Number of enforcements', xlabel='Year',
	y2nd = 1, y2nd_title = 'Funding level ($M, 2016 dollars)',
	scaleBeginAtZero=0)

mychart.jekyll_write('../docs/_includes/charts/MADEP_enforcement_vsbudget.html')

## Output correlation level
pr = pearsonr(s_data_g.values, (f_data['DEPAdministration_inf_float'].ix[years]/1e6).values)
with open(fact_file, 'a') as f:
	f.write('cor_enforcement_funding: %0.0f'%(pr[0]*100)+'\n')


#############################
## Show enforcement fractions by topic per year
#############################

s_data_g = s_data.groupby(['Year'])
topics = [d for d in s_data.columns if d.startswith('order_') or d.startswith('law_')]

## Establish chart
mychart = chartjs.chart("DEP Enforcements by Topic Per Year", "Line", 640, 480)
mychart.set_labels(s_data_g.count().index.values.tolist())
for i,topic in enumerate(topics):
	mychart.add_dataset(
		(s_data_g.sum()[topic] / s_data_g.count()[topic].astype(float)).tolist(), 
		topic.split('_')[1].strip().title(),
		backgroundColor="'"+(color_cycle*10)[i]+"'",
		stack="'annual'", yAxisID= "'y-axis-0'", fill = "false",
		hidden = 'false' if topic=='order_wetlands' else 'true')
mychart.set_params(JSinline = 0, ylabel = 'Reported enforcement actions (% of annual total)', xlabel='Year',
	scaleBeginAtZero=1)

mychart.jekyll_write('../docs/_includes/charts/MADEP_enforcement_bytopic.html')


## Export some facts.
## Exclude most recent year from averages, as it will be partial.
with open(fact_file, 'a') as f:
	f.write('yearly_ch91: %0.1f'%(s_data_g.sum()['law_chapter 91'][:-1].mean())+'\n')
	f.write('yearly_npdes: %0.1f'%(s_data_g.sum()['law_npdes'][:-1].mean())+'\n')
	f.write('yearly_avg_consentorder: %0.0f'%(s_data_g.mean()['order_consent order'][:-1].mean() * 100)+'\n')
	f.write('yearly_avg_delta2016_wetlands: %0.0f'%((1 - s_data_g.mean()['order_wetlands'].ix[2016] / s_data_g.mean()['order_wetlands'].max()) * 100)+'\n')
	f.write('yearly_2004_watersupply: %0.1f'%(s_data_g.mean()['order_water supply'].ix[2004] * 100)+'\n')
	f.write('yearly_2016_watersupply: %0.1f'%(s_data_g.mean()['order_water supply'].ix[2016] * 100)+'\n')
	
	#Water supply-related enforcement has grown from ~5% to ~25% of all enforcements since 2004
	#Wetlands-related enforcement has declined from ~16% at peak to <10% in recent years.

	

#############################
## Show distribution of penalties
#############################

#penalties_per_year = s_data_g.Fine.apply(lambda x: np.histogram(np.log10(x), bins=20, range=[2,7]))

fine_bin_edges = 200*2**(np.arange(19))
## Round down to 1 sig fig
fine_bin_edges = [int('%0.0f'%(c/10**np.floor(np.log10(c))))*10**np.floor(np.log10(c)) for c in fine_bin_edges]
fine_dist, fine_bins = np.histogram(s_data.Fine.values, bins=fine_bin_edges, range=[2,7])
fine_bins_fmt = [locale.format("%d", c, grouping=True) for c in fine_bins]

## Establish chart
mychart = chartjs.chart("Penalty distribution", "Bar", 640, 480)
mychart.set_labels(['$' + fine_bins_fmt[i]+' - '+fine_bins_fmt[i+1] for i in range(len(fine_bins_fmt)-1)])
mychart.add_dataset(fine_dist, 
	"Number of enforcements",
	backgroundColor="'rgba(50,100,100,0.8)'",
	stack="'annual'", yAxisID= "'y-axis-0'",)
mychart.set_params(JSinline = 0, ylabel = 'Number of enforcement actions since 2004', xlabel='Penalty amount ($, logarithmic spacing)',
	scaleBeginAtZero=0)

mychart.jekyll_write('../docs/_includes/charts/MADEP_enforcement_fine_dist.html')


## Show evolution of median With bootstrap resampling

## Bootstrap more appropriate here
#def jackknife(x, func):
	#n = len(x)
	#idx = np.arange(n)
	#return np.array([func(x[idx!=i]) for i in range(n)])

def bootstrap(x, func, reps = 1000):
	n = len(x)
	return func(np.random.choice(x, (n, reps)), axis=0)

s_meds = s_data_g.Fine.apply(lambda x: np.nanpercentile(bootstrap(x, np.nanmedian), [5,50,95], axis=0))
## Exclude most recent partial year
s_meds = s_meds[:-1]

## Establish chart
mychart = chartjs.chart("Penalty average", "Line", 640, 480)
mychart.set_labels(s_meds.index.tolist())
mychart.add_dataset(s_meds.apply(lambda x: x[1]).values.tolist(), 
	"Best estimate",
	backgroundColor="'rgba(50,100,100,0.8)'", yAxisID= "'y-axis-0'", borderWidth = 3, fill = 'false'  )
mychart.add_dataset(s_meds.apply(lambda x: x[0]).values.tolist(), 
	"Lower bound (5% limit)",
	backgroundColor="'rgba(50,50,50,0.3)'", yAxisID= "'y-axis-0'", borderWidth = 1, 
	fill = 'false', pointBackgroundColor="'rgba(0,0,0,0)'", pointBorderColor="'rgba(0,0,0,0)'")
mychart.add_dataset(s_meds.apply(lambda x: x[2]).values.tolist(), 
	"Upper bound (95% limit)",
	backgroundColor="'rgba(50,50,50,0.3)'", yAxisID= "'y-axis-0'", borderWidth = 1, fill = "'1'", pointBackgroundColor="'rgba(0,0,0,0)'", pointBorderColor="'rgba(0,0,0,0)'")
mychart.set_params(JSinline = 0, ylabel = 'Median penalty amount per year', xlabel='Year',
	scaleBeginAtZero=0)

mychart.jekyll_write('../docs/_includes/charts/MADEP_enforcement_fine_avg_bootstrap.html')


#############################
## Show change in ACOPs over time
#############################

s_data_g = s_data.groupby(['Year'])
s_data_g_acop = s_data_g.apply(lambda x: np.mean((x['order_consent order']) & (x['Fine'] > 0)) / np.mean(x['order_consent order'])) * 100

## Establish chart
mychart = chartjs.chart("DEP ACOPs Per Year", "Line", 640, 480)
mychart.set_labels(s_data_g_acop.index.values.tolist())
mychart.add_dataset(
	s_data_g_acop.values.tolist(), 
	'Consent orders with penalties',
	backgroundColor="'"+color_cycle[0]+"'",
	stack="'annual'", yAxisID= "'y-axis-0'", fill = "false")
mychart.set_params(JSinline = 0, ylabel = 'Enforcements with financial penalties (% of annual total consent orders)', xlabel='Year',
	scaleBeginAtZero=0)

mychart.jekyll_write('../docs/_includes/charts/MADEP_enforcement_ACOP_byyear.html')


