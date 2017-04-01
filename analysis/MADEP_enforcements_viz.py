import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import chartjs
from scipy.stats import pearsonr

import matplotlib as mpl
color_cycle = [c['color'] for c in list(mpl.rcParams['axes.prop_cycle'])]

 
## Load database
disk_engine = create_engine('sqlite:///../get_data/MERDR.db')


## Get MADep website data
s_data = pd.read_sql_query('SELECT * FROM MADEP_enforcement', disk_engine)
years = s_data.Year.unique()



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



