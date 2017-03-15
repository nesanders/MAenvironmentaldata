from bs4 import BeautifulSoup
import urllib2
import pickle
import pandas as pd
from unidecode import unidecode
import re
import os
import datetime
import numpy as np
 
URL_permit = {}
URL_permit['final'] = "https://www3.epa.gov/region1/npdes/permits_listing_{}.html"
URL_permit['draft'] = "https://www3.epa.gov/region1/npdes/draft_permits_listing_{}.html"

all_states = ['ct','me','nh','ma','ri','vt']

all_urls = []
all_url_stages = []
all_url_states = []

for state in all_states:
	for stage in URL_permit:
		all_urls += [URL_permit[stage].format(state)]
		all_url_states += [state]
		all_url_stages += [stage]

all_content = [urllib2.urlopen(all_urls[i]).read() for i in range(len(all_urls))]
with open('EPARegion1_NPDES_permit_pages.p', 'w') as f: pickle.dump(all_content, f)

permit_data = []
for ci, content in enumerate(all_content):
	soup = BeautifulSoup(content, 'lxml')
	table = soup.findAll('tr')
	stage = all_url_stages[ci]
	state = all_url_states[ci]
	print stage, state
	header = [table[0].findAll('th')[i].get_text() for i in range(len(table[0].findAll('th')))]

	for row in table[1:]:
		permit_data += [{}]
		
		permit_data[-1]['Stage'] = stage
		permit_data[-1]['State'] = state
		
		for i,col in enumerate(header):
			if '<td>' in str(row):
				element = row.findAll('td')[i]
			elif '<th>' in str(row):
				element = row.findAll('th')[i]
			else:
				raise 
			
			permit_data[-1][col] = unidecode(element.get_text())
			
			if permit_data[-1][col] == 'N/A':
				nullcol = 1
				permit_data[-1][col] = np.nan
			else:
				nullcol = 0
			
			if stage == 'draft':
				
				permit_data[-1]['Watershed'] = np.nan
				
				if col == 'Comment Period Dates':
					if nullcol == 0 and '-' not in permit_data[-1][col]: nullcol=1
					if nullcol:
						for cc in ['Comment_date_start', 'Comment_date_end', 'Comment_date_extension']:
							permit_data[-1][cc] = np.nan
					else:
						permit_data[-1]['Comment_date_start'] = permit_data[-1][col].split()[0]
						permit_data[-1]['Comment_date_end'] = permit_data[-1][col].split(' - ')[1].split(' (')[0]
						permit_data[-1]['Comment_date_extension'] = permit_data[-1][col].split()[-1][:-1] if ('Extended' in permit_data[-1][col] or 'Re-opening' in permit_data[-1][col]) else np.nan
				
			
			if stage == 'final':
				if 'Watershed' in col:
					if '(' in permit_data[-1][col]:
						permit_data[-1]['Watershed'] = permit_data[-1][col].split('(')[1][:-1].strip()
					else:
						permit_data[-1]['Watershed'] = np.nan
					permit_data[-1]['City/Town'] = permit_data[-1][col].split(' (')[0].strip()
				
			if col == 'Facility Name':
				permit_data[-1]['Facility_name_clean'] = permit_data[-1][col].split(' (PDF')[0]
				if '(PDF' in permit_data[-1][col]:
					permit_data[-1]['Permit_URL'] = ['https://www3.epa.gov/region1/npdes/' + element.findAll('a')[j].get('href') for j in range(len(element.findAll('a')))]
				else:
					permit_data[-1]['Permit_URL'] = np.nan


permit_df = pd.DataFrame(permit_data)

permit_dir = '../docs/assets/permits/EPA_Region1_NPDES_permits/{}/{}/{}_'
os.system('mkdir '+permit_dir.split('/')[0])

out_files = []
for i in range(len(permit_df)):
	row = permit_df.iloc[i]
	state = row['State']
	stage = row['Stage']
	permitID = row['Permit Number']
	if row['Permit_URL'] is not np.nan:
		out_files += [[]]
		for permit in row['Permit_URL']:
			out_path = permit_dir.format(state, stage, permitID)
			for i in range(1,len(out_path.split('/'))):
				check_path = '/'.join(out_path.split('/')[:i])
				if os.path.exists(check_path) == 0:
					os.system('mkdir '+check_path)
			out_files[-1] += [out_path + permit.split('/')[-1]]
			os.system('wget '+permit+' --no-clobber -O ' + out_files[-1][-1])
	else:
		out_files += [['']]

permit_df['permit_path'] = out_files

## Write out data
permit_df.to_pickle('EPARegion1_NPDES_permit_data.p')
permit_df.to_csv('../docs/data/EPARegion1_NPDES_permit_data.csv', index=0)
os.system('cp ../docs/data/EPARegion1_NPDES_permit_data.csv ../docs/_data/EPARegion1_NPDES_permit_data.csv')


## Report last update
with open('../docs/_data/ts_update_EPARegion1_NPDES_permit.yml', 'w') as f:
	f.write('updated: '+str(datetime.datetime.now()).split('.')[0]+'\n')

