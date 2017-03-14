"""
DEP salary data since 2004 is retrieved from:

https://qvs.visiblegovernment.us/QvAJAXZfc/notoolbar.htm?document=Clients/Massachusetts/Payroll/MA_Payroll.qvw&host=localhost&anonymous=true

To export: filter the view to DEP staff only, then right click on the spreadsheet and 'send to excel'
"""
import pandas as pd
import numpy as np
from matplotlib import pyplot as plt
import os

s_data = pd.read_excel('DEP_staff_data_2017-03-14.xls')
s_data = s_data.sort('Calendar Year')
s_data.groupby('Employee Name')['Calendar Year'].apply(lambda x: np.arange(len(x)))
s_data['Seniority'] = s_data.groupby('Employee Name').cumcount()

years = s_data['Calendar Year'].unique()

## Seniority decline over time
plt.figure()
((s_data.groupby('Calendar Year')['Seniority'].mean()) - np.arange(len(s_data['Calendar Year'].unique()))).plot()
plt.ylabel('Adjusted mean seniority since 2004')


## Assign seniority and role tags
major_levels = ['I', 'II', 'III', 'IV', 'V', 'VI']
major_titles = [['Environmental Analyst'], ['Environmental Engineer'], ['Program Coordinator'], ['Regional Planner', 'Planners'], ['Director', 'Dir '], ['Counsel'], ['Accountant'], ['Scientist'], ['Administrative Assistant'], ['Commissioner'], ['IT Pro'], ['Laboratory Supervisor'], ['Chemist'], ['Auditor'], ['Clerk']]

def identify_title(x):
	for title in major_titles:
		for t in title:
			if t.lower() in x.lower():
				return title[0]
				break
	return 'OTHER'

s_data['JobType'] = s_data['Job Title'].apply(identify_title)


def identify_level(x):
	for level in major_levels:
		if x.lower().endswith(' ' + level.lower()):
			return level
			break
	return 'NONE'

s_data['JobLevel'] = s_data['Job Title'].apply(identify_level)

## Sort in a reasonable way
s_data.sort(['Calendar Year','JobType','JobLevel'], inplace=1)

## Export
e_cols = [u'Calendar Year', u'Employee Name', u'Job Title', u'Earnings', u'JobType', u'JobLevel', u'Seniority']
s_data[e_cols].rename(columns = {d:d.replace(' ','') for d in e_cols}).to_csv('../docs/data/MADEP_staff.csv', index=0)
os.system('cp ../docs/data/MADEP_staff.csv ../docs/_data/MADEP_staff.csv')


## Report last update
with open('../docs/_data/ts_update_MADEP_staff.yml', 'w') as f:
	f.write('updated: 2017-03-14\n')


