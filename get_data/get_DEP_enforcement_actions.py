from bs4 import BeautifulSoup
import urllib2
import pickle
import pandas as pd
from unidecode import unidecode
import re
import numpy as np
import datetime
import os

years = range(2004, datetime.date.today().year+1)

## Download DEP enforcement news archives
base_url = "http://www.mass.gov/eea/agencies/massdep/service/enforcement/enforcement-actions-{}.html"
all_urls = [base_url.format(i) for i in years]
all_content = [urllib2.urlopen(url).read() for url in all_urls]
with open('DEP_enforcement_pages.p', 'w') as f: pickle.dump(all_content, f)

## Iterate through content
all_soups = [BeautifulSoup(c, "lxml") for c in all_content]
all_content_list = []
for year, soup in zip(years, all_soups):
	print year
	divs = soup.findAll('div')
	div_i = [i for i in range(len(divs)) if 'class' in divs[i].attrs and divs[i].attrs['class'] == ['col','col12','bodyfield']] # identify which div has the enforcement data - this can change when alerts, etc. are temporarily posted to the site
	assert(len(div_i) == 1)
	div_i = div_i[0]
	pars = divs[div_i].findAll('p')
	for par in pars:
		## Check that this paragraph starts with a date
		pt = par.get_text()
		if re.match('^[0-9]{1,2}\/[0-9]{1,2}\/[0-9]{2,4}:', pt) is not None:
			p_date = pt.split(':')[0]
			p_text = pt.split(':')[1].lstrip()
			all_content_list += [(year, p_date, p_text)]

## Setup output data frame
DEP_df = pd.DataFrame(data = np.array(all_content_list), columns = ['Year','Date','Text'])
DEP_df.Text = DEP_df.Text.apply(unidecode)
DEP_df.to_csv('../docs/data/MADEP_enforcement_actions.csv', index=False)
os.system('cp ../docs/data/MADEP_enforcement_actions.csv ../docs/_data/MADEP_enforcement_actions.csv')

## Report last update
with open('../docs/_data/ts_update_MADEP_enforcement_actions.yml', 'w') as f:
	f.write('updated: '+str(datetime.datetime.now()).split('.')[0]+'\n')


