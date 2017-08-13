import pandas as pd
import numpy as np
import folium
import json
from sqlalchemy import create_engine

import matplotlib as mpl
color_cycle = [c['color'] for c in list(mpl.rcParams['axes.prop_cycle'])]

geo_path = '../docs/assets/geo_json/'
geo_towns = geo_path+'TOWNSSURVEY_POLYM_geojson_simple.json'

geo_towns_dict = json.load(open(geo_towns))['features']

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
data_ins_g_t = data_ins.groupby('Town')['Program'].count()

## Map total inspections
map_1 = folium.Map(
	location=[42.29, -71.74], 
	zoom_start=8.2,
	tiles='Stamen Terrain',
	)

## Add popup information as illustrated here https://nbviewer.jupyter.org/github/ocefpaf/folium_notebooks/blob/618e31754aa9325cae6c315b687bea95f3f92ae4/test_geojson_popup.ipynb
## See example geojson file associated with it, here: https://raw.githubusercontent.com/ocefpaf/folium_notebooks/618e31754aa9325cae6c315b687bea95f3f92ae4/data/tri.json
for i in range(len(geo_towns_dict)):
	town = geo_towns_dict[i]['properties']['TOWN']
	if town in data_ins_g_t:
		## Gather town data
		inspections = data_ins_g_t.ix[town]
		pop10 = geo_towns_dict[i]['properties']['POP2010']
		## Add marker
		popup_text = town+'<br>Population (2010): '+str(pop10)+'<br>Total inspections: '+str(inspections)
		geo_towns_dict[i]['properties']['popupContent'] = popup_text
		
## Draw choropleth
map_1.choropleth(
	geo_path=geo_towns, 
	data_out=out_path+'EEADP_ins_data_total.json', 
	data=data_ins_g_t,
	key_on='feature.properties.TOWN',
	legend_name='Total # of inspections recorded',
	threshold_scale = list(np.percentile(data_ins_g_t, [0,50,90,100])),
	fill_color='PuBu', fill_opacity=0.7, line_opacity=0.3, highlight=True,
	)
### Add markers
#for i in range(len(geo_towns_dict)):
	#town = geo_towns_dict[i]['properties']['TOWN']
	#if town in data_ins_g_t:
		### Gather town data
		#inspections = data_ins_g_t.ix[town]
		#pop10 = geo_towns_dict[i]['properties']['POP2010']
		### Take average position of polygon points for marker center
		#raw_coords = geo_towns_dict[i]['geometry']['coordinates']
		#if np.ndim(raw_coords) == 2: # Take most complicated polygon if multiple are provided
			#j = np.argmax([np.shape(raw_coords[i][0])[0] for i in range(len(raw_coords))])
			#coords = raw_coords[j]
		#elif np.ndim(raw_coords) == 3:
			#coords = raw_coords
		#else: 
			#raise
		#mean_pos = list(np.mean(coords, axis=1)[0])[::-1]
		### Add marker
		#popup_text = town+'\nPopulation (2010): '+str(pop10)+'\nTotal inspections: '+str(inspections)
		#folium.Marker(mean_pos, popup=popup_text).add_to(map_1)
## Save to html
map_1.save(out_path+'EEADP_ins_map_total.html')


##########################
## Generate map - XXX
##########################

## Map inspections per year
#data_ins_g_yt = data_ins.groupby(['Year','Town']).Program.count()
