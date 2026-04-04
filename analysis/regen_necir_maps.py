"""Regenerate NECIR CSO maps from cached CSV data using Plotly.

Reads the intermediate data files produced by a previous full NECIR_CSO_map.py
run so we don't need to re-run the expensive geopandas/Stan pipeline.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
from cso_maps import make_discharge_map, make_ej_map

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.join(_HERE, '..')
DATA_PATH = os.path.join(_ROOT, 'docs', 'data') + os.sep
OUT_PATH  = os.path.join(_ROOT, 'docs', 'assets', 'maps') + os.sep
GEO_PATH  = os.path.join(_ROOT, 'docs', 'assets', 'geo_json') + os.sep

slug = 'NECIR_CSO'

data_cso       = pd.read_csv(DATA_PATH + f'{slug}_data_cso.csv')
# NECIR has no separate operator field; add a column so the point trace doesn't error
data_cso['Operator'] = data_cso['Municipality']
data_ins_g_bg  = pd.read_csv(DATA_PATH + f'{slug}_data_ins_g_bg.csv', index_col='GEOID')
data_ins_g_muni= pd.read_csv(DATA_PATH + f'{slug}_data_ins_g_muni_j.csv', index_col='Town')
data_egs_merge = pd.read_csv(DATA_PATH + f'{slug}_data_egs_merge.csv.gz')
df_watershed   = pd.read_csv(DATA_PATH + f'{slug}_df_watershed_level.csv', index_col='Watershed')
df_town        = pd.read_csv(DATA_PATH + f'{slug}_df_town_level.csv', index_col='Town')

# data_ins_g_bg uses NECIR column names
VOL_COL   = '2011_Discharges_MGal'
COUNT_COL = '2011_Discharge_N'

geo_bg   = GEO_PATH + 'cb_2017_25_bg_500k.json'
geo_muni = GEO_PATH + 'TOWNSSURVEY_POLYM_geojson_simple.json'
geo_ws   = GEO_PATH + 'watshdp1_geojson_simple.json'

# data_ins_g_ws - derive from egs_merge
data_ins_g_ws = (
    data_egs_merge
    .dropna(subset=['Watershed'])
    .groupby('Watershed')[[VOL_COL, COUNT_COL]].sum()
    .fillna(0)
)
# data_egs_merge needs index = ID for CBG layer
data_egs_merge_idx = data_egs_merge.set_index('ID')

print('Making NECIR total discharge map...')
make_discharge_map(
    data_cso=data_cso,
    data_ins_g_bg=data_ins_g_bg,
    data_ins_g_muni=data_ins_g_muni,
    data_ins_g_ws=data_ins_g_ws,
    geo_blockgroups_path=geo_bg,
    geo_towns_path=geo_muni,
    geo_watershed_path=geo_ws,
    outpath=OUT_PATH + f'{slug}_map_total.html',
    vol_col=VOL_COL,
    count_col=COUNT_COL,
    lat_col='Latitude',
    lon_col='Longitude',
    loc_col='Nearest_Pipe_Address',
    waterbody_col='DischargesBody',
    muni_col='Municipality',
    operator_col='Operator',
    period_label='2011',
)

EJ_VARS = [
    ('MINORPCT',   'Fraction of population identifying as non-white'),
    ('LOWINCPCT',  'Fraction of population with low income'),
    ('LINGISOPCT', 'Fraction of population linguistically isolated'),
]

for ej_col, ej_label in EJ_VARS:
    print(f'Making NECIR EJ map: {ej_col}...')
    make_ej_map(
        data_cso=data_cso,
        data_egs_merge=data_egs_merge_idx,
        df_town_level=df_town,
        df_watershed_level=df_watershed,
        geo_blockgroups_path=geo_bg,
        geo_towns_path=geo_muni,
        geo_watershed_path=geo_ws,
        outpath=OUT_PATH + f'{slug}_map_EJ_{ej_col}.html',
        ej_col=ej_col,
        ej_label=ej_label,
        vol_col=VOL_COL,
        count_col=COUNT_COL,
        lat_col='Latitude',
        lon_col='Longitude',
        loc_col='Nearest_Pipe_Address',
        waterbody_col='DischargesBody',
        muni_col='Municipality',
        operator_col='Operator',
        period_label='2011',
    )

print('Done.')
