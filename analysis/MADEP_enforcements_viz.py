from __future__ import absolute_import
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import chartjs
import json
import ast
from scipy.stats import pearsonr

import matplotlib as mpl

from cso_maps import make_enforcement_map

color_cycle = [c['color'] for c in list(mpl.rcParams['axes.prop_cycle'])]

import locale
locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')


def generate_charts(engine, prefix=''):
	"""Generate DEP enforcement charts with optional filename prefix.

	Parameters
	----------
	engine : sqlalchemy.engine.Engine
		Database connection engine
	prefix : str, default ''
		Prefix to add to all output chart filenames (e.g., 'dash_')
	"""

	## Get enforcement data - use hybrid approach:
	## - MAEEADP_Enforcement (EEA Data Portal) for overall counts/fines (has data through 2026)
	## - MADEP_enforcement for topic breakdown (has proper topic columns through 2017)
	try:
		s_data = pd.read_sql_query('SELECT * FROM MAEEADP_Enforcement', engine)
		# Extract year from EnforcementDate
		s_data['Year'] = pd.to_datetime(s_data['EnforcementDate'], errors='coerce').dt.year
		# Rename/create columns to match expected schema
		s_data.rename(columns={'FacilityName': 'facility', 'PenaltyAssessed': 'Fine'}, inplace=True)
		s_data['Fine'] = s_data['Fine'].fillna(0)
		# Set municipality to empty list
		s_data['municipality'] = [[]] * len(s_data)
		# Add zero topic columns (will be overwritten with MADEP data later)
		for col in ['order_consent order', 'order_wetlands', 'order_water supply', 'law_chapter 91', 'law_npdes', 'order_stormwater']:
			s_data[col] = 0

		# Filter out routine administrative notices (not reflective of enforcement effort)
		# Notice Of Non-Compliance records (78% of data) are routine notices issued at high volume;
		# keep only substantive enforcement actions (consent orders, unilateral orders, penalty notices)
		ROUTINE_NOTICE_TYPES = {
			'Notice Of Non-Compliance',
			'Field Notice Of Non Compliance',
			'BOIL ORDER',
			'Federal Administrative Order Against PWS',
			'Federal Notice Of Noncompliance Against PWS',
		}
		s_data_before_filter = len(s_data)
		s_data = s_data[~s_data['EnforcementType'].isin(ROUTINE_NOTICE_TYPES)].copy()
		print(f'Using MAEEADP_Enforcement data (EEA Data Portal): {len(s_data)} substantive enforcement records (filtered from {s_data_before_filter} total) from {s_data.Year.min()}-{s_data.Year.max()}')

		# Also load MADEP_enforcement for topic breakdown (which has proper topic columns)
		s_data_madep = pd.read_sql_query('SELECT * FROM MADEP_enforcement', engine)
		s_data_madep['municipality'] = s_data_madep.municipality.apply(lambda x: [t.upper() for t in ast.literal_eval(x)])
		print(f'Also loaded MADEP_enforcement for topic breakdown: {len(s_data_madep)} records through {s_data_madep.Year.max()}')
	except Exception as e:
		print(f'Could not load MAEEADP_Enforcement: {e}. Using MADEP_enforcement only.')
		s_data = pd.read_sql_query('SELECT * FROM MADEP_enforcement', engine)
		s_data['municipality'] = s_data.municipality.apply(lambda x: [t.upper() for t in ast.literal_eval(x)])
		s_data_madep = s_data

	## Get funding data
	f_data = pd.read_sql_query('SELECT * FROM MassBudget_summary', engine)
	f_data.index = f_data.Year.astype(int)

	# Filter enforcement data to years that have budget data
	budget_years = set(f_data.index.astype(int).unique())
	s_data = s_data[s_data['Year'].astype(int).isin(budget_years)].copy()
	s_data['Year'] = s_data['Year'].astype(int)
	print(f'Filtered to years with budget data: {sorted(budget_years)}')

	# Recalculate years after filtering
	years = sorted(s_data.Year.unique())

	## Get Census data
	c_data = pd.read_sql_query('SELECT * FROM Census_ACS', engine)
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

	s_data_g = s_data.groupby(['Year']).count().iloc[:,1]

	## Establish chart
	mychart = chartjs.chart("Overall DEP Enforcement", "Bar", 640, 480)
	# Format year labels as integers (e.g., "2024" not "2024.0")
	mychart.set_labels([str(int(y)) for y in s_data_g.index.values])
	mychart.add_dataset(s_data_g.values.tolist(),
		"Number of enforcements",
		backgroundColor="'rgba(50,50,200,0.8)'",
		stack="'annual'", yAxisID= "'y-axis-0'",)
	mychart.set_params(JSinline = 0, ylabel = 'Total reported enforcement actions', xlabel='Year',
		scaleBeginAtZero=1)

	mychart.jekyll_write(f'../docs/_includes/charts/{prefix}MADEP_enforcement_overall.html')



	#############################
	## Show total penalties per year
	#############################

	s_data_g = s_data.groupby(['Year']).sum()

	## Establish chart
	mychart = chartjs.chart("Overall DEP Enforcement Penalties ($M)", "Bar", 640, 480)
	# Format year labels as integers
	mychart.set_labels([str(int(y)) for y in s_data_g.index.values])
	mychart.add_dataset((s_data_g.Fine/1e6).tolist(),
		"Reported penalties",
		backgroundColor="'rgba(50,50,200,0.8)'",
		stack="'annual'", yAxisID= "'y-axis-0'",)
	mychart.set_params(JSinline = 0, ylabel = 'Sum of reported penalties ($M)', xlabel='Year',
		scaleBeginAtZero=1)

	mychart.jekyll_write(f'../docs/_includes/charts/{prefix}MADEP_enforcement_fines_overall.html')


	s_data_g_na = s_data.dropna().groupby(['Year']).Fine

	## Establish stacked chart: top N individual penalties + "Other" bucket
	TOP_N = 10
	mychart = chartjs.chart("Individual DEP Enforcement Penalties ($M)", "Bar", 640, 480)
	mychart.set_labels(s_data_g.index.values.tolist())
	rgba_list = [
		'rgba(166,206,227)',
		'rgba(31,120,180)',
		'rgba(178,223,138)',
		'rgba(51,160,44)'
		]
	for i in range(TOP_N):
		def get_sorted_i(x, _i=i):
			s = sorted(x.values)[::-1]
			return s[_i] if _i < len(s) else 0
		mychart.add_dataset((s_data_g_na.apply(get_sorted_i)/1e6).tolist(),
			"Rank #{} penalty of the year".format(i + 1),
			backgroundColor="'"+rgba_list[np.mod(i, len(rgba_list))]+"'",)
	# "Other" bucket: sum of all penalties beyond rank TOP_N
	def get_other(x):
		s = sorted(x.values)[::-1]
		return sum(s[TOP_N:]) if len(s) > TOP_N else 0
	mychart.add_dataset((s_data_g_na.apply(get_other)/1e6).tolist(),
		"All other penalties (ranks {0}+)".format(TOP_N + 1),
		backgroundColor="'rgba(200,200,200,0.7)'",)
	mychart.set_params(JSinline = 0, ylabel = 'Sum of reported penalties ($M)', xlabel='Year',
		scaleBeginAtZero=1, stacked=1, legend=0)

	mychart.jekyll_write(f'../docs/_includes/charts/{prefix}MADEP_enforcement_fines_overall_stacked.html')



	#############################
	## Show enforcements per year versus budget
	#############################

	s_data_g = s_data.groupby(['Year']).count().iloc[:,1]

	## Establish chart
	mychart = chartjs.chart("DEP Enforcements versus budget", "Line", 640, 480)
	# Format year labels as integers
	mychart.set_labels([str(int(y)) for y in s_data_g.index.values])
	mychart.add_dataset(s_data_g.values.tolist(), "Number of enforcements",
		backgroundColor="'rgba(50,50,50,0.5)'",
		type="'line'", fill = "false",
		borderWidth = 2,
		stack="'annual'", yAxisID= "'y-axis-0'")
	mychart.add_dataset((f_data['DEPAdministration_inf_float'].loc[years]/1e6).values.tolist(), "DEP administrative budget",
		borderColor = "'"+color_cycle[1]+"'", fill = "false",
		borderWidth = 2,
		stack="'annual'", type="'line'", yAxisID= "'y-axis-1'")
	mychart.set_params(JSinline = 0, ylabel = 'Number of enforcements', xlabel='Year',
		y2nd = 1, y2nd_title = 'Funding level ($M, 2024 dollars)',
		scaleBeginAtZero=0)

	mychart.jekyll_write(f'../docs/_includes/charts/{prefix}MADEP_enforcement_vsbudget.html')

	## Output correlation level
	pr = pearsonr(s_data_g.values, (f_data['DEPAdministration_inf_float'].loc[years]/1e6).values)
	with open(fact_file, 'a') as f:
		f.write('cor_enforcement_funding: %0.0f'%(pr[0]*100)+'\n')


	#############################
	## Show enforcement fractions by topic per year
	## Use MADEP_enforcement data since it has proper topic columns
	#############################

	s_data_g = s_data_madep.groupby(['Year'])
	topics = [d for d in s_data_madep.columns if d.startswith('order_') or d.startswith('law_')]

	## Establish chart
	mychart = chartjs.chart("DEP Enforcements by Topic Per Year", "Line", 640, 480)
	# Format year labels as integers
	mychart.set_labels([str(int(y)) for y in s_data_g.count().index.values])
	# Topics to show by default
	visible_topics = ['order_wetlands', 'order_stormwater', 'order_water supply', 'law_npdes', 'law_chapter 91']
	for i,topic in enumerate(topics):
		mychart.add_dataset(
			(s_data_g.sum()[topic] / s_data_g.count()[topic].astype(float) * 100).tolist(),
			topic.split('_')[1].strip().title(),
			backgroundColor="'"+(color_cycle*10)[i]+"'",
			stack="'annual'", yAxisID= "'y-axis-0'", fill = "false",
			hidden = 'false' if topic in visible_topics else 'true')
	mychart.set_params(JSinline = 0, ylabel = 'Reported enforcement actions (% of annual total)', xlabel='Year',
		scaleBeginAtZero=1)

	mychart.jekyll_write(f'../docs/_includes/charts/{prefix}MADEP_enforcement_bytopic.html')


	#############################
	## Show enforcement actions by type per year (using MAEEADP data through 2026)
	## Uses substantive enforcement types after filtering routine notices
	#############################

	s_data_enftype = s_data.groupby(['Year', 'EnforcementType']).size().unstack(fill_value=0)

	## Map full enforcement type names to shorter labels
	enforce_type_labels = {
		'Administrative Consent Order With Penalty': 'ACO w/ Penalty',
		'Administrative Consent Order No Penalty': 'ACO w/o Penalty',
		'Unilateral Administrative Order': 'Unilateral Order',
		'Penalty Assessment Notice': 'Penalty Notice',
		'Reporting Penalty Assessment Notice': 'Reporting Penalty',
		'Demand Action': 'Demand Action',
		'FEDERAL ADMINISTRATIVE ORDER AGAINST PWS': 'Federal ACO (PWS)',
		'FEDERAL NOTICE OF NONCOMPLIANCE AGAINST PWS': 'Federal NOC (PWS)',
	}

	## Establish chart
	mychart = chartjs.chart("DEP Enforcements by Action Type", "Bar", 640, 480)
	# Format year labels as integers
	mychart.set_labels([str(int(y)) for y in s_data_enftype.index.values])

	# Add datasets for each enforcement type with distinct colors
	color_palette = [
		'rgba(31,120,180,0.8)',
		'rgba(166,206,227,0.8)',
		'rgba(51,160,44,0.8)',
		'rgba(178,223,138,0.8)',
		'rgba(227,26,28,0.8)',
		'rgba(253,191,111,0.8)',
		'rgba(202,178,214,0.8)',
		'rgba(106,61,154,0.8)',
	]

	for i, enftype in enumerate(s_data_enftype.columns):
		label = enforce_type_labels.get(enftype, enftype)
		color = color_palette[i % len(color_palette)]
		mychart.add_dataset(s_data_enftype[enftype].values.tolist(),
			label,
			backgroundColor="'"+color+"'",
			stack="'annual'", yAxisID="'y-axis-0'")

	mychart.set_params(JSinline = 0, ylabel = 'Number of enforcement actions', xlabel='Year',
		scaleBeginAtZero=1, stacked=1)

	mychart.jekyll_write(f'../docs/_includes/charts/{prefix}MADEP_enforcement_bytype.html')


	## Export some facts (using MADEP data for topic facts).
	## Exclude most recent year from averages, as it will be partial.
	with open(fact_file, 'a') as f:
		f.write('yearly_ch91: %0.1f'%(s_data_g.sum()['law_chapter 91'][:-1].mean())+'\n')
		f.write('yearly_npdes: %0.1f'%(s_data_g.sum()['law_npdes'][:-1].mean())+'\n')
		f.write('yearly_avg_consentorder: %0.0f'%(s_data_g['order_consent order'].mean()[:-1].mean() * 100)+'\n')
		if 2016 in s_data_g['order_wetlands'].mean().index and s_data_g['order_wetlands'].mean().max() > 0:
			f.write('yearly_avg_delta2016_wetlands: %0.0f'%(
				(1 - s_data_g['order_wetlands'].mean().loc[2016] / s_data_g['order_wetlands'].mean().max()) * 100
				)+'\n')
		if 2004 in s_data_g['order_water supply'].mean().index:
			f.write('yearly_2004_watersupply: %0.1f'%(s_data_g['order_water supply'].mean().loc[2004] * 100)+'\n')
		if 2016 in s_data_g['order_water supply'].mean().index:
			f.write('yearly_2016_watersupply: %0.1f'%(s_data_g['order_water supply'].mean().loc[2016] * 100)+'\n')


if __name__ == '__main__':
	disk_engine = create_engine('sqlite:///../get_data/AMEND.db')
	generate_charts(disk_engine)
