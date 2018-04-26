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
## Assign Census blocks to towns and watersheds
##########################

## Loop over Census block groups
bg_mapping = pd.DataFrame(index=[geo_blockgroups_dict[i]['properties']['GEOID'] for i in range(len(geo_blockgroups_dict))] , columns=['Town','Watershed'])
## Loop over block groups
for feature in geo_blockgroups_dict:
	polygon = shape(feature['geometry'])
	point = polygon.centroid
	## Loop over towns
	for town_feature in geo_towns_dict:
		town_polygon = shape(town_feature['geometry'])
		if town_polygon.contains(point):
			bg_mapping.loc[feature['properties']['GEOID'], 'Town'] = town_feature['properties']['TOWN'] 
	## Warn if a town was not found
	if bg_mapping.loc[feature['properties']['GEOID'], 'Town'] is np.nan:
		print('No Town found for Block Group #', str(cso_i))
	## Loop over watersheds
	for watershed_feature in geo_watersheds_dict:
		watershed_polygon = shape(watershed_feature['geometry'])
		if watershed_polygon.contains(point):
			bg_mapping.loc[feature['properties']['GEOID'], 'Watershed'] = watershed_feature['properties']['NAME'] 
	## Warn if a watershed was not found
	if bg_mapping.loc[feature['properties']['GEOID'], 'Town'] is np.nan:
		print('No Town found for Block Group #', str(cso_i))

data_ejs = pd.merge(data_ejs, bg_mapping, left_on = 'ID', right_index=True, how='left')


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
	fill_color='PuBu', fill_opacity=0.4, line_opacity=0.3, highlight=True,
	)
## Save to html
map_1.save(out_path+'NECIR_CSO_map_total.html')




##Scratch
#from matplotlib import pyplot as plt
#plt.ion()

#plt.figure()
#plt.scatter(data_ins_g_bg_j['VULSVI6PCT'], data_ins_g_bg_j['2011_Discharge_N'], c=data_ins_g_bg_j['ACSTOTPOP'])
#plt.colorbar(label='Total Population')
#plt.xlabel('VULSVI6PCT (EJ Demographic Index combining racial, income, language, education, and age characteristics)')
#plt.ylabel('Count of CSO discharges (2011)')
#plt.title('MA Census Block Groups')


## Do a pop-weighted average... since these are block groups, pop is similar anyway
data_egs_merge = pd.merge(
	data_ins_g_bg_j.groupby('ID')[['2011_Discharge_N', '2011_Discharges_MGal']].sum(),
	data_ejs, left_index = True, right_on='ID')

def pop_weighted_average(x, cols):
	w = x['ACSTOTPOP']
	out = []
	for col in cols:
		out += [np.sum(w * x[col].values) / np.sum(w)]
	return pd.Series(data = out, index=cols)

df_watershed_level = data_egs_merge.groupby('Watershed').apply(lambda x: pop_weighted_average(x, ['MINORPCT', 'LOWINCPCT', 'LINGISOPCT', 'OVER64PCT', 'VULSVI6PCT']))

df_town_level = data_egs_merge.groupby('Town').apply(lambda x: pop_weighted_average(x, ['MINORPCT', 'LOWINCPCT', 'LINGISOPCT', 'OVER64PCT', 'VULSVI6PCT']))




#############################
## Show layers for watershed, town, and census block group with CSO points
#############################


folium.LayerControl().add_to(m)
