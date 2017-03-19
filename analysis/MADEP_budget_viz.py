import pandas as pd
import chartjs

import matplotlib as mpl
color_cycle = [c['color'] for c in list(mpl.rcParams['axes.prop_cycle'])]

## Load dataset
data_summary = pd.read_csv('../docs/data/MassBudget_environmental_summary.csv')
data_summary.sort_values(by='Year', inplace=1)

## Establish chart
mychart = chartjs.chart("DEP budget data", "Line", 640, 480)
mychart.set_labels(data_summary['FiscalYear'].values.tolist())
mychart.set_params(JSinline = 0, ylabel = 'Total Budget ($M)', xlabel='Fiscal Year')

mychart.add_dataset(
	(data_summary['TotalBudget_noinf_float'].values/1e6).tolist(), "Total environmental budget\\n(not inflation adjusted)",
	borderDash = '[10,15]', borderColor = "'rgba(0,0,0,0.5)'", fill = "false",
	steppedLine = 'true',
	)

#mychart.add_dataset(
	#data_summary['TotalBudget_inf_float'].values.tolist(), "Inflation adjusted"
	#)
	
mychart.add_dataset(
	(data_summary['DEPAdministration_noinf_float'].values/1e6).tolist(), "DEP administration (not inflation adjusted)",
	borderDash = '[10,15]', borderColor = "'"+color_cycle[0]+"'", fill = "false",
	steppedLine = 'true',
	)

mychart.add_dataset(
	(data_summary['DEPAdministration_inf_float'].values/1e6).tolist(), "DEP administration (inflation adjusted)",
	borderColor = "'"+color_cycle[0]+"'", fill = "true",
	steppedLine = 'true',
	)



## Write out
#with open('../docs/_includes/charts/MADEP_budget_summary.html', 'w') as f:
	#f.write("{% raw  %}\n")
	#out = mychart.make_chart_full_html().split('\n')
	#out = [o for o in out if '<h2>' not in o and 'doctype html' not in o]
	#out = '\n'.join(out)
	#f.write(out)
	#f.write("{% endraw  %}\n")

mychart.jekyll_write('../docs/_includes/charts/MADEP_budget_summary.html')
	
