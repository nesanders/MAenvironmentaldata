"""Download all NPDES permits from EPA Region 1 (CT, ME, NH, MA, RI, VT) and upload PDFs to GCS.

Scrapes the EPA NPDES permit listing pages for both draft and final permits in all six
New England states.  For each state/stage combination the page may serve either an
AJAX-loaded JSON table (the newer format) or a static HTML table; both are handled.

Key known EPA page changes that have been worked around:
  - ~2025: JSON payload switched from orient='split' to {"data": [...]}
  - ~2025: Column renamed from 'Facility Name' to 'Applicant / Facility Name'

PDF sync is incremental: a single `gsutil ls` call lists what is already in GCS and
only newly-discovered PDFs are downloaded and uploaded.  This makes both local runs
and GitHub Actions runs efficient.

Outputs:
  ../docs/data/EPARegion1_NPDES_permit_data.csv  — permit metadata table
  gs://openamend-data/EPA_Region1_NPDES_permits/ — permit PDFs
  ../docs/data/ts_update_EPARegion1_NPDES_permit.yml — timestamp of last run
"""

from io import StringIO
from bs4 import BeautifulSoup
from urllib import request
import pickle
import pandas as pd
from unidecode import unidecode,unidecode_expect_nonascii
import os
import datetime
import numpy as np

# ------------------------------
# Constants
# ------------------------------

PERMIT_DIR = 'EPA_Region1_NPDES_permits/{}/{}/{}_'
GS_URL = 'https://storage.googleapis.com/openamend-data/EPA_Region1_NPDES_permits/{}/{}/{}_'

ALL_STATES = {'ct':'connecticut','me':'maine','nh':'new-hampshire','ma':'massachusetts','ri':'rhode-island','vt':'vermont'}
 
PERMIT_URL_DICT = {}
PERMIT_URL_DICT['final'] = "https://www.epa.gov/npdes-permits/{}-final-individual-npdes-permits"
PERMIT_URL_DICT['draft'] = "https://www.epa.gov/npdes-permits/{}-draft-individual-npdes-permits"

if __name__ == '__main__':
    # ------------------------------
    # Download files
    # ------------------------------

    all_urls = []
    all_url_stages = []
    all_url_states = []

    for state in ALL_STATES:
        for stage in PERMIT_URL_DICT:
            all_urls += [PERMIT_URL_DICT[stage].format(ALL_STATES[state])]
            all_url_states += [state]
            all_url_stages += [stage]

    opener = request.build_opener()  
    all_content = [opener.open(request.Request(all_urls[i])).read() for i in range(len(all_urls))]
    with open('EPARegion1_NPDES_permit_pages.p', 'wb') as f: 
        pickle.dump(all_content, f)

    permit_data = []
    for ci, content in enumerate(all_content):
        
        # Convert from bytes to string
        content = content.decode('utf-8')
        
        stage = all_url_stages[ci]
        state = all_url_states[ci]
        print(f'Downloading stage={stage}, state={state}')
            
        ## ajax/json table
        if "'ajax': jsonURL" in content:
            print('Parsing json table')

            ## Construct URL
            if "jsonURL = '" not in content:
                raise ValueError(f"Expected 'jsonURL' JS variable not found in page for {state}/{stage}. EPA page structure may have changed.")
            jsonfn = content.split("jsonURL = '")[1].split("';")[0].split("?\'")[0].lstrip('/')
            jsonURL = '/'.join(all_urls[ci].split('/')[:-2]) + '/' + jsonfn

            ## Request content
            json_raw = opener.open(request.Request(jsonURL)).read()

            ## Decode content
            jsoncontent = unidecode_expect_nonascii(json_raw.decode('utf-8'))

            ## Convert to dataframe
            ## EPA changed JSON format from orient='split' to {"data": [...]} around 2025
            import json as _json
            raw = _json.loads(jsoncontent)
            if isinstance(raw, dict) and 'data' in raw:
                pdf = pd.DataFrame(raw['data'])
            else:
                pdf = pd.read_json(StringIO(jsoncontent), orient='split')

            ## Clean up dataframe content
            city_col_matches = pdf.columns[pdf.columns.str.startswith('City / Town')]
            if len(city_col_matches) == 0:
                raise ValueError(f"Expected 'City / Town' column not found in JSON table for {state}/{stage}. Columns: {list(pdf.columns)}")
            city_col_name = city_col_matches.values[0]
            pdf['City/Town'] = pdf[city_col_name].apply(lambda x: x.split(' (')[0].strip())
            ## EPA renamed 'Facility Name' to 'Applicant / Facility Name' around 2025
            facility_col = 'Facility Name' if 'Facility Name' in pdf.columns else 'Applicant / Facility Name'
            if facility_col not in pdf.columns:
                raise ValueError(f"Expected facility name column not found for {state}/{stage}. Columns: {list(pdf.columns)}")
            pdf['Facility Name'] = pdf[facility_col]
            pdf['Facility_name_clean'] = pdf['Facility Name'].apply(lambda x: BeautifulSoup(x).text.split(' (PDF')[0].split('\n')[0].split("in new window.'>")[-1])
            pdf['Permit_URL'] = pdf['Facility Name'].apply(lambda x: [
                BeautifulSoup(x).findAll('a')[j].get('href')
                for j in range(len(BeautifulSoup(x, features="lxml").findAll('a')))
            ])
            pdf['Stage'] = stage
            pdf['State'] = state
            pdf['Watershed'] = pdf[city_col_name].apply(lambda x: x.split('(')[1][:-1].strip() if '(' in x else np.nan)
            
            ## Add to list readout
            for i in range(len(pdf)):
                permit_data += [dict(pdf.iloc[i])]
        
        ## HTML table
        else:
            print('Parsing html table')
            soup = BeautifulSoup(content, 'lxml')
            
            table = soup.findAll('tr')
            header = [table[0].findAll('th')[i].get_text() for i in range(len(table[0].findAll('th')))]

            print(f'Iterating over N={len(table[1:])} rows')
            for row in table[1:]:
                if 'Facility Name' not in row.text:
                    
                    permit_data += [{}]
                    
                    permit_data[-1]['Stage'] = stage
                    permit_data[-1]['State'] = state
                    
                    for i,col in enumerate(header):
                        if '<td>' in str(row):
                            element = row.findAll('td')[i]
                        elif '<th>' in str(row):
                            element = row.findAll('th')[i]
                        else:
                            raise ValueError('Missing expected HTML elements in table')
                        
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
                                    permit_data[-1]['Comment_date_start'] = permit_data[-1][col].split('-')[0].strip()
                                    permit_data[-1]['Comment_date_end'] = permit_data[-1][col].split('-')[1].split(' (')[0].strip()
                                    permit_data[-1]['Comment_date_extension'] = permit_data[-1][col].split()[-1][:-1] if ('Extended' in permit_data[-1][col] or 'Re-opening' in permit_data[-1][col]) else np.nan
                        
                        if stage == 'final':
                            if 'Watershed' in col:
                                if '(' in permit_data[-1][col]:
                                    permit_data[-1]['Watershed'] = permit_data[-1][col].split('(')[1][:-1].strip()
                                else:
                                    permit_data[-1]['Watershed'] = np.nan
                                permit_data[-1]['City/Town'] = permit_data[-1][col].split(' (')[0].strip()
                                
                            if 'Issuance' in col:
                                permit_data[-1]['Date of Issuance'] = permit_data[-1][col]
                            
                        if col == 'Facility Name':
                            permit_data[-1]['Facility_name_clean'] = permit_data[-1][col].split(' (PDF')[0].split('\n')[0]
                            if '(PDF' in permit_data[-1][col]:
                                permit_data[-1]['Permit_URL'] = ['https://www3.epa.gov/region1/npdes/' + element.findAll('a')[j].get('href') for j in range(len(element.findAll('a')))]
                            else:
                                permit_data[-1]['Permit_URL'] = np.nan


    permit_df = pd.DataFrame(permit_data)

    if len(permit_df) < 500:
        raise ValueError(f"Only {len(permit_df)} permits parsed — expected at least 500. Aborting to avoid overwriting good data.")

    os.system('mkdir '+PERMIT_DIR.split('/')[0])

    ## Build a set of PDF filenames already in GCS with a single listing call.
    ## This lets us skip both the download and upload for existing PDFs, keeping
    ## the sync incremental whether running locally or in CI.
    print('Listing existing PDFs in GCS...')
    gs_ls = os.popen('gsutil ls "gs://openamend-data/EPA_Region1_NPDES_permits/**"').read()
    existing_in_gcs = set(os.path.basename(p) for p in gs_ls.splitlines() if p.strip())
    print(f'Found {len(existing_in_gcs)} files already in GCS.')

    out_files = []
    new_pdf_count = 0
    for i in range(len(permit_df)):
        row = permit_df.iloc[i]
        state = row['State']
        stage = row['Stage']
        permitID = row['Permit Number']
        if row['Permit_URL'] is not np.nan:
            out_files += [[]]
            for permit in row['Permit_URL']:
                # Skip anything that isn't a direct PDF link (avoids downloading
                # HTML listing pages, anchor fragments, etc.)
                if not permit.lower().split('?')[0].split('#')[0].endswith('.pdf'):
                    continue
                out_path = PERMIT_DIR.format(state, stage, permitID)
                for i in range(1,len(out_path.split('/'))):
                    check_path = '/'.join(out_path.split('/')[:i])
                    if os.path.exists(check_path) == 0:
                        os.system('mkdir '+check_path)
                filename = permit.split('/')[-1]
                local_file = out_path + filename
                gs_file = GS_URL.format(state, stage, permitID) + filename
                out_files[-1] += [gs_file]
                # Check by the stored filename (includes permitID prefix from out_path)
                stored_filename = os.path.basename(local_file)
                if stored_filename not in existing_in_gcs:
                    os.system('wget '+permit+' --no-clobber --timeout=30 --tries=3 -O ' + local_file)
                    if os.path.exists(local_file):
                        os.system('gsutil cp ' + local_file + ' gs://openamend-data/' + local_file)
                        new_pdf_count += 1
        else:
            out_files += [['']]

    print(f'Uploaded {new_pdf_count} new PDFs to GCS.')
    ## access at e.g. https://storage.googleapis.com/openamend-data/EPA_Region1_NPDES_permits/nh/final/NH0000116_finalnh0000116permit.pdf

    ## Write out data
    permit_df.to_pickle('EPARegion1_NPDES_permit_data.p')
    permit_df.rename(columns = {c:c.replace(' ','_') for c in permit_df.columns}, inplace=True)
    # NOTE: UTF8 outputs break tables in jekyll!  http://support.markedapp.com/discussions/problems/18583-rendering-tables-with-kramdown
    permit_df.to_csv('../docs/data/EPARegion1_NPDES_permit_data.csv', index=0, encoding='ascii')


    # ------------------------------
    # Bump time last updated
    # ------------------------------

    ## Report last update
    with open('../docs/data/ts_update_EPARegion1_NPDES_permit.yml', 'w') as f:
        f.write('updated: '+str(datetime.datetime.now()).split('.')[0]+'\n')

