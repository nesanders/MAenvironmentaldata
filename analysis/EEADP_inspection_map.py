import pandas as pd
import numpy as np
import folium
from sqlalchemy import create_engine

import matplotlib as mpl
color_cycle = [c['color'] for c in list(mpl.rcParams['axes.prop_cycle'])]

geo_path = '../docs/assets/geo_json/'
geo_towns = geo_path+'TOWNSSURVEY_POLYM_geojson_simple.json'

out_path = '../docs/assets/maps/'

##########################
## Load data
##########################

## Load database
disk_engine = create_engine('sqlite:///../get_data/AMEND.db')

## Get inspection data
data_ins = pd.read_sql_query('SELECT * FROM MAEEADP_Inspection', disk_engine)
data_ins['Year'] = pd.to_datetime(data_ins['InspectionDate']).apply(lambda x: x.year)


##########################
## Generate map - total counts by town
##########################

## Get counts by town
data_ins_g_t = data_ins.groupby('Town')[['Program']].count().reset_index()

## Map total inspections
map_1 = folium.Map(
	location=[42.29, -71.74], 
	zoom_start=8.2,
	tiles='Stamen Terrain',
	)
map_1.choropleth(
	geo_path=geo_towns, 
	data_out=out_path+'EEADP_ins_data_total.json', 
	data=data_ins_g_t,
	columns=['Town','Program'],
	key_on='feature.properties.TOWN',
	legend_name='Total # of inspections recorded',
	fill_color='PuBu', fill_opacity=0.7, line_opacity=0.3, highlight=True,
	)
map_1.save(out_path+'EEADP_ins_map_total.html')


##########################
## Generate map - XXX
##########################

## Map inspections per year
#data_ins_g_yt = data_ins.groupby(['Year','Town']).Program.count()
