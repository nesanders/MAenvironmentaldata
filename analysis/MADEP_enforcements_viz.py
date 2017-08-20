import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import chartjs
import json
import ast
import folium
from scipy.stats import pearsonr

import matplotlib as mpl
color_cycle = [c['color'] for c in list(mpl.rcParams['axes.prop_cycle'])]

import locale
locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
 
## Load database
disk_engine = create_engine('sqlite:///../get_data/AMEND.db')


## Get MADEP website enforcement data
s_data = pd.read_sql_query('SELECT * FROM MADEP_enforcement', disk_engine)
years = s_data.Year.unique()
s_data['municipality'] = s_data.municipality.apply(lambda x: [t.upper() for t in ast.literal_eval(x)])

## Get funding data
f_data = pd.read_sql_query('SELECT * FROM MassBudget_summary', disk_engine)
f_data.index = f_data.Year

## Get Census data
c_data = pd.read_sql_query('SELECT * FROM Census_ACS', disk_engine)
c_data.index = c_data.Subdivision.str.upper()

## Establish file to export facts
fact_file = '../docs/data/facts_DEPenforce.yml'
with open(fact_file, 'w') as f: f.write('')

## Geo data
geo_path = '../docs/assets/geo_json/'
geo_towns = geo_path+'TOWNSSURVEY_POLYM_geojson_simple.json'
geo_towns_dict = json.load(open(geo_towns))['features']
geo_out_path = '../docs/assets/maps/'



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
		(s_data_g.sum()[topic] / s_data_g.count()[topic].astype(float) * 100).tolist(), 
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
#s_data_g_acop = s_data_g.apply(lambda x: np.mean((x['order_consent order']) & (x['Fine'] > 0)) / np.mean(x['order_consent order'])) * 100
s_data_g_acop = s_data_g.apply(lambda x: 
		np.percentile(
			bootstrap(x.iloc[np.where(x['order_consent order'])]['Fine'].values > 0, np.mean)
			, [5,50,95], axis=0)
		) * 100

## Establish chart
mychart = chartjs.chart("DEP ACOPs Per Year", "Line", 640, 480)
mychart.set_labels(s_data_g_acop.index.values.tolist())
#mychart.add_dataset(
	#s_data_g_acop.values.tolist(), 
	#'Consent orders with penalties',
	#backgroundColor="'"+color_cycle[0]+"'",
	#stack="'annual'", yAxisID= "'y-axis-0'", fill = "false")
mychart.add_dataset(s_data_g_acop.apply(lambda x: x[1]).values.tolist(), 
	"Best estimate",
	backgroundColor="'rgba(50,100,100,0.8)'", yAxisID= "'y-axis-0'", borderWidth = 3, fill = 'false'  )
mychart.add_dataset(s_data_g_acop.apply(lambda x: x[0]).values.tolist(), 
	"Lower bound (5% limit)",
	backgroundColor="'rgba(50,50,50,0.3)'", yAxisID= "'y-axis-0'", borderWidth = 1, 
	fill = 'false', pointBackgroundColor="'rgba(0,0,0,0)'", pointBorderColor="'rgba(0,0,0,0)'")
mychart.add_dataset(s_data_g_acop.apply(lambda x: x[2]).values.tolist(), 
	"Upper bound (95% limit)",
	backgroundColor="'rgba(50,50,50,0.3)'", yAxisID= "'y-axis-0'", borderWidth = 1, fill = "'1'", pointBackgroundColor="'rgba(0,0,0,0)'", pointBorderColor="'rgba(0,0,0,0)'")
mychart.set_params(JSinline = 0, ylabel = 'Enforcements with financial penalties (% of annual total consent orders)', xlabel='Year',
	scaleBeginAtZero=0)

mychart.jekyll_write('../docs/_includes/charts/MADEP_enforcement_ACOP_byyear.html')


#############################
## Show variation by town
#############################

## Count enforcements per town
towns = sorted([geo_towns_dict[i]['properties']['TOWN'] for i in range(len(geo_towns_dict))])
town_count = {}
town_fines = {}
for town in towns:
	## Check if town appears in each row
	count = s_data.municipality.apply(lambda x: town in x)
	town_count[town] = count.sum()
	## tally enforcement penalties
	fines = s_data.apply(lambda x: x.Fine if town in x.municipality else 0, axis=1)
	town_fines[town] = fines.sum()

town_count = pd.Series(town_count)
town_fines = pd.Series(town_fines)

merge_census_df = pd.DataFrame(data={
	'Population': c_data['population_acs52014'].ix[towns].values,
	'Per capita income ($k)': c_data['per_capita_income_acs52014'].ix[towns].values / 1000,
	'DEP enforcements': town_count.ix[towns].values,
	'DEP penalties ($1,000)': town_fines.ix[towns].values / 1000,
	}, index=towns)


## Map total inspections
map_bytown = folium.Map(
	location=[42.29, -71.74], 
	zoom_start=8.2,
	tiles='cartodbpositron',
	)

## Draw choropleth
map_bytown.choropleth(
	geo_path=geo_towns, 
	data_out=geo_out_path+'EEADP_ins_data_total.json', 
	data=town_count,
	key_on='feature.properties.TOWN',
	legend_name='Total # of MA DEP enforcements reported',
	threshold_scale = [0,1.] + list(np.percentile(town_count, [50,90,95, 100])),
	fill_color='PuBu', fill_opacity=0.7, line_opacity=0.3, highlight=True,
	)

## Add statistics and top enforcement actions to each city
for i in range(len(geo_towns_dict)):
	town = geo_towns_dict[i]['properties']['TOWN']
	if town in towns:
		## Gather town data
		enforcements = merge_census_df['DEP enforcements'].ix[town]
		pop14 = merge_census_df['Population'].ix[town]
		top_enforcements = s_data[s_data.municipality.apply(lambda x: town in x)].sort_values('Fine', ascending=False)[['Date','Fine','Text']].values[:3]
		enforcement_summary = '<br>'.join(['<b>'+c[0]+', $%0.0f'%(0 if np.isnan(c[1]) else c[1])+'</b>: '+c[2] for c in top_enforcements])
		## Take average position of polygon points for marker center
		raw_coords = geo_towns_dict[i]['geometry']['coordinates']
		if np.ndim(raw_coords) == 2: # Take most complicated polygon if multiple are provided
			j = np.argmax([np.shape(raw_coords[i][0])[0] for i in range(len(raw_coords))])
			coords = raw_coords[j]
		elif np.ndim(raw_coords) == 3:
			coords = raw_coords
		else: 
			raise
		mean_pos = list(np.mean(coords, axis=1)[0])[::-1]
		## Add marker
		html="""
		<h1>{town}</h1>
		<p>Population (2014): {pop}<br>
		Total MA DEP enforcements reported since {enforcement_start}: {enforcements}</p>
		
		<p>Largest enforcements reported (by penalty):</p>
		<p>{enforcement_summary}</p>
		""".format(
				town=town, 
				pop=pop14, 
				enforcements=enforcements, 
				enforcement_summary=enforcement_summary, 
				enforcement_start=s_data.Year.min()
			)
		iframe = folium.IFrame(html=html, width=400, height=200)
		popup = folium.Popup(iframe, max_width=500)
		folium.RegularPolygonMarker(
				location=mean_pos, 
				popup=popup, 
				number_of_sides=4, 
				radius=6, 
				color='green',
				fill_color='green',
			).add_to(map_bytown)

## Save to html
map_bytown.save(geo_out_path+'MADEP_enforcements_town_total.html')


#############################
## Compare census data to town characteristics
#############################

"""
## Matplotlib plots for testing purposes
from matplotlib import pyplot as plt
from statsmodels.nonparametric.smoothers_lowess import lowess

## counts
x = merge_census_df['Per capita income ($k)'].values
y = merge_census_df['DEP enforcements'].values / merge_census_df['Population'].values * 1e5
pxy = lowess(np.log10(y), x, frac=0.2)

#x_bins = np.linspace(min(x), max(x), 10)
x_bins = np.nanpercentile(x, list(np.linspace(0,100,11)))
x_bin_id = pd.cut(x, x_bins, labels=False)
y_bin = [np.mean((y)[x_bin_id == i]) for i in range(len(x_bins) - 1)]
dy_bin = [np.std((y)[x_bin_id == i]) / np.sqrt(sum(x_bin_id == i)) for i in range(len(x_bins) - 1)]

plt.figure()
plt.plot(x, y, '.')
plt.semilogy()
plt.plot(pxy[:,0], 10**pxy[:,1], lw=3)
plt.errorbar([np.mean([x_bins[i], x_bins[i+1]]) for i in range(len(x_bins) - 1)], y_bin, yerr = dy_bin, marker='o')
plt.xlabel('Per Capita Income ($1,000)')
plt.ylabel('Per Capita Enforcements (per 100,000)')

## penalties
x = merge_census_df['Per capita income ($k)']
y = (merge_census_df['DEP penalties ($1,000)']) / (merge_census_df['Population']/1e5)
pxy = lowess(np.log10(y), x, frac=0.2)

plt.figure()
plt.plot(x, y, '.')
plt.semilogy()
plt.plot(pxy[:,0], 10**pxy[:,1], lw=3)
plt.xlabel('Per Capita Income ($1,000)')
plt.ylabel('Per Capita Enforcement Penalties ($1,000 per 100,000)')
"""

#############################
## Enforcement count per capita by town income
#############################

## Lookup base values
x = merge_census_df['Per capita income ($k)'].values
y = merge_census_df['DEP enforcements'].values / merge_census_df['Population'].values * 1e5
l = merge_census_df.index.values

## Calculate binned values
x_bins = np.nanpercentile(x, list(np.linspace(0,100,8)))
x_bin_cent = [np.mean([x_bins[i], x_bins[i+1]]) for i in range(len(x_bins) - 1)]
x_bin_id = pd.cut(x, x_bins, labels=False)
y_bin = np.array([np.mean((y)[x_bin_id == i]) for i in range(len(x_bins) - 1)])
dy_bin = np.array([np.std((y)[x_bin_id == i]) / np.sqrt(sum(x_bin_id == i)) for i in range(len(x_bins) - 1)])

## Establish chart
mychart = chartjs.chart("DEP Enforcements per capita versus town income", "Scatter", 640, 480)

## Add individual town dataset
mychart.add_dataset(
	np.array([x, y]).T, 
	dataset_label="Individual towns",
	backgroundColor="'rgba(50,50,50,0.5)'",
	showLine = "false",
	yAxisID= "'y-axis-0'",
	fill="'false'",
	hidden="'true'"
	)
## Add binned dataset
mychart.add_dataset(
	np.array([x_bin_cent, y_bin]).T, 
	dataset_label="Average (binned)",
	backgroundColor="'rgba(50,50,200,1)'",
	showLine = "true",
	borderColor="'rgba(50,50,200,1)'",
	borderWidth=3,
	yAxisID= "'y-axis-0'",
	fill="'false'",
	pointRadius=6,
	)
## Add uncertainty contour
mychart.add_dataset(np.array([x_bin_cent, y_bin - 1.65 * dy_bin]).T, 
	"Average lower bound (5% limit)",
	backgroundColor="'rgba(50,50,200,0.3)'", yAxisID= "'y-axis-0'", borderWidth = 1, 
	fill = 'false', pointBackgroundColor="'rgba(50,50,200,0.3)'", pointBorderColor="'rgba(50,50,200,0.3)'")
mychart.add_dataset(np.array([x_bin_cent, y_bin + 1.65 * dy_bin]).T, 
	"Average upper bound (95% limit)",
	backgroundColor="'rgba(50,50,200,0.3)'", yAxisID= "'y-axis-0'", borderWidth = 1, fill = "'2'", pointBackgroundColor="'rgba(50,50,200,0.3)'", pointBorderColor="'rgba(50,50,200,0.3)'")
## Set overall chart parameters
mychart.set_params(
	JSinline = 0, 
	ylabel = 'MA DEP enforcements per 100,000 residents', 
	xlabel='Per capita income ($k)',
	yaxis_type='logarithmic',	
	y2nd = 0,
	scaleBeginAtZero=0,
	custom_tooltips = """
                mode: 'single',
                callbacks: {
                    label: function(tooltipItems, data) { 
						var town = ma_towns[tooltipItems.index];
						if (tooltipItems.datasetIndex == 0) {
							return [town,'Enforcements per 100,000 residents: ' + tooltipItems.yLabel,'Per capita income ($k): ' + tooltipItems.xLabel];
						};
                    }
				}
"""
	) 
## Update logarithm tick format as in https://github.com/chartjs/Chart.js/issues/3121
mychart.add_extra_code(
"""
Chart.scaleService.updateScaleDefaults('logarithmic', {
  ticks: {
	autoSkip: true,
	autoSkipPadding: 100,
	callback: function(tick, index, ticks) {
      return tick.toLocaleString()
    }
  }
});
""")
## Add town dataset
mychart.add_extra_code(
	'var ma_towns = ["' + '","'.join(l) + '"];')

mychart.jekyll_write('../docs/_includes/charts/MADEP_enforcement_bytown_income.html')


#############################
## Enforcements per capita - extreme value tables
#############################

## Top cities
merge_census_df['Enforcements per capita (per 100,000 people)'] = merge_census_df['DEP enforcements']/merge_census_df['Population'] * 1e5
merge_census_df['Penalties per capita ($1M per 100,000 people)'] = (merge_census_df['DEP penalties ($1,000)'] / 1000) / (merge_census_df['Population']/1e5)

merge_census_df[merge_census_df.Population>25000].sort_values('Enforcements per capita (per 100,000 people)').dropna().tail()
merge_census_df[merge_census_df.Population>25000].sort_values('Penalties per capita ($1M per 100,000 people)').dropna().tail()


