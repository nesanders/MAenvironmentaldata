"""
MA DEP staff data can be collected from the MA office of the Comptroller of the Commonwealth:

https://cthru.data.socrata.com/Government/Comptroller-of-the-Commonwealth-Payroll/rr3a-7twk

The Comptroller provides a SODA API, which is used here to retrieve the data:

https://dev.socrata.com/foundry/cthru.data.socrata.com/rr3a-7twk

Unfortunately, the Comptroller's site only provides data back
to 2010, whereas other sources extend back to 2004.
"""

import pandas as pd
import sodapy
import datetime
import os

DEP_slug = "rr3a-7twk"

### Load credentials - you need to sign up for a SODA account to register a token
with open('SECRET_SODA_token', 'r') as f:
	app_token, secret_token = [g.strip() for g in f.readlines()]

fields = {
	u'bargaining_group_title': str,
	u'contract': str,
	u'department_division': str,
	u'department_location_zip_code': str,
	u'name_first': str,
	u'name_last': str,
	u'pay_base_actual': float,
	u'pay_buyout_actual': float,
	u'pay_overtime_actual': float,
	u'pay_total_actual': float,
	u'position_title': str,
	u'position_type': str,
	u'year': int
}

client = sodapy.Socrata("cthru.data.socrata.com", app_token=app_token)#, access_token=secret_token)

query_limit=50000
i = 0; df_d = []
## Page through records
while i == 0 or len(df_d[-1]) == query_limit: 
	print i
	df_d += [client.get(DEP_slug, 
		where="department_division = 'DEPARTMENT OF ENVIRONMENTAL PROTECTION (EQE)'",
		select = ','.join(fields.keys()),
		limit = query_limit, offset=i
		)]
	i += query_limit

df = pd.concat([pd.DataFrame(d) for d in df_d])

for f in fields: df[f] = df[f].astype(fields[f])

df.to_csv('../docs/data/MADEP_staff_SODA.csv', index=0)
os.system('cp ../docs/data/MADEP_staff_SODA.csv ../docs/_data/MADEP_staff_SODA.csv')


## Report last update
with open('../docs/_data/ts_update_MADEP_staff_SODA.yml', 'w') as f:
	f.write('updated: '+str(datetime.datetime.now()).split('.')[0]+'\n')


