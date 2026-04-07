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

print(f'[{datetime.datetime.now().isoformat()}] get_DEP_staff_SODA.py starting...')

DEP_SLUG = "rr3a-7twk"

### Load credentials - you need to sign up for a SODA account to register a token
print(f'[{datetime.datetime.now().isoformat()}] Loading SODA credentials from SECRET_SODA_token...')
with open('SECRET_SODA_token', 'r') as f:
	app_token, secret_token = [g.strip() for g in f.readlines()]
print('✓ Credentials loaded')

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

print(f'[{datetime.datetime.now().isoformat()}] Connecting to SODA API...')
client = sodapy.Socrata("cthru.data.socrata.com", app_token=app_token)#, access_token=secret_token)
print('✓ Connected to SODA API')

query_limit=50000
i = 0; df_d = []
total_records = 0
## Page through records
print(f'[{datetime.datetime.now().isoformat()}] Fetching DEP staff payroll records...')
while i == 0 or len(df_d[-1]) == query_limit:
	print(f'  Loading page {i//query_limit}: offset {i}...', end='', flush=True)
	df_d += [client.get(DEP_SLUG,
		where="department_division = 'DEPARTMENT OF ENVIRONMENTAL PROTECTION (EQE)'",
		select = ','.join(list(fields.keys())),
		limit = query_limit, offset=i
		)]
	page_count = len(df_d[-1])
	total_records += page_count
	print(f' {page_count} records (total: {total_records})')
	i += query_limit

print(f'✓ Fetched {total_records} total records across {len(df_d)} pages')
print(f'[{datetime.datetime.now().isoformat()}] Concatenating dataframes...')
df = pd.concat([pd.DataFrame(d) for d in df_d])
print(f'✓ Concatenated to {len(df)} rows')

print(f'[{datetime.datetime.now().isoformat()}] Converting data types...')
for f in fields: df[f] = df[f].astype(fields[f])
print('✓ Data types converted')

## Write out
print(f'[{datetime.datetime.now().isoformat()}] Writing CSV to ../docs/data/MADEP_staff_SODA.csv...')
df.to_csv('../docs/data/MADEP_staff_SODA.csv', index=0)
print('✓ Main CSV written')

## Print a sample of the file as an example
print('Writing sample CSV to ../docs/data/MADEP_staff_SODA_sample.csv...')
df.sample(n=10).to_csv('../docs/data/MADEP_staff_SODA_sample.csv', index=0)
print('✓ Sample CSV written')

## Report last update
print('Writing timestamp to ../docs/data/ts_update_MADEP_staff_SODA.yml...')
with open('../docs/data/ts_update_MADEP_staff_SODA.yml', 'w') as f:
	f.write('updated: '+str(datetime.datetime.now()).split('.')[0]+'\n')
print('✓ Timestamp written')

print(f'\n✓ get_DEP_staff_SODA.py completed successfully at {datetime.datetime.now().isoformat()}')


