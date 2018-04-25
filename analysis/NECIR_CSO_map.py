import pandas as pd
import numpy as np
import folium
import json
from shapely.geometry import shape, Point
from sqlalchemy import create_engine

import matplotlib as mpl
color_cycle = [c['color'] for c in list(mpl.rcParams['axes.prop_cycle'])]

##########################
## Load shapefiles
##########################

geo_path = '../docs/assets/geo_json/'
geo_towns = geo_path+'TOWNSSURVEY_POLYM_geojson_simple.json'
geo_watersheds = geo_path+'watshdp1_geojson_simple.json'
geo_blockgroups = geo_path+'cb_2017_25_bg_500k.json'

geo_towns_dict = json.load(open(geo_towns))['features']
geo_watersheds_dict = json.load(open(geo_watersheds))['features']
geo_blockgroups_dict = json.load(open(geo_blockgroups))['features']

out_path = '../docs/assets/maps/'

def safe_float(x):
	try:
		return float(x)
	except:
		return np.nan

##########################
## Load data
##########################

## Load database
disk_engine = create_engine('sqlite:///../get_data/AMEND.db')

## Get CSO data
data_cso = pd.read_sql_query('SELECT * FROM NECIR_CSO_2011', disk_engine)
data_cso['2011_Discharges_MGal'] = data_cso['2011_Discharges_MGal'].apply(safe_float)
data_cso['2011_Discharge_N'] = data_cso['2011_Discharge_N'].apply(safe_float)

## Get EJSCREEN data
data_ejs = pd.read_sql_query('SELECT * FROM EPA_EJSCREEN_2017', disk_engine)
data_ejs['ID'] = data_ejs['ID'].astype(str)

##########################
## Lookup CSOs assignment to census blocks
##########################

## Loop over Census block groups
data_cso['BlockGroup'] = np.nan
## Loop over CSO outfalls
for cso_i in range(len(data_cso)):
	point = Point(data_cso.iloc[cso_i]['Longitude'], data_cso.iloc[cso_i]['Latitude'])
	for feature in geo_blockgroups_dict:
		polygon = shape(feature['geometry'])
		if polygon.contains(point):
			data_cso.loc[cso_i, 'BlockGroup'] = feature['properties']['GEOID'] 
	## Warn if a blockgroup was not found
	if data_cso.loc[cso_i, 'BlockGroup'] is np.nan:
		print('No block group found for CSO #', str(cso_i))



##########################
## Generate map - total gallons by Census block group
##########################

## Get counts by block group
data_ins_g_bg = data_cso.groupby('BlockGroup').sum()[['2011_Discharges_MGal', '2011_Discharge_N']]
data_ins_g_bg_j = pd.merge(data_ins_g_bg, data_ejs, left_index=True, right_on ='ID', how='left')

## Map total discharge volume
map_1 = folium.Map(
	location=[42.29, -71.74], 
	zoom_start=8.2,
	tiles='Stamen Terrain',
	)

## Draw choropleth
map_1.choropleth(
	geo_data=geo_blockgroups, 
	data=data_ins_g_bg['2011_Discharges_MGal'],
	key_on='feature.properties.GEOID',
	legend_name='Total volume of discharge (2011; Millions of gallons)',
	threshold_scale = list(np.nanpercentile(data_ins_g_bg, [0,50,90,100])),  ## NOTE Do I need to index these in order??
	fill_color='PuBu', fill_opacity=0.7, line_opacity=0.3, highlight=True,
	)
## Save to html
map_1.save(out_path+'NECIR_CSO_map_total.html')





##Scratch
plt.figure()
plt.scatter(data_ins_g_bg_j['LOWINCPCT'], data_ins_g_bg_j['2011_Discharge_N'], c=data_ins_g_bg_j['ACSTOTPOP'])
plt.colorbar(label='Total Population')
plt.xlabel('% low income')
plt.ylabel('Count of CSO discharges (2011)')
plt.title('MA Census Block Groups')


