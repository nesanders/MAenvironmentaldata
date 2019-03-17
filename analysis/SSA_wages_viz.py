from __future__ import absolute_import
import pandas as pd
import chartjs

## Load dataset
ssadata = pd.read_csv('../docs/data/SSAWages_2019-03-17.csv')

## Establish chart
mychart = chartjs.chart("SSA wage data", "Line", 640, 480)
mychart.set_labels(ssadata.Year.values.tolist())
mychart.add_dataset(ssadata['AWI'].values.tolist(), "AWI")
mychart.set_params(
	fillColor = "rgba(220,220,220,0.5)", strokeColor = "rgba(220,220,220,0.8)", 
	highlightFill = "rgba(220,220,220,0.75)", highlightStroke = "rgba(220,220,220,1)",
	JSinline = 0, ylabel = 'AWI', xlabel='Year')

## Write out
#with open('../docs/_includes/charts/SSAwages.html', 'w') as f:
	#f.write("{% raw  %}\n")
	#out = mychart.make_chart_full_html().split('\n')
	#out = [o for o in out if '<h2>' not in o and 'doctype html' not in o]
	#out = '\n'.join(out)
	#f.write(out)
	#f.write("{% endraw  %}\n")
	
mychart.jekyll_write('../docs/_includes/charts/SSAwages.html')

