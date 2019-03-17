from __future__ import absolute_import
from __future__ import print_function
import pandas as pd
import numpy as np
import us,os
from unidecode import unidecode
from six.moves import range
all_states = [s.name for s in us.STATES]

import csv

## Tables from each PDF published by ECOS extracted using Tabula and manually edited to assure consistency
## * http://tabula.technology/
## Note - ECOS_state env budget, green report, 2009-2011.pdf not parsing correctly
## Provide in chronological order
ECOS_files = [
	'ECOS/tabula-ECOS_state env budget, green report, 2009-2011_manualedit.csv',
	'ECOS/tabula-ECOS_state env budget, green report, 2011-2013_manualedit.csv',
	'ECOS/tabula-Budget-Report-FINAL-3_15_17-Final-4_manualedit.csv',
	]

print("""
NOTE: ECOs reports state the following caveats,
* 2009-2011 report, "Thirty-seven ECOS member agencies responded to the ECOS budget survey in May 2010 - 36 states and Puerto Rico, hereinafter referred to as 'states.'... ECOS omitted data provided by Michigan, New Hampshire, Pennsylvania, and West Virginia..."
* 2011 - 2013 report, "We were unable to obtain data for Florida, Iowa, and New Mexico."
* 2015 - 2017, "Louisiana, New Jersey, New Mexico, and North Carolina did not report information."
""")

## Parse each ECOS file
state_df = {}
for ecos_file in ECOS_files:
	reader = csv.reader(open(ecos_file, "rb"))

	in_state = 0
	start_at = 1
	state = None
	state_data = {}
	for line in reader:
		## Is this a gap between states?
		if all([g == '' for g in line]):
			state = None
			in_state = 0
		
		## Is this a state title?
		if len(line[0]) > 2 and sum([len(x) for x in line[1:]]) == 0\
			and any([line[0].startswith(g) for g in ['Environmental Agency Budget','Amount of', 'Capital spend']])==0: ## exceptions for 2017 document
			state = line[0]
		
		## Is this a year header?
		year_markers = ['FY'] # ['FY 2011', 'FY 2010-2011']
		for yt in year_markers:
			yt_present = [g.startswith(yt) for g in line]
			if any(yt_present):
				start_at = np.where(yt_present)[0][0] ## first non-zero entry
				cols = line[start_at:]
				## If this is a multi-year budget, just associate it with second year
				if '-' in yt:
					cols = ['FY '+c.split('-')[1] for c in cols]
				state_data[state] = pd.DataFrame(columns = cols)
				## Fix for future rows if 2011 got placed in column 0
				if start_at == 0: start_at = 1
		
		## Does this have data?
		if any([(g in line[0]) for g in ['% from', 'of Budget', 'Env. Agency Budget', 'Amount from', 'Status of', 'Environmental Agency']]) \
				and any([g != '' for g in line[1:]]):
			ser = pd.Series(name = line[0], data = line[start_at:], index=cols)
			state_data[state] = state_data[state].append(ser)


	state_df[ecos_file] = pd.concat(state_data)
	state_df[ecos_file].index = state_df[ecos_file].index.set_names(['State','Budget Detail'])


	# Indexing examples
	#state_df[ecos_file].xs('Status of Budget', level=1)
	#state_df[ecos_file].xs('California', level=0)

	"""
	From report: FY 2011 and FY 2012 data include 47 states, the District of Columbia, and Puerto Rico. We were unable
	to obtain data for Florida, Iowa, and New Mexico.
	"""
	print('\n\n',ecos_file)
	print("Total number of territories / states:", len(np.unique(state_df[ecos_file].index.get_level_values(0))))
	print("States missing: ", [s for s in all_states if s not in np.unique(state_df[ecos_file].index.get_level_values(0))])

	#state_df[ecos_file].to_pickle('ECOS/ECOS_state env budget_2011-2013.p')
	state_df[ecos_file].to_csv(ecos_file.replace('.csv','_parsed.csv'))


#### Combine parsed files
## Standardize dates - collapse multi-year time periods to one
for key in state_df:
	state_df[key].rename(columns = {k:(k.replace('FY','').strip().split('-')[-1]) for k in state_df[key]}, inplace = 1)
	## Combine duplicated columns - e.g. 'FY 2011' and 'FY 2011-2012'
	for col in np.unique(state_df[key].columns):
		## Does this column appear multiple times, and has it not already been converted?
		if (sum(c == col for c in state_df[key].columns) > 1 and int(col) not in state_df[key].columns):
			state_df[key][int(col)] = state_df[key][col].max(axis=1)
		## OR does it only appear once?
		elif sum(c == col for c in state_df[key].columns) == 1:
			state_df[key][int(col)] = state_df[key][col]
	state_df[key] = state_df[key][[c for c in state_df[key].columns if c == int(c)]]


### Merge across files
state_df_u = {}
for key in state_df: 
	state_df_u[key] = state_df[key].reset_index()
	## Fix some attribute names
	state_df_u[key]['Budget Detail'] = state_df_u[key]['Budget Detail'].str.replace('\n',' ').str.replace('  ',' ').str.strip().str.replace('Env\.','Environmental').str.replace('\%','Percent')
	state_df_u[key]['Budget Detail'] = state_df_u[key]['Budget Detail'].apply(lambda x: x.replace('Percent from Federal Government (e.g., EPA)', 'Percent from Federal Government'))

## Manually check formatting of columns with: state_df_merge['Budget Detail'].value_counts()[:25]

### Standardize amounts and percents
#for key in state_df:
	#yrs = [c for c in state_df_u[key].columns if c not in ['State','Budget Detail']]
	#if np.sum([c.startswith('Percent') for c in state_df_u[key]['Budget Detail'].unique()]) > 0:
		#suffixes = [c.split('Percent from ')[1] for c in state_df_u[key]['Budget Detail'].unique() if c.startswith('Percent from ')]
		#df_add = []
		#for suf in suffixes:
			#sel_am = (state_df_u[key]['Budget Detail'] == 'Amount from '+suf)
			#sel_bu = (state_df_u[key]['Budget Detail'] == 'Environmental Agency Budget')
			#df_add += [state_df_u[key][sel_am].copy()]
			#for yr in yrs:
				#df_add[-1][yr] = (df_add[-1][yr][sel_am] / df_add[-1][yr][sel_bu]).values
			#df_add[-1]['Budget Detail'] = 'Percent from '+suf
		#state_df_u[key] = pd.concat([state_df_u[key]] + df_add)
	##elif np.sum([c.startswith('Amount') for c in state_df_u[key].columns]) > 0:
		##suffixes = np.unique([c.split('Amount from ')[1] for c in state_df_u[key].columns if c.startswith('Amount from ')])
		##for suf in suffixes:

### When the same year is reported in multiple files, keep info from later file
state_df_merge = state_df_u[ECOS_files[0]]
for i in range(1,len(ECOS_files)):
	state_df_merge = pd.merge(state_df_merge, state_df_u[ECOS_files[i]], on=['State','Budget Detail'], suffixes=['','_old'], how='outer')

## Strip % and $ signs
for col in state_df_merge:
	state_df_merge[col] = state_df_merge[col].str.replace('\%','').str.replace(',','').str.replace('$','')

## Pivot stack on Budget Detail
state_df_merge.index = pd.MultiIndex.from_arrays([state_df_merge['State'], state_df_merge['Budget Detail']], names=['State', 'Budget Detail'])

yrs = sorted(set(state_df_merge.columns) - set(list(state_df_merge.index.names)))

l_state_df = []
for y in yrs:
	l_state_df.append(state_df_merge[[y,]])
	l_state_df[-1] = l_state_df[-1].rename(columns={y:'value'})
	l_state_df[-1]['Year'] = y

## Flatten index
state_df_merge_pivot = pd.concat(l_state_df).reset_index()
## Remove space in column name
state_df_merge_pivot.rename(columns={'Budget Detail':'BudgetDetail'}, inplace=True)

## Encode as ascii
#state_df_merge_pivot['Budget Detail'] = state_df_merge_pivot['Budget Detail'].apply(unidecode)

## Drop nulls
state_df_merge_pivot.dropna(subset=['value'], axis=0, inplace=True)

## Standardize amounts and percents
def cast_amount_percent(df):
	bds = df.BudgetDetail.unique()
	df_add = []
	
	## Get budget, calculating if need be
	## Applies to 2012 report
	if 'Environmental Agency Budget (SRF Added)' in df['BudgetDetail'].values:
		budget = df[df['BudgetDetail'] == 'Environmental Agency Budget (SRF Added)'].value.values[0]
		try:
			budget = float(budget)
		except:
			budget = np.nan
		srf = df[df['BudgetDetail'] == 'Amount of Budget from SRF'].value.values[0]
		try:
			srf = float(srf)
		except:
			srf = np.nan
		df_add += [df.iloc[0].copy()]
		df_add[-1].set_value('BudgetDetail', 'Environmental Agency Budget (No SRF)')
		df_add[-1].set_value('value', budget - srf)
		df_add += [df.iloc[0].copy()]
		df_add[-1].set_value('BudgetDetail', 'Environmental Agency Budget')
		df_add[-1].set_value('value', budget)
	## Applies to 2017 report
	elif 'Amount of Reported SRF' in df['BudgetDetail'].values:
		budget = np.float(df[df['BudgetDetail'] == 'Environmental Agency Budget'].value.values[0])
		srf = df[df['BudgetDetail'] == 'Amount of Reported SRF'].value.values[0]
		try:
			srf = float(srf)
		except:
			srf = np.nan
		df_add += [df.iloc[0].copy()]
		df_add[-1].set_value('BudgetDetail', 'Environmental Agency Budget (No SRF)')
		df_add[-1].set_value('value', budget - srf	)
		df_add += [df.iloc[0].copy()]
		df_add[-1].set_value('BudgetDetail', 'Environmental Agency Budget')
		df_add[-1].set_value('value', budget)
	## Applies to 2010 report
	elif "Budget includes SRF/ARRA funds (Yes/No)?" in df['BudgetDetail'].values:
		budget = np.float(df[df['BudgetDetail'] == 'Environmental Agency Budget'].value.values[0])
		srf_bool = (df[df['BudgetDetail'] == 'Budget includes SRF/ARRA funds (Yes/No)?'].value.values[0] == 'Yes')
		try:
			srf = float(srf)
		except:
			srf = np.nan
		df_add += [df.iloc[0].copy()]
		df_add[-1].set_value('BudgetDetail', 'Environmental Agency Budget (No SRF)')
		if srf_bool:
			df_add[-1].set_value('value', np.nan)
		else:
			df_add[-1].set_value('value', budget)
		df_add += [df.iloc[0].copy()]
		df_add[-1].set_value('BudgetDetail', 'Environmental Agency Budget')
		if srf_bool:
			df_add[-1].set_value('value', budget)
		else:
			df_add[-1].set_value('value', np.nan)
	## Others
	elif 'Environmental Agency Budget' in df['BudgetDetail'].values:
		try:
			budget = np.float(df[df['BudgetDetail'] == 'Environmental Agency Budget'].value.values[0])
		except:
			budget = np.nan
	
	## Calculate percent or amount
	for bd in bds:
		if bd.startswith('Percent from '):
			suf = bd.split('Percent from ')[1]
			
			df_add += [df.iloc[0].copy()]
			df_add[-1].set_value('BudgetDetail', 'Amount from '+suf)
			try:
				df_add[-1].set_value('value', np.round(np.float(df[df['BudgetDetail'] == bd].value.iloc[0])/100. * budget, 2))
			except:
				df_add[-1].set_value('value', np.nan)
		elif bd.startswith('Amount from '):
			suf = bd.split('Amount from ')[1]	
			
			df_add += [df.iloc[0].copy()]
			df_add[-1].set_value('BudgetDetail', 'Percent from '+suf)
			try:
				df_add[-1].set_value('value', np.round(np.float(df[df['BudgetDetail'] == bd].value.iloc[0]) / budget * 100., 2))
			except:
				df_add[-1].set_value('value', np.nan)

	## To debug:
	#if df.name == ('Massachusetts',2009):
		#pdb.set_trace()
	
	return df.append(df_add)

state_df_merge_pivot_stand = state_df_merge_pivot.groupby(['State','Year']).apply(cast_amount_percent) 

## Write out
## Note: jeykll table display on website will not work if there are linebreaks within table cells
state_df_merge_pivot_stand.value = state_df_merge_pivot_stand.value.str.replace('\\n',' ')
state_df_merge_pivot_stand.sort_values(['State','BudgetDetail','Year']).fillna('').to_csv('../docs/data/ECOS_budget_history.csv', index=0, encoding='ascii')
