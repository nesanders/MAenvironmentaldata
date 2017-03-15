import pandas as pd
import numpy as np
from matplotlib.ticker import FixedLocator, MaxNLocator,  MultipleLocator
from matplotlib import pyplot as plt
from matplotlib import cm


s_data = pd.read_csv('../docs/data/MADEP_staff.csv')

ssa_wage_df = pd.read_csv('../docs/data/SSAWages_2016-12-09.csv')
## Temporary insertion for 2016 assuming no inflation
ssa_wage_df = ssa_wage_df.append(ssa_wage_df.iloc[-1])
ssa_wage_df.Year.iloc[-1] = 2016

ssa_wage_df.index = ssa_wage_df.Year.astype(int)

years = s_data.CalendarYear.unique()

## Show average seniority per job type
s_data_gj = s_data.groupby(['JobType','CalendarYear'])
sel_titles = [['Environmental Analyst'], ['Environmental Engineer'], ['Program Coordinator'], ['Regional Planner', 'Planners'], ['Counsel']]
wage_adjust = ssa_wage_df.ix[years].AWI.values / ssa_wage_df.ix[2015].AWI
fig, axgrid = plt.subplots(int(np.ceil(len(sel_titles)/3.)), 3, sharex='all', sharey='all', figsize=(8, 8))
axs = axgrid.flatten()
for i,jt in enumerate(sel_titles):
	y = np.zeros(len(years))
	c = np.zeros(len(years))
	try:
		y += s_data_gj.Earnings.sum().ix[(jt[0])].ix[years].replace(np.nan, 0).values
		c += s_data_gj.Earnings.count().ix[(jt[0])].ix[years].replace(np.nan, 0).values
	except pd.core.indexing.IndexingError:
		pass
	axs[i].plot(years, y / wage_adjust / 1000. / c.astype(float), lw=2, color='k', marker='o', label='2015 adjusted dollars')
	axs[i].plot(years, y / 1000. / c.astype(float), lw=1, color='.5', ls='dashed', label='Absolute dollars')
	axs[i].set_title(jt[0], fontsize=9)
	axs[i].xaxis.set_major_locator(MultipleLocator(4))
	axs[i].xaxis.set_minor_locator(MultipleLocator(1))

for k in range(i + 1, len(axs)):
	axs[k].set_visible(0)

axs[i].set_xlim(2003, 2017)
axs[i].legend(prop={'size':10}, loc='center left', bbox_to_anchor=(1, 0.5), title='Level')
plt.figtext(0.05, 0.5, 'Average earnings per year ($k)', rotation='vertical', va='center')
plt.legend()

plt.savefig('../docs/assets/figures/MADEP_staff_earnings_by_role.png', dpi=150)
