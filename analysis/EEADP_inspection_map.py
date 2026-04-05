"""Generate Plotly choropleth map of EEA inspection counts by municipality."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
from sqlalchemy import create_engine
from cso_maps import make_inspection_map

geo_path = '../docs/assets/geo_json/'
geo_towns = geo_path + 'TOWNSSURVEY_POLYM_geojson_simple.json'
out_path = '../docs/assets/maps/'

disk_engine = create_engine('sqlite:///../get_data/AMEND.db')
data_ins = pd.read_sql_query('SELECT * FROM MAEEADP_Inspection', disk_engine)

data_ins_g_t = data_ins.groupby('Town')['Program'].count()

make_inspection_map(
    data_ins_g_t=data_ins_g_t,
    geo_towns_path=geo_towns,
    outpath=out_path + 'EEADP_ins_map_total.html',
)
