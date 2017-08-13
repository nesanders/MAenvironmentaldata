from bs4 import BeautifulSoup
import urllib2
import pickle
import pandas as pd
from unidecode import unidecode
import re
import numpy as np
import datetime
import os


proper_noun_regexp = r'(?:\s*\b[A-Z][a-z\-]+\b)+'
proper_noun_regexp_c = re.compile(proper_noun_regexp)
def extract_proper_nouns(s): 
	"""
	Function to check if a town name is only used as part of a longer proper noun (e.g. 'Rever Copper Products, Inc. of New Bedford')
	"""
	return [g.lstrip() for g in proper_noun_regexp_c.findall(s)]


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

## Fix some by hand
DEP_df_replacements = {
	r'''MassDEP entered into a Consent Order with a $53, 938 Penalty involving Charles Wilmot, a home improvement contractor, for Air Quality (Asbestos) violations at a work site in Worcester. Due to financial hardship information provided by Wilmot, MassDEP agreed to suspend the Penalty provided Wilmot remain in compliance with state's air regulations.4/27/06''': '''MassDEP entered into a Consent Order with a $53,938 Penalty involving Charles Wilmot, a home improvement contractor, for Air Quality (Asbestos) violations at a work site in Worcester. Due to financial hardship information provided by Wilmot, MassDEP agreed to suspend the Penalty provided Wilmot remain in compliance with state's air regulations.4/27/06''',
	r'''MassDEP entered into a Consent Order with a $67,8200 Penalty involving Glyptal, Inc. of Chelsea for Waste Site Cleanup violations. 305 Eastern Avenue, Chelsea for continued violations of M.G.L c 21C. Within 180 days of the effective date of the Consent Order $3,500 is due with the balance of $64,320 payable with 30 days of a DEP Demand Notice as a result of non-compliance with the ACO.''':r'''MassDEP entered into a Consent Order with a $67,820 Penalty involving Glyptal, Inc. of Chelsea for Waste Site Cleanup violations. 305 Eastern Avenue, Chelsea for continued violations of M.G.L c 21C. Within 180 days of the effective date of the Consent Order $3,500 is due with the balance of $64,320 payable with 30 days of a DEP Demand Notice as a result of non-compliance with the ACO.''',
	r'''MassDEP entered into a Consent Order with a $23, 950 Penalty involving Pride Ford and Pride Dodge of North Attleboro for Hazardous Waste violations. Inspections by MassDEP revealed the facilities had not complied with the''':r'''MassDEP entered into a Consent Order with a $23,950 Penalty involving Pride Ford and Pride Dodge of North Attleboro for Hazardous Waste violations. Inspections by MassDEP revealed the facilities had not complied with the''',
	r'''MassDEP entered into a Consent Order with a $9.750 Penalty involving the King Phillip Realty Trust of Raynham. The Trust was operating a public water supply without MassDEP approval. A previous notice of noncompliance was issued against this particular facility. The Trust has now agreed to either, register - and conduct testing - or connects to an existing water supplier.''':r'''MassDEP entered into a Consent Order with a $9,750 Penalty involving the King Phillip Realty Trust of Raynham. The Trust was operating a public water supply without MassDEP approval. A previous notice of noncompliance was issued against this particular facility. The Trust has now agreed to either, register - and conduct testing - or connects to an existing water supplier.''',
	r'''MassDEP executed a Consent Order with a $30.000 Penalty involving Mohammad Al Omari for Waste Site Cleanup violations at 454 Water Street in Wakefield. Mohammad Al Omari is the owner and/or operator of the property at 454 Water Street where violations including failure to meet deadlines set out in previously-issued notice of noncompliance dated 6/12/13.  Today's Order requires a tier two cleanup permit transfer and tier two extension by 2/28/14; a phase three remedial alternatives analysis report for the site which meets the requirements by 4/30/14; and, phase four remedial implementation report for the site which meets the requirements by 7/30/14.  Finally, by 7/30/14, the respondent shall submit to MassDEP a response action final outcome statement or a remedy operation status whic9h meets the requirements for the site. Under the terms of today's Order, the respondent has agreed to pay $5,000 of the Penalty with the remaining $25,000 suspended pending compliance with the terms of the Order and meeting all the required deadlines.''':r'''MassDEP executed a Consent Order with a $30,000 Penalty involving Mohammad Al Omari for Waste Site Cleanup violations at 454 Water Street in Wakefield. Mohammad Al Omari is the owner and/or operator of the property at 454 Water Street where violations including failure to meet deadlines set out in previously-issued notice of noncompliance dated 6/12/13.  Today's Order requires a tier two cleanup permit transfer and tier two extension by 2/28/14; a phase three remedial alternatives analysis report for the site which meets the requirements by 4/30/14; and, phase four remedial implementation report for the site which meets the requirements by 7/30/14.  Finally, by 7/30/14, the respondent shall submit to MassDEP a response action final outcome statement or a remedy operation status whic9h meets the requirements for the site. Under the terms of today's Order, the respondent has agreed to pay $5,000 of the Penalty with the remaining $25,000 suspended pending compliance with the terms of the Order and meeting all the required deadlines. ''',
	r'''MassDEP issued a $2.524 Penalty Assessment Notice to Lamberto's Garage for Air Quality (Stage II vapor recovery) violations in Franklin. Inspections in 2007 by MassDEP found failures to perform in-use compliance tests on vapor recovery systems at this gasoline dispensing facility and other recordkeeping violations. Efforts to reach a negotiated settlement of this enforcement action were unsuccessful.''':r'''MassDEP issued a $2,524 Penalty Assessment Notice to Lamberto's Garage for Air Quality (Stage II vapor recovery) violations in Franklin. Inspections in 2007 by MassDEP found failures to perform in-use compliance tests on vapor recovery systems at this gasoline dispensing facility and other recordkeeping violations. Efforts to reach a negotiated settlement of this enforcement action were unsuccessful.''',
	r'''DEP executed a Consent Order with a $9.250 Penalty involving Boston and Main Corporation for hazardous waste violations at its facility in East Deerfield. B&M, with offices located in North Billerica, was cited for hazardous waste management violations discovered during a DEP inspection on 6/30/04. Waste oil had been stored at this facility in excess of the time limit allowed under state regulations. As part of the settlement agreement, Boston & Maine has agreed to implement measures to prevent this violation from reoccurring.''':r'''DEP executed a Consent Order with a $9,250 Penalty involving Boston and Main Corporation for hazardous waste violations at its facility in East Deerfield. B&M, with offices located in North Billerica, was cited for hazardous waste management violations discovered during a DEP inspection on 6/30/04. Waste oil had been stored at this facility in excess of the time limit allowed under state regulations. As part of the settlement agreement, Boston & Maine has agreed to implement measures to prevent this violation from reoccurring.''',
	r'''MassDEP entered into a Consent Order with a $39.000 Penalty involving M.K. Realty Trust for Water Pollution Control violations in Tewksbury.Robert Scarano, President of M.K. Realty Trust, failed to obtain a sewer extension permit before building eight residential townhouse condominiums (16 condos), a twelve-room bed and breakfast, new road (Preservation Lane) and temporary sewage pump station. The pump station will be in use until such time as the town's expanding sewer system can receive flows by gravity. The new road had already been constructed and most of the condos sold and occupied. Once the Respondent obtains Massachusetts Historical Commission approval for the project and site, the sewer permitting process will resume. MassDEP has agreed to suspend $28,000 of the Penalty provided all terms of the Order are met.''':r'''MassDEP entered into a Consent Order with a $39,000 Penalty involving M.K. Realty Trust for Water Pollution Control violations in Tewksbury.Robert Scarano, President of M.K. Realty Trust, failed to obtain a sewer extension permit before building eight residential townhouse condominiums (16 condos), a twelve-room bed and breakfast, new road (Preservation Lane) and temporary sewage pump station. The pump station will be in use until such time as the town's expanding sewer system can receive flows by gravity. The new road had already been constructed and most of the condos sold and occupied. Once the Respondent obtains Massachusetts Historical Commission approval for the project and site, the sewer permitting process will resume. MassDEP has agreed to suspend $28,000 of the Penalty provided all terms of the Order are met.''',
	r'''MassDEP entered into a Consent Order with the Cambridge Public Health Commission, which owns and operates facilities in Everett, Somerville and Cambridge, for Air Quality and Hazardous Waste Management violations. The Cambridge Public Health Commission ("CPHC") operates three non-profit hospitals (Whidden Memorial Hospital in Everett, Somerville Hospital and Cambridge Hospital). At these three facilities, MassDEP observed various violations for which CPHC has now agreed to pay a $47, 130 Penalty ($12,630 of which is for missed compliance fees) and MassDEP has agreed to suspend $14,500 of the total pending full compliance over the next year.''':r'''MassDEP entered into a Consent Order with the Cambridge Public Health Commission, which owns and operates facilities in Everett, Somerville and Cambridge, for Air Quality and Hazardous Waste Management violations. The Cambridge Public Health Commission ("CPHC") operates three non-profit hospitals (Whidden Memorial Hospital in Everett, Somerville Hospital and Cambridge Hospital). At these three facilities, MassDEP observed various violations for which CPHC has now agreed to pay a $47,130 Penalty ($12,630 of which is for missed compliance fees) and MassDEP has agreed to suspend $14,500 of the total pending full compliance over the next year.''',
	r'''MassDEP entered into a Consent Order with a $53, 938 Penalty involving Charles Wilmot, a home improvement contractor, for Air Quality (Asbestos) violations at a work site in Worcester. Due to financial hardship information provided by Wilmot, MassDEP agreed to suspend the Penalty provided Wilmot remain in compliance with state's air regulations.4/27/06''':r'''MassDEP entered into a Consent Order with a $53,938 Penalty involving Charles Wilmot, a home improvement contractor, for Air Quality (Asbestos) violations at a work site in Worcester. Due to financial hardship information provided by Wilmot, MassDEP agreed to suspend the Penalty provided Wilmot remain in compliance with state's air regulations.4/27/06''',
	}

for g in DEP_df_replacements:
	DEP_df.Text[DEP_df.Text == g] = DEP_df_replacements[g]


####  Parse and annotate data
## Add inferred type
order_types = ['consent order', 'unilateral order', 'demand', 'demand notice', 'agreement', 
	       'notice of noncompliance', 'boil water order', 'settlement agreement', 'amendment', 
	       'penalty assessment notice', 'civil administrative penalty', 'labels', 'water supply', 
	       'attorney general', 'water','hazardous waste', 'sewer',
	       'civil penalty',' supplemental environmental project', 'gasoline', 'asbestos', 'wetlands',
	       'stormwater']
for order in order_types:
	DEP_df['order_'+order] = DEP_df.Text.str.lower().str.contains(order)

law_types = [['npdes','National Pollution Discharge Elimination System'],['chapter 91', 'ch 91']]
for law in law_types:
	DEP_df['law_'+law[0]] = DEP_df.Text.str.lower().apply(lambda x: np.any([g in x for g in law]))

## Add inferred cost
currency_match = r'\$[0-9]{1,3}(?:,?[0-9]{3})*(?:\.[0-9]{2})?\b'
currency_match_millions = r'\$[0-9]{1,3}(?:,?[0-9]{3})*(?:\.{0,2}[0-9]{0,2} million)\b'
def get_dollars(x):
	a = re.search(currency_match, x)
	## Seems to just return the first number from the string
	if a:
		## check if first group is a million
		b = re.search(currency_match_millions, x)
		if b and b.group(0).split('.')[0].split()[0] == a.group(0):
			return float(b.group(0).replace(',','').replace('$','').split()[0])*1e6
		else:
			return float(a.group(0).replace(',','').replace('$',''))
	else:
		return np.nan

DEP_df['Fine'] = DEP_df.Text.apply(get_dollars)

## Annotate towns
pop_inc_data = pd.read_csv('../docs/data/Census_ACS_MA.csv')
pop_inc_data.index = pop_inc_data['Subdivision']
DEP_df['municipality'] = DEP_df.Text.apply(extract_proper_nouns).apply(lambda x: [town for town in pop_inc_data['Subdivision'] if town in x])

##Add in municipal population data, averaging when multiple are listed (obviously not the ideal in every case)
def pop_inc_data_avg(towns, col):
	vals = []
	for town in towns:
		vals += [pop_inc_data.ix[town][col]]
	return np.mean(vals)


## Output dataframe
DEP_df.to_csv('../docs/data/MADEP_enforcement_actions.csv', index=False)

## Print a sample of the file as an example
DEP_df.sample(n=10).to_csv('../docs/data/MADEP_enforcement_actions_sample.csv', index=False)

## Report last update
with open('../docs/data/ts_update_MADEP_enforcement_actions.yml', 'w') as f:
	f.write('updated: '+str(datetime.datetime.now()).split('.')[0]+'\n')


