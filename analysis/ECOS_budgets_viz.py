import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import chartjs
import matplotlib as mpl
color_cycle = [c['color'] for c in list(mpl.rcParams['axes.prop_cycle'])]

import locale
locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')

# ---------------------------------------------------------------------------
# EPA Region groupings for legend clustering
# ---------------------------------------------------------------------------
EPA_REGIONS = [
    ('Region 1 – New England',      ['Connecticut', 'Maine', 'Massachusetts', 'New Hampshire', 'Rhode Island', 'Vermont']),
    ('Region 2 – NY/NJ/PR',         ['New Jersey', 'New York', 'Puerto Rico']),
    ('Region 3 – Mid-Atlantic',     ['Delaware', 'District of Columbia', 'Maryland', 'Pennsylvania', 'Virginia', 'West Virginia']),
    ('Region 4 – Southeast',        ['Alabama', 'Florida', 'Georgia', 'Kentucky', 'Mississippi', 'North Carolina', 'South Carolina', 'Tennessee']),
    ('Region 5 – Great Lakes',      ['Illinois', 'Indiana', 'Michigan', 'Minnesota', 'Ohio', 'Wisconsin']),
    ('Region 6 – South Central',    ['Arkansas', 'Louisiana', 'New Mexico', 'Oklahoma', 'Texas']),
    ('Region 7 – Central',          ['Iowa', 'Kansas', 'Missouri', 'Nebraska']),
    ('Region 8 – Mountain',         ['Colorado', 'Montana', 'North Dakota', 'South Dakota', 'Utah', 'Wyoming']),
    ('Region 9 – Pacific/Southwest',['Arizona', 'California', 'Hawaii', 'Nevada']),
    ('Region 10 – Northwest',       ['Alaska', 'Idaho', 'Oregon', 'Washington']),
    ('Territories',                 ['Northern Mariana Islands']),
]

# Reverse mapping: state → region label
_STATE_TO_REGION = {
    state: region
    for region, states in EPA_REGIONS
    for state in states
}

# States shown by default (visible on load)
_DEFAULT_VISIBLE = {'Massachusetts', 'New Hampshire', 'Vermont', 'Maine', 'Rhode Island'}


# JS snippet injected into every chart: makes region-header legend entries
# non-clickable and visually distinct (no colored box, italic text).
_REGION_LEGEND_JS = """\
;(function() {
    try {
        var origGenLabels = (Chart.defaults.plugins.legend.labels || {}).generateLabels;
        if (!origGenLabels) return;
        chart_data.options.plugins.legend.labels = {
            generateLabels: function(chart) {
                var items = origGenLabels(chart);
                items.forEach(function(item) {
                    var ds = chart.data.datasets[item.datasetIndex];
                    if (ds && ds._isRegionHeader) {
                        item.fillStyle   = 'transparent';
                        item.strokeStyle = 'transparent';
                        item.lineWidth   = 0;
                        item.hidden      = false;
                        item.fontStyle   = 'italic';
                    }
                });
                return items;
            }
        };
        chart_data.options.plugins.legend.onClick = function(e, legendItem, legend) {
            var ds = legend.chart.data.datasets[legendItem.datasetIndex];
            if (ds && ds._isRegionHeader) return;
            Chart.defaults.plugins.legend.onClick.call(this, e, legendItem, legend);
        };
        chart_data.options.plugins.legend.onHover = function(e, legendItem, legend) {
            var ds = legend.chart.data.datasets[legendItem.datasetIndex];
            e.native.target.style.cursor = (ds && ds._isRegionHeader) ? 'default' : 'pointer';
        };
        chart_data.options.plugins.legend.onLeave = function(e, legendItem, legend) {
            e.native.target.style.cursor = 'default';
        };
    } catch(err) { /* legend customisation failed, fall back to default */ }
})();
"""


def safe_cast(x, to_type=int):
	y = []
	for xx in x:
		try:
			y += [to_type(xx)]
		except:
			pass
	return np.array(y)


def _add_datasets_by_region(mychart, states_in_data, get_vals_fn, ECOS_years):
	"""Add datasets sorted by EPA region with region-header spacers between groups."""
	null_data = [None] * len(ECOS_years)
	states_set = set(states_in_data)

	all_sorted_states = [
		s for _, region_states in EPA_REGIONS for s in region_states if s in states_set
	]
	unregioned = sorted(s for s in states_set if s not in _STATE_TO_REGION)
	all_sorted_states += unregioned

	color_idx = {state: i for i, state in enumerate(all_sorted_states)}

	for region_label, region_states in EPA_REGIONS:
		states_here = [s for s in region_states if s in states_set]
		if not states_here:
			continue
		mychart.add_dataset(
			null_data,
			region_label,
			backgroundColor="'transparent'",
			borderColor="'transparent'",
			borderWidth=0,
			pointRadius=0,
			hidden='false',
			_isRegionHeader='true',
		)
		for state in states_here:
			ci = color_idx[state]
			vals_list, color_str = get_vals_fn(state, ci)
			mychart.add_dataset(
				vals_list,
				state,
				backgroundColor=f"'{color_str}'",
				borderColor=f"'{color_str}'",
				stack="'annual'", yAxisID="'y'", fill="false",
				hidden='false' if state in _DEFAULT_VISIBLE else 'true',
			)

	for state in unregioned:
		ci = color_idx[state]
		vals_list, color_str = get_vals_fn(state, ci)
		mychart.add_dataset(
			vals_list,
			state,
			backgroundColor=f"'{color_str}'",
			borderColor=f"'{color_str}'",
			stack="'annual'", yAxisID="'y'", fill="false",
			hidden='true',
		)


def generate_charts(engine, prefix=''):
	"""Generate ECOS budget charts with optional filename prefix.

	Parameters
	----------
	engine : sqlalchemy.engine.Engine
		Database connection engine
	prefix : str, default ''
		Prefix to add to all output chart filenames (e.g., 'dash_')
	"""

	#############################
	## Load data
	#############################

	## Get ECOS state budget data
	s_data = pd.read_sql_query('SELECT * FROM ECOS_budgets', engine)
	ECOS_years = np.unique(safe_cast(s_data.Year.values)).astype(str)

	## Get DEP funding data
	f_data = pd.read_sql_query('SELECT * FROM MassBudget_summary', engine)
	f_data.index = f_data.Year

	## Get Census population data
	statepop_data = pd.read_sql_query('SELECT * FROM Census_statepop', engine)

	## Get DEP funding data
	inf_data = pd.read_sql_query('SELECT * FROM SSAWages', engine)
	inf_data.index = inf_data.Year.astype(str)
	inf_target = '2024'
	## Restrict to relevant years and calculate correction factors (2024 dollars)
	inf_data_sel = inf_data.reindex(ECOS_years)
	inf_data_sel['correct'] = inf_data.loc[inf_target, 'AWI'] / inf_data_sel['AWI']

	## Establish file to export facts
	fact_file = '../docs/data/facts_ECOSbudgets.yml'
	with open(fact_file, 'w') as f: f.write('')


	#############################
	## Show total budget per year by state
	#############################

	sel = (s_data['BudgetDetail']=="Environmental Agency Budget") & s_data.Year.isin(ECOS_years.astype(str))
	s_data_g = s_data[sel].groupby('State')
	states_budget = list(s_data_g.groups.keys())

	def get_budget_vals(state, ci):
		vals = pd.to_numeric(s_data_g.get_group(state).set_index('Year').reindex(ECOS_years).value, errors='coerce') * inf_data_sel['correct'] / 1e6
		vals_list = [float(v) if pd.notna(v) else np.nan for v in vals.values]
		return vals_list, (color_cycle * 10)[ci]

	mychart = chartjs.chart("ECOS Budgets by State Per Year", "Line", 640, 650)
	mychart.set_labels(ECOS_years)
	_add_datasets_by_region(mychart, states_budget, get_budget_vals, ECOS_years)
	mychart.add_extra_code(_REGION_LEGEND_JS)
	mychart.set_params(js_inline=0, ylabel='Reported Environmental Agency Budget (ECOS, $M)', xlabel='Year',
		scale_begin_at_zero=1)
	mychart.jekyll_write(f'../docs/_includes/charts/{prefix}ECOS_budget_peryear_bystate.html')


	#############################
	## Show per capita budget per year by state
	#############################

	def get_percap_vals(state, ci):
		budget = pd.to_numeric(
			s_data_g.get_group(state).set_index('Year').reindex(ECOS_years).value,
			errors='coerce',
		)
		pop_rows = statepop_data[statepop_data['State'] == state]
		if pop_rows.empty:
			vals_list = [np.nan] * len(ECOS_years)
		else:
			# statepop columns are year strings; build a Series indexed by year
			pop_cols = [c for c in pop_rows.columns if c in set(ECOS_years)]
			pop_series = pop_rows[pop_cols].iloc[0].reindex(ECOS_years).astype(float)
			vals = budget * inf_data_sel['correct'] / pop_series / 1e3
			vals_list = [float(v) if pd.notna(v) else np.nan for v in vals.values]
		return vals_list, (color_cycle * 10)[ci]

	mychart = chartjs.chart("ECOS Budget per capita by State Per Year", "Line", 640, 650)
	mychart.set_labels(ECOS_years)
	_add_datasets_by_region(mychart, states_budget, get_percap_vals, ECOS_years)
	mychart.add_extra_code(_REGION_LEGEND_JS)
	mychart.set_params(js_inline=0, ylabel='Reported Environmental Agency Budget (ECOS, $k per capita)', xlabel='Year',
		scale_begin_at_zero=1)
	mychart.jekyll_write(f'../docs/_includes/charts/{prefix}ECOS_budget_percap_peryear_bystate.html')


	#############################
	## Show federal contribution per year by state
	#############################

	sel = (s_data['BudgetDetail']=="Percent from Federal Government") & s_data.Year.isin(ECOS_years.astype(str))
	s_data_g_fed = s_data[sel].groupby('State')
	states_fed = list(s_data_g_fed.groups.keys())

	def get_fed_vals(state, ci):
		vals = pd.to_numeric(s_data_g_fed.get_group(state).set_index('Year').reindex(ECOS_years).value, errors='coerce')
		vals_list = [float(v) if pd.notna(v) else np.nan for v in vals.values]
		return vals_list, (color_cycle * 10)[ci]

	mychart = chartjs.chart("ECOS Federal Contribution by State Per Year", "Line", 640, 650)
	mychart.set_labels(ECOS_years)
	_add_datasets_by_region(mychart, states_fed, get_fed_vals, ECOS_years)
	mychart.add_extra_code(_REGION_LEGEND_JS)
	mychart.set_params(js_inline=0, ylabel='Environmental Agency Budget % from Federal Government (ECOS)', xlabel='Year',
		scale_begin_at_zero=1)
	mychart.jekyll_write(f'../docs/_includes/charts/{prefix}ECOS_fedcont_peryear_bystate.html')


if __name__ == '__main__':
	disk_engine = create_engine('sqlite:///../get_data/AMEND.db')
	generate_charts(disk_engine)
