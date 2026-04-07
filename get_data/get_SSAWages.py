"""Fetch SSA Average Wage Index from ssa.gov and update the SSAWages CSV.

Replaces manual CSV updates. Reads the HTML table from:
https://www.ssa.gov/oact/cola/awidevelop.html

NOTE (2026-04-06): ssa.gov is blocking automated access (403 Forbidden).
This script would work once SSA opens access, or if invoked from an authenticated
context. For now, the CSV is updated manually.
"""

import datetime
import pandas as pd
import requests
from io import StringIO

SSA_AWI_URL = 'https://www.ssa.gov/oact/cola/awidevelop.html'

if __name__ == '__main__':
    try:
        # Fetch with User-Agent to avoid 403 Forbidden
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        resp = requests.get(SSA_AWI_URL, headers=headers, timeout=30)
        resp.raise_for_status()

        tables = pd.read_html(StringIO(resp.text))
        # First table is the AWI series
        awi = tables[0].copy()

        # Column names vary; look for Year and AWI series columns
        if 'Year' in awi.columns and 'AWI series' in awi.columns:
            awi = awi[['Year', 'AWI series']].copy()
            awi.columns = ['Year', 'AWI']
        else:
            # Fallback: first column is Year, second numeric is AWI
            numeric_cols = awi.select_dtypes(include=['number']).columns.tolist()
            awi = awi[[awi.columns[0], numeric_cols[0]]].copy()
            awi.columns = ['Year', 'AWI']

        awi = awi.dropna()
        awi['Year'] = awi['Year'].astype(int)
        awi['AWI'] = awi['AWI'].astype(float)
        awi = awi.sort_values('Year')

        awi.to_csv('../docs/data/SSAWages.csv', index=False)

        print(f"Saved SSA AWI: {awi.Year.min()}–{awi.Year.max()}, latest AWI=${awi.iloc[-1].AWI:.2f}")

        # Write update timestamp
        with open('../docs/data/ts_update_SSAWages.yml', 'w') as f:
            f.write('updated: ' + str(datetime.datetime.now()).split('.')[0] + '\n')

    except requests.exceptions.HTTPError as e:
        print(f"ERROR: {e}")
        print("SSA website is blocking automated access. Update the CSV manually or wait for API access.")
        exit(1)
