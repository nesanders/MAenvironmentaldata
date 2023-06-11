"""Generate folium-based map visualizations and pystan regression model fits for CSO discharge distributions using
NECIR CSO data.

NOTE - this code was updated in 2023 to use pystan 3 conventions

This code uses joblib.Memory to do local disk caching of expensive operations (geo polygon lookups to assign census 
blocks to town and watershed units). If you rerun the script locally, it should hit the cache and skip those
computations.

NOTE - if you run into pystan errors when executing this script in a conda environment, try using 
[this solution](https://github.com/stan-dev/pystan/issues/294#issuecomment-988791438)
to update the C compilers in the env.
```
conda install -c conda-forge c-compiler cxx-compiler
```

NOTE: We define CSOAnalysis as a class so that we can easily inherit and overwrite methods from it, e.g. in the 
EEA_DP_CSO_map.py script.
"""

import json
from typing import Any, Dict, List, Optional, Tuple

import chartjs
import folium
from joblib import Memory
import matplotlib as mpl
from matplotlib import pyplot as plt
from matplotlib import cm
import pandas as pd
import numpy as np
from shapely.geometry import Point, shape
from shapely.strtree import STRtree
import sqlalchemy
import stan

# Create a joblib cache
memory = Memory('necir_cso_data_cache', verbose=1)

# Colors to use in plots
COLOR_CYCLE = [c['color'] for c in list(mpl.rcParams['axes.prop_cycle'])]

DATABASE_URI = 'sqlite:///../get_data/AMEND.db'

GeoList = List[Dict[str, Any]]

# -------------------------
# Standalone functions
# -------------------------

def hex2rgb(hexcode: str) -> Tuple[int, int, int]:
    """Convert a hex color to RGB tuple)
    See http://www.psychocodes.in/rgb-to-hex-conversion-and-hex-to-rgb-conversion-in-python.html
    See https://stackoverflow.com/a/29643643
    """
    rgb = tuple(int(hexcode.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    return rgb

def safe_float(x: Any) -> float:
    """Return a float if possible, or else a np.nan value.
    """
    try:
        return float(x)
    except:
        return np.nan

def get_engine() -> sqlalchemy.engine.Engine:
    """Establish a sqlite database connection
    """
    print('Opening SQL engine')
    return sqlalchemy.create_engine(DATABASE_URI)

def weight_mean(x, weights, N=1000):
    """Boostrapped weighted mean function
    """
    avgs = np.zeros(N)
    nonan_sel = (np.isnan(x) == 0) & (np.isnan(weights) == 0)
    x = x[nonan_sel]
    weights = weights[nonan_sel]
    for i in range(N):
        sel = np.random.randint(len(x), size=len(x))
        avgs[i] = np.average(x[sel], weights=weights[sel])
    return np.mean(avgs), np.std(avgs)

def pick_non_null(x: list) -> Optional[str]:
    """Return the first non-null value from a list, if any.
    """
    for val in x:
        if val is not None:
            return val
    return None

def is_nan(x: Any) -> bool:
    """Safely check if a value is np.nan.
    """
    if isinstance(x, float) and np.isnan(x):
        return True
    return False

def lookup_town_for_feature(town_feature, point) -> Optional[str]:
    """Try to assign an input feature to a town
    """
    town_polygon = shape(town_feature['geometry'])
    if town_polygon.contains(point):
        return town_feature['properties']['TOWN'] 
    else:
        return None

def lookup_watershed_for_feature(watershed_feature, point) -> Optional[str]:
    """Try to assign an input feature to a watershed
    """
    town_polygon = shape(watershed_feature['geometry'])
    if town_polygon.contains(point):
        return watershed_feature['properties']['NAME']
    else:
        return None

def pop_weighted_average(x, cols):
    w = x['ACSTOTPOP']
    out = []
    for col in cols:
        out += [np.sum(w * x[col].values) / np.sum(w)]
    return pd.Series(data = out, index=cols)

@memory.cache
def _assign_cso_data_to_census_blocks(data_cso: pd.DataFrame, geo_blockgroups_list: GeoList, 
    latitude_col: str, longitude_col: str) -> pd.DataFrame:
    """Add a new 'BlockGroup' column to `data_cso` assigning CSOs to Census block groups.
    """
    print('Assigning CSO data to census blocks')
    data_out = data_cso.copy()
    ## Loop over Census block groups
    data_out['BlockGroup'] = np.nan
    ## Loop over CSO outfalls
    for cso_i in range(len(data_out)):
        point = Point(data_out.iloc[cso_i][longitude_col], data_out.iloc[cso_i][latitude_col])
        for feature in geo_blockgroups_list:
            polygon = shape(feature['geometry'])
            if polygon.contains(point):
                data_out.loc[cso_i, 'BlockGroup'] = feature['properties']['GEOID'] 
        ## Warn if a blockgroup was not found
        if is_nan(data_out.loc[cso_i, 'BlockGroup']):
            print('No block group found for CSO #', str(cso_i))
    return data_out

@memory.cache
def _assign_cso_data_to_census_blocks_with_strtree(data_cso: pd.DataFrame, geo_blockgroups_list: GeoList, 
    latitude_col: str, longitude_col: str) -> pd.DataFrame:
    """Add a new 'BlockGroup' column to `data_cso` assigning CSOs to Census block groups using Shapely's
    STRTree class, based on a Sort-Tile-Recursive algorithm.
    
    This should be functionally equivalent to `_assign_cso_data_to_census_blocks`, but much faster.
    """
    print('Assigning CSO data to census blocks')
    data_out = data_cso.copy()
    # Loop over Census block groups
    data_out['BlockGroup'] = np.nan
    # Create STRTree
    census_block_tree = STRtree([shape(feature['geometry']) for feature in geo_blockgroups_list])
    cso_points = [Point(data_out.iloc[cso_i][longitude_col], data_out.iloc[cso_i][latitude_col]) for cso_i in range(len(data_out))]
    # Query for containment
    result_indices = census_block_tree.query(cso_points, predicate='within')
    # Parse the results
    for cso_i in range(len(data_out)):
        cso_result_set = (np.array(result_indices[0]) == cso_i)
        ## Warn if a blockgroup was not found
        if sum(cso_result_set) == 0:
            print(f'No block group found for CSO #{cso_i}')
            continue
        ## Warn if multiple blockgroups were found
        if sum(cso_result_set) > 1:
            print(f'N={sum(cso_result_set)} block groups were found for CSO #{cso_i}; will pick the first')
        data_out.loc[cso_i, 'BlockGroup'] = geo_blockgroups_list[result_indices[1][cso_result_set][0]]['properties']['GEOID']
    return data_out

@memory.cache
def assign_ej_data_to_geo_bins(data_ejs: pd.DataFrame, geo_towns_list: GeoList, geo_watersheds_list: GeoList, 
    geo_blockgroups_list: GeoList) -> pd.DataFrame:
    """Return a version of `data_ejs` with added 'Town' and 'Watershed' columns.
    """
    print('Adding Town and Watershed labels to EJ data')
    ## Loop over Census block groups
    bg_mapping = pd.DataFrame(
        index=[geo_blockgroups_list[i]['properties']['GEOID'] for i in range(len(geo_blockgroups_list))], 
        columns=['Town','Watershed'])
    ## Loop over block groups
    for feature in geo_blockgroups_list:
        polygon = shape(feature['geometry'])
        point = polygon.centroid
        ## Loop over towns
        bg_mapping.loc[feature['properties']['GEOID'], 'Town'] = pick_non_null(
            lookup_town_for_feature(town_feature, point) for town_feature in geo_towns_list)
        ## Warn if a town was not found
        if is_nan(bg_mapping.loc[feature['properties']['GEOID'], 'Town']):
            print(f"No Town found for GEOID {feature['properties']['GEOID']}")
        ## Loop over watersheds
        bg_mapping.loc[feature['properties']['GEOID'], 'Watershed'] = pick_non_null(
            lookup_watershed_for_feature(watershed_feature, point) for watershed_feature in geo_watersheds_list)
        ## Warn if a watershed was not found
        if is_nan(bg_mapping.loc[feature['properties']['GEOID'], 'Watershed']):
            print(f"No Watershed found for GEOID {feature['properties']['GEOID']}")

    data_ejs = pd.merge(data_ejs, bg_mapping, left_on = 'ID', right_index=True, how='left')
    return data_ejs

@memory.cache
def assign_ej_data_to_geo_bins_with_strtree(data_ejs: pd.DataFrame, geo_towns_list: GeoList, geo_watersheds_list: GeoList, 
    geo_blockgroups_list: GeoList) -> pd.DataFrame:
    """Return a version of `data_ejs` with added 'Town' and 'Watershed' columns.
    
    This should be functionally equivalent to `assign_ej_data_to_geo_bins`, but much faster. But it still takes 
    a few minutes to run over all block groups.
    """    
    print('Adding Town and Watershed labels to EJ data')
    ## Loop over Census block groups
    bg_mapping = pd.DataFrame(
        index=[geo_blockgroups_list[i]['properties']['GEOID'] for i in range(len(geo_blockgroups_list))], 
        columns=['Town','Watershed'])
    
    cbg_points = {feature['properties']['GEOID']: shape(feature['geometry']).centroid for feature in geo_blockgroups_list}
    for geo_type, geo_list, geo_key in [
            ('Town', geo_towns_list, 'TOWN'), 
            ('Watershed', geo_watersheds_list, 'NAME')
        ]:
        # Create STRTrees
        tree = STRtree([shape(feature['geometry']) for feature in geo_list])
        # Query for containment
        result_indices = tree.query(list(cbg_points.values()), predicate='within')
        # Parse the results
        for cbg_i, cbg_id in enumerate(cbg_points.keys()):
            result_set = (np.array(result_indices[0]) == cbg_i)
            ## Warn if a town was not found
            if sum(result_set) == 0:
                print(f'No {geo_type} found for Census Block Group #{cbg_id}')
                continue
            ## Warn if multiple towns were found
            if sum(result_set) > 1:
                print(f'N={sum(result_set)} {geo_type}s were found for Census Block Group #{cbg_id}; will pick the first')
            bg_mapping.loc[cbg_id, geo_type] = geo_list[result_indices[1][result_set][0]]['properties'][geo_key]

    data_ejs = pd.merge(data_ejs, bg_mapping, left_on='ID', right_index=True, how='left')
    return data_ejs

@memory.cache
def _apply_pop_weighted_avg( data_cso: pd.DataFrame, data_ejs: pd.DataFrame, discharge_vol_col: str, discharge_count_col: str
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Calculate population weighted averages for EJ characteristics, averaging over block group, watershed, and town.
    """
    print('Calculating population weighted averages')
    ## Get counts by block group
    data_ins_g_bg = data_cso.groupby('BlockGroup').sum()[[discharge_vol_col, discharge_count_col]]
    data_ins_g_bg_j = pd.merge(data_ins_g_bg, data_ejs, left_index=True, right_on ='ID', how='left')
    data_egs_merge = pd.merge(
        data_ins_g_bg_j.groupby('ID')[[discharge_count_col, discharge_vol_col]].sum(),
        data_ejs, left_index = True, right_on='ID', how='outer')

    ## Get counts by municipality
    data_ins_g_muni_j = pd.merge(data_cso, data_ejs, left_on='BlockGroup', right_on='ID', how='outer')\
                        .groupby('Town').sum()[[discharge_vol_col, discharge_count_col]].fillna(0)

    ## Get counts by watershed
    data_ins_g_ws_j = pd.merge(data_cso, data_ejs, left_on='BlockGroup', right_on='ID', how='outer')\
                        .groupby('Watershed').sum()[[discharge_vol_col, discharge_count_col]].fillna(0)

    df_watershed_level = data_egs_merge.groupby('Watershed').apply(
        lambda x: pop_weighted_average(x, ['MINORPCT', 'LOWINCPCT', 'LINGISOPCT', 'OVER64PCT', 'VULSVI6PCT']))

    df_town_level = data_egs_merge.groupby('Town').apply(
        lambda x: pop_weighted_average(x, ['MINORPCT', 'LOWINCPCT', 'LINGISOPCT', 'OVER64PCT', 'VULSVI6PCT']))
    
    return data_ins_g_bg, data_ins_g_muni_j, data_ins_g_ws_j, data_egs_merge, df_watershed_level, df_town_level

# -------------------------
# Analysis class
# -------------------------

class CSOAnalysis():
    """Class containing methods and attributes related to CSO EJ analysis.
    """
    
    output_slug_dataset: str = 'NECIR'
    output_slug: str = 'NECIR_CSO'
    discharge_vol_col: str = '2011_Discharges_MGal'
    discharge_count_col: str = '2011_Discharge_N'
    outfall_address_col: str = 'Nearest_Pipe_Address'
    water_body_col: str = 'DischargesBody'
    municipality_col: str = 'Municipality'
    latitude_col: str = 'Latitude'
    longitude_col: str = 'Longitude'
    cso_data_year: int = 2011
    
    def __init__(
        self, 
        fact_file: str='../docs/data/facts_NECIR_CSO.yml',
        out_path: str='../docs/assets/maps/',
        fig_path: str='../docs/assets/figures/',
        stan_model_code: str='discharge_regression_model.stan',
        geo_towns_path: str='../docs/assets/geo_json/TOWNSSURVEY_POLYM_geojson_simple.json',
        geo_watershed_path: str='../docs/assets/geo_json/watshdp1_geojson_simple.json',
        geo_blockgroups_path: str='../docs/assets/geo_json/cb_2017_25_bg_500k.json',
        make_maps: bool=True,
        make_charts: bool=True,
        make_regression: bool=True
    ):
        """Initialize parameters
        
        Parameters
        ----------
        fact_file: str
            Path of yml file to write calculated results to, by default '../docs/data/facts_NECIR_CSO.yml',
        out_path: str
            Path of directory to write map outputs to, by default '../docs/assets/maps/',
        fig_path: str
            Path of directory to write chart outputs to, by default '../docs/assets/figures/',
        stan_model_code: str
            Path to file with stan regression model code, by default 'discharge_regression_model.stan',
        geo_towns_path: str
            Path to geojson file with municipality polygons, by default '../docs/assets/geo_json/TOWNSSURVEY_POLYM_geojson_simple.json',
        geo_watershed_path: str
            Path to geojson file with watershed polygons, by default '../docs/assets/geo_json/watshdp1_geojson_simple.json',
        geo_blockgroups_path: str
            Path to geojson file with Census block group polygons, by default '../docs/assets/geo_json/cb_2017_25_bg_500k.json',
        make_maps: bool
            Whether or not to execute the functions to generate maps, by default True,
        make_charts: bool
            Whether or not to execute the functions to generate charts, by default True,
        make_regression: bool
            Whether or not to execute the functions to generate regression models, by default True
        """
        # Establish file to export facts
        self.fact_file = fact_file
        # Location to write out map and figure assets
        self.out_path = out_path
        self.fig_path = fig_path
        # Location of Stan regression model code
        self.stan_model_code = stan_model_code
        # Location of input geo json data
        self.geo_towns_path = geo_towns_path
        self.geo_watershed_path = geo_watershed_path
        self.geo_blockgroups_path = geo_blockgroups_path
        # Year represented by the CSO dataset
        self.cso_data_year = 2011
        self.make_maps = make_maps
        self.make_charts = make_charts
        self.make_regression = make_regression
   
    
    # -------------------------
    # Data loading methods
    # -------------------------
    
    def get_geo_files(self) -> Tuple[GeoList, GeoList, GeoList, GeoList]:
        """Load and return geo json files.
        """
        geo_towns_list = json.load(open(self.geo_towns_path))['features']
        geo_watersheds_list = json.load(open(self.geo_watershed_path))['features']
        geo_blockgroups_list = json.load(open(self.geo_blockgroups_path))['features']
        return geo_towns_list, geo_watersheds_list, geo_blockgroups_list

    
    def load_data_cso(self) -> pd.DataFrame:
        """Load NECIR 2011 CSO data
        """
        print('Loading NECIR 2011 CSO data')
        disk_engine = get_engine()
        data_cso = pd.read_sql_query('SELECT * FROM NECIR_CSO_2011', disk_engine)
        data_cso[self.discharge_vol_col] = data_cso[self.discharge_vol_col].apply(safe_float)
        data_cso[self.discharge_count_col] = data_cso[self.discharge_count_col].apply(safe_float)
        return data_cso
    
    @staticmethod
    def load_data_ej() -> pd.DataFrame:
        """Load EJSCREEN data
        """
        print('Loading EJSCREEN data')
        disk_engine = get_engine()
        data_ejs = pd.read_sql_query('SELECT * FROM EPA_EJSCREEN_2017', disk_engine)
        data_ejs['ID'] = data_ejs['ID'].astype(str)
        return data_ejs

    def load_data(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Load all data, CSO and EJ.
        """
        print('Loading all data')
        data_cso = self.load_data_cso()
        data_ejs = self.load_data_ej()
        return data_cso, data_ejs

    # -------------------------
    # Data transforming methods
    # -------------------------

    def assign_cso_data_to_census_blocks(self, data_cso: pd.DataFrame, geo_blockgroups_list: GeoList) -> pd.DataFrame:
        """Add a new 'BlockGroup' column to `data_cso` assigning CSOs to Census block groups.
        """
        # This is an older, much slower method, which should yield equivalent results
        #_assign_cso_data_to_census_blocks(data_cso, geo_blockgroups_list, self.latitude_col, self.longitude_col)
        return _assign_cso_data_to_census_blocks_with_strtree(data_cso, geo_blockgroups_list, self.latitude_col, self.longitude_col)
    
    def apply_pop_weighted_avg(self, data_cso: pd.DataFrame, data_ejs: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Calculate population weighted averages for EJ characteristics, averaging over block group, watershed, and town.
        """
        return _apply_pop_weighted_avg(data_cso, data_ejs, self.discharge_vol_col, self.discharge_count_col)

    # -------------------------
    # Mapping functions
    # -------------------------
    
    def make_map_discharge_volumes(self, data_cso: pd.DataFrame, geo_watersheds_list: GeoList, data_ins_g_bg: pd.DataFrame, 
        data_ins_g_muni_j: pd.DataFrame, data_ins_g_ws_j: pd.DataFrame):
        """
        Map of discharge volumes with layers for watershed, town, and census block group with CSO points
        """
        print('Making map of discharge volumes')
        ## Map total discharge volume
        map_1 = folium.Map(
            location=[42.29, -71.74], 
            zoom_start=8.2,
            tiles='Stamen Terrain',
            )

        # We show only the watershed view by default
        ## Draw choropleth layer for census blocks
        map_1.choropleth(
            geo_data=self.geo_blockgroups_path, 
            name='Census Block Groups',
            data=data_ins_g_bg[self.discharge_vol_col],
            key_on='feature.properties.GEOID',
            legend_name=f'Block Group: Total volume of discharge ({self.cso_data_year}; Millions of gallons)',
            threshold_scale = list(np.nanpercentile(data_ins_g_bg[self.discharge_vol_col], [0,25,50,75,100])),  
            fill_color='BuGn', fill_opacity=0.7, line_opacity=0.3, highlight=True, show=False
            )

        ## Draw Choropleth layer for towns
        map_1.choropleth(
            geo_data=self.geo_towns_path, 
            name='Municipalities',
            data=data_ins_g_muni_j[self.discharge_vol_col],
            key_on='feature.properties.TOWN',
            legend_name=f'Municipality: Total volume of discharge ({self.cso_data_year}; Millions of gallons)',
            threshold_scale = [0] + list(np.nanpercentile(
                data_ins_g_muni_j[self.discharge_vol_col][data_ins_g_muni_j[self.discharge_vol_col] > 0], 
                [25,50,75,100])),  
            fill_color='PuRd', fill_opacity=0.7, line_opacity=0.3, highlight=True, show=False
            )

        ## Draw Choropleth layer for watersheds
        map_1.choropleth(
            geo_data=self.geo_watershed_path, 
            name='Watersheds',
            data=data_ins_g_ws_j[self.discharge_vol_col],
            key_on='feature.properties.NAME',
            legend_name=f'Watershed: Total volume of discharge ({self.cso_data_year}; Millions of gallons)',
            threshold_scale = list(np.nanpercentile(data_ins_g_ws_j[self.discharge_vol_col], [0,25,50,75,100])),  
            fill_color='PuBu', fill_opacity=0.7, line_opacity=0.3, highlight=True,
            )

        ## Add points layer for CSOs
        for i in range(len(data_cso)):
            ## Gather CSO data
            cso = data_cso.iloc[i]
            ## Add marker
            html="""
            <h1>CSO outfall at {address}</h1>
            <p>
            Discharge Body: {body}<br>
            Municipality: {muni}<br>
            Discharge volume ({cso_data_year}): {vol} (Millions of gallons)<br>
            Discharge frequency ({cso_data_year}): {N} discharges<br>
            </p>
            """.format(
                    address = cso[self.outfall_address_col],
                    body = cso[self.water_body_col],
                    muni = cso[self.municipality_col],
                    vol = cso[self.discharge_vol_col],
                    N = cso[self.discharge_count_col],
                    cso_data_year = self.cso_data_year
                )
            iframe = folium.IFrame(html=html, width=400, height=200)
            popup = folium.Popup(iframe, max_width=500)
            folium.RegularPolygonMarker(
                    location=(cso[self.latitude_col], cso[self.longitude_col]), 
                    popup=popup, 
                    number_of_sides=8, 
                    radius=6, 
                    color='green',
                    fill_color='green',
                ).add_to(map_1)

        ## Add labels for watersheds
        for feature in geo_watersheds_list:
            pos = shape(feature['geometry']).centroid.coords.xy
            pos = (pos[1][0], pos[0][0])
            folium.Marker(pos, icon=folium.features.DivIcon(
                icon_size=(150,36),
                icon_anchor=(7,20),
                html='<div style="font-size: 12pt; color: blue; opacity: 0.3">{}</div>'.format(feature['properties']['NAME']),
                )).add_to(map_1)

        ## Add a layer control
        folium.LayerControl(collapsed=False).add_to(map_1)

        ## Save to html
        map_1.save(self.out_path + f'{self.output_slug}_map_total.html')

    def make_map_ej_characteristics(self, data_egs_merge: pd.DataFrame, data_cso: pd.DataFrame, 
        df_town_level: pd.DataFrame, df_watershed_level: pd.DataFrame, geo_watersheds_list: GeoList):
        """Map of EJ characteristics with layers for watershed, town, and census block group with CSO points
        """
        print('Making map of EJ characteristics')
        for col, col_label in (
            ('MINORPCT', 'Fraction of population identifying as non-white'),
            ('LOWINCPCT', 'Fraction of population with income less than twice the Federal poverty limit'),
            ('LINGISOPCT', 'Fraction of population in households whose adults speak English less than "very well"'),
            ):

            ## Map total discharge volume
            map_2 = folium.Map(
                location=[42.29, -71.74], 
                zoom_start=8.2,
                tiles='Stamen Terrain',
                )

            # We show only the watershed by default
            ## Draw choropleth layer for census blocks
            map_2.choropleth(
                geo_data=self.geo_blockgroups_path, 
                name='Census Block Groups',
                data=data_egs_merge[col],
                key_on='feature.properties.GEOID',
                legend_name='Block Group: '+col_label,
                threshold_scale = list(np.nanpercentile(data_egs_merge[col], [0,25,50,75,100])),  
                fill_color='BuGn', fill_opacity=0.7, line_opacity=0.3, highlight=True, show=False
                )

            ## Draw Choropleth layer for towns
            map_2.choropleth(
                geo_data=self.geo_towns_path, 
                name='Municipalities',
                data=df_town_level[col],
                key_on='feature.properties.TOWN',
                legend_name='Municipality: '+col_label,
                threshold_scale = list(np.nanpercentile(df_town_level[col], [0,25,50,75,100])),  
                fill_color='PuRd', fill_opacity=0.7, line_opacity=0.3, highlight=True, show=False
                )

            ## Draw Choropleth layer for watersheds
            map_2.choropleth(
                geo_data=self.geo_watershed_path, 
                name='Watersheds',
                data=df_watershed_level[col],
                key_on='feature.properties.NAME',
                legend_name='Watershed: '+col_label,
                threshold_scale = list(np.nanpercentile(df_watershed_level[col], [0,25,50,75,100])),  
                fill_color='PuBu', fill_opacity=0.7, line_opacity=0.3, highlight=True,
                )

            ## Add points layer for CSOs
            for i in range(len(data_cso)):
                ## Gather CSO data
                cso = data_cso.iloc[i]
                ## Add marker
                html="""
                <h1>CSO outfall at {address}</h1>
                <p>
                Discharge Body: {body}<br>
                Municipality: {muni}<br>
                Discharge volume ({cso_data_year}): {vol} (Millions of gallons)<br>
                Discharge frequency ({cso_data_year}): {N} discharges<br>
                </p>
                """.format(
                        address = cso[self.outfall_address_col],
                        body = cso[self.water_body_col],
                        muni = cso[self.municipality_col],
                        vol = cso[self.discharge_vol_col],
                        N = cso[self.discharge_count_col],
                        cso_data_year = self.cso_data_year
                    )
                iframe = folium.IFrame(html=html, width=400, height=200)
                popup = folium.Popup(iframe, max_width=500)
                folium.RegularPolygonMarker(
                        location=(cso[self.latitude_col], cso[self.longitude_col]), 
                        popup=popup, 
                        number_of_sides=8, 
                        radius=6, 
                        color='green',
                        fill_color='green',
                    ).add_to(map_2)

            ## Add labels for watersheds
            for feature in geo_watersheds_list:
                pos = shape(feature['geometry']).centroid.coords.xy
                pos = (pos[1][0], pos[0][0])
                folium.Marker(pos, icon=folium.features.DivIcon(
                    icon_size=(150,36),
                    icon_anchor=(7,20),
                    html='<div style="font-size: 12pt; color: blue; opacity: 0.3">{}</div>'.format(feature['properties']['NAME']),
                    )).add_to(map_2)

            ## Add a layer control
            folium.LayerControl(collapsed=False).add_to(map_2)

            ## Save to html
            map_2.save(self.out_path + f'{self.output_slug}_map_EJ_'+col+'.html')

    @staticmethod
    def make_chart_summary_ej_characteristics_watershed(df_watershed_level: pd.DataFrame, 
        outpath: str='../docs/_includes/charts/EJSCREEN_demographics_watershed.html'):
        """Summary of EJ characteristics per watershed
        """
        print('Making map of EJ characteristics per watershed')
        mychart = chartjs.chart("EJ characteristics by watershed", "Bar", 640, 480)
        sel = np.argsort(df_watershed_level['MINORPCT'])
        mychart.set_labels(df_watershed_level.index.values[sel].tolist())
            
        for i, col, col_label in (
            (0, 'MINORPCT', 'Fraction of population identifying as non-white'),
            (1, 'LOWINCPCT', 'Fraction of population with income less than twice the Federal poverty limit'),
            (2, 'LINGISOPCT', 'Fraction of population in households whose adults speak English less than "very well"'),
            ):

            mychart.add_dataset(df_watershed_level[col][sel].values.tolist(), 
                col_label,
                backgroundColor="'rgba({},0.8)'".format(", ".join([str(x) for x in hex2rgb(COLOR_CYCLE[i])])),
                yAxisID= "'y-axis-0'")
        mychart.set_params(JSinline = 0, ylabel = 'Fraction of households', xlabel='Watershed',
            scaleBeginAtZero=1, x_autoskip=False)

        mychart.jekyll_write(outpath)

    def make_chart_summary_ej_characteristics_town(self, df_town_level: pd.DataFrame, 
        outpath: str='../docs/_includes/charts/EJSCREEN_demographics_municipality.html'):
        """Summary of EJ characteristics per town
        """
        print('Making summary chart of EJ data by town')
        mychart = chartjs.chart("EJ characteristics by municipality", "Bar", 640, 480)
        sel = np.argsort(df_town_level['MINORPCT'])
        mychart.set_labels(df_town_level.index.values[sel].tolist())
            
        for i, col, col_label in (
            (0, 'MINORPCT', 'Fraction of population identifying as non-white'),
            (1, 'LOWINCPCT', 'Fraction of population with income less than twice the Federal poverty limit'),
            (2, 'LINGISOPCT', 'Fraction of population in households whose adults speak English less than "very well"'),
            ):

            mychart.add_dataset(df_town_level[col][sel].values.tolist(), 
                col_label,
                backgroundColor="'rgba({},0.8)'".format(", ".join([str(x) for x in hex2rgb(COLOR_CYCLE[i])])),
                yAxisID= "'y-axis-0'")
        mychart.set_params(JSinline = 0, ylabel = 'Fraction of households', xlabel=self.municipality_col,
            scaleBeginAtZero=1, x_autoskip=True)

        mychart.jekyll_write(outpath)
    
    def make_chart_ej_cso_comparison(self, data_egs_merge: pd.DataFrame, data_ins_g_ws_j: pd.DataFrame, 
        df_ej_variables: pd.DataFrame, level_name: str='watershed', lookup_col: str='Watershed'):
        """Comparison of EJ and CSO characteristics by a geographic unit named `level_name` with discharge volumes reported in 
        `data_ins_g_ws_j`, with EJ characteristics tabulated in `df_ej_variables`, corresponding to the column `lookup_col` 
        in `data_egs_merge`.
        """
        print('Making comparison plot of EJ and CSO data')
        for i, col, col_label in (
            (0, 'MINORPCT', 'Fraction of population identifying as non-white'),
            (1, 'LOWINCPCT', 'Fraction of population with income less than twice the Federal poverty limit'),
            (2, 'LINGISOPCT', 'Fraction of population in households whose adults speak English less than "very well"'),
            ):
            ## Lookup base values - Census group block level
            l = data_egs_merge[lookup_col].unique()
            l = l[pd.isnull(l) == 0]
            pop = data_egs_merge.groupby(lookup_col)['ACSTOTPOP'].sum().reindex(l).values
            x = df_ej_variables[col].reindex(l).values
            y = data_ins_g_ws_j[self.discharge_vol_col].reindex(l).values

            ## Calculate binned values
            x_bins = np.unique(np.nanpercentile(x, list(np.linspace(0,100,5))))
            x_bin_cent = [np.mean([x_bins[i], x_bins[i+1]]) for i in range(len(x_bins) - 1)]
            x_bin_id = pd.cut(x, x_bins, labels=False)
            y_bin = np.array([
                weight_mean(y[x_bin_id == i], pop[x_bin_id == i])
                for i in range(len(x_bins) - 1)]).T

            ## Establish chart
            mychart = chartjs.chart(f"CSO discharge volume vs EJ characteristics by {level_name}: "+col, "Scatter", 640, 480)

            ## Add individual-level dataset
            mychart.add_dataset(
                np.array([x, y]).T, 
                dataset_label=f"Individual {level_name}s",
                backgroundColor="'rgba(50,50,50,0.125)'",
                showLine = "false",
                yAxisID= "'y-axis-0'",
                fill="false",
                hidden="'true'"
                )
            ## Add binned dataset
            mychart.add_dataset(
                np.array([x_bin_cent, y_bin[0]]).T, 
                dataset_label="Average (population weighted & binned)",
                backgroundColor="'rgba(50,50,200,1)'",
                showLine = "true",
                borderColor="'rgba(50,50,200,1)'",
                borderWidth=3,
                yAxisID= "'y-axis-0'",
                fill="false",
                pointRadius=6,
                )
            ## Add uncertainty contour
            mychart.add_dataset(np.array([x_bin_cent, y_bin[0] - 1.65 * y_bin[1]]).T, 
                "Average lower bound (5% limit)",
                backgroundColor="'rgba(50,50,200,0.3)'", showLine = "true", yAxisID= "'y-axis-0'", borderWidth = 1, 
                fill = 'false', pointBackgroundColor="'rgba(50,50,200,0.3)'", pointBorderColor="'rgba(50,50,200,0.3)'")
            mychart.add_dataset(np.array([x_bin_cent, y_bin[0] + 1.65 * y_bin[1]]).T, 
                "Average upper bound (95% limit)",
                backgroundColor="'rgba(50,50,200,0.3)'", showLine = "true", yAxisID= "'y-axis-0'", borderWidth = 1, fill = "'-1'", pointBackgroundColor="'rgba(50,50,200,0.3)'", pointBorderColor="'rgba(50,50,200,0.3)'")

            ## Set overall chart parameters
            mychart.set_params(
                JSinline = 0, 
                ylabel = f'Total volume of discharge ({self.cso_data_year}; Millions of gallons)', 
                xlabel=col_label,
                yaxis_type='linear',    
                y2nd = 0,
                scaleBeginAtZero=1,
                custom_tooltips = """
                            mode: 'single',
                            callbacks: {
                                label: function(tooltipItems, data) { 
                                    var title = '';
                                    
                                    if (tooltipItems.datasetIndex == 0) {
                                        title = ma_towns[tooltipItems.index];
                                    } else {
                                        title = data.datasets[tooltipItems.datasetIndex].label;
                                    }
                                    return [title, 'Total volume of discharge: ' + tooltipItems.yLabel, 'Linguistic isoluation: ' + tooltipItems.xLabel];
                                }
                            }
            """
                ) 
            ## Update logarithm tick format as in https://github.com/chartjs/Chart.js/issues/3121
            mychart.add_extra_code(
            """
            Chart.scaleService.updateScaleDefaults('linear', {
            ticks: {
                autoSkip: true,
                autoSkipPadding: 100,
                callback: function(tick, index, ticks) {
                return tick.toLocaleString()
                }
            }
            });
            """)
            ## Add watershed dataset
            mychart.add_extra_code(
                'var ma_towns = ["' + '","'.join(l) + '"];')

            mychart.jekyll_write(f'../docs/_includes/charts/{self.output_slug_dataset}_EJSCREEN_correlation_by{level_name}_{col}.html')


    # -------------------------
    # Regression modeling methods
    # -------------------------
    
    def fit_stan_model(self, col: str, data_egs_merge: pd.DataFrame, df_watershed_level: pd.DataFrame, 
        data_ins_g_ws_j: pd.DataFrame) -> Tuple[stan.fit.Fit, pd.DataFrame, dict, np.ndarray]:
        """Fit Stan model for a particular EJ characteristic (`col`)
        """
        print(f'Building stan model for {col}')
        ## Lookup base values - Census group block level
        l = data_egs_merge.Watershed.unique()
        l = l[pd.isnull(l) == 0]
        pop = data_egs_merge.groupby('Watershed')['ACSTOTPOP'].sum().loc[l].values
        x = df_watershed_level[col].loc[l].values
        y = data_ins_g_ws_j[self.discharge_vol_col].loc[l].values
        
        ## Fit Stan model
        stan_dat = {
            'J': len(x),
            'x': list(x),
            'y': list(y),
            'p': list(pop / np.mean(pop))
            }
        
        sm = stan.build(open(self.stan_model_code).read(), data=stan_dat)
        fit = sm.sample(num_samples=10000, num_chains=10)
        fit_par = fit.to_frame()
        
        return fit, fit_par, stan_dat, pop
        
    ## Stan fit diagnostic output
    #s = fit.summary()
    #summary = pd.DataFrame(s['summary'], columns=s['summary_colnames'], index=s['summary_rownames'])
    #print(col)
    #print(summary)
    
    def regression_plot_beta_posterior(self, fit_par: pd.DataFrame, col: str, plot_path: str):
        """Plot a beta posterior histogram for the regression model. Also output some summary statistics
        to the `fact_file`.
        """
        print('Plotting regression beta posterior')
        plt.figure()
        ph = 2**fit_par['beta']
        plt.hist(ph, bins=100, range=[0,6])
        plt.xlabel("2x growth ratio -- " + col)
        plt.ylabel('Posterior samples')
        plt.savefig(plot_path, dpi=200)
        
        ## Output summary dependence statistics
        with open(self.fact_file, 'a') as f:
            f.write(f'depend_cso_{col}: {np.median(ph):0.1f} times (90% confidence interval '
                    f'{np.percentile(ph, 5):0.1f} to {np.percentile(ph, 95):0.1f} times)\n')
    
    def regression_plot_model_draws(self, fit_par: pd.DataFrame, col_label: str, plot_path: str, stan_dat: dict, 
        pop_data: np.ndarray):
        """Plot fitted exponential model draws from the regression model posterior.
        """
        print('Plotting sample regression model draws')
        
        x = stan_dat['x']
        y = stan_dat['y']
        
        plt.figure()
        N = len(fit_par['beta'])
        for i, n in enumerate(np.random.randint(0, N, 20)):
            px = np.linspace(min(x), max(x), 1000)
            plt.plot(px, fit_par.loc[n, 'alpha'] * px**fit_par.loc[n, 'beta'], color='r', alpha=0.3, 
                    label = 'Posterior draw' if i==0 else None, zorder=1)
        
        plt.xlabel(col_label, wrap=True)
        plt.ylabel(f'CSO discharge ({self.cso_data_year}; Mgal)')
        
        plt.scatter(x, y, marker='o', c=pop_data / 1e3, cmap=cm.Blues, label='Watersheds', zorder=2)
        plt.colorbar(label='Population (1000s)')
        plt.legend(loc=2)
        plt.savefig(plot_path, dpi=200, bbox_inches='tight')

    # -------------------------
    # Main logic
    # -------------------------
    
    def run_analysis(self):
        """Load all data and generate all plots and analysis.
        """
        # Clear out the fact file
        open(self.fact_file, 'w').close()
        
        # Data ETL
        self.geo_towns_list, self.geo_watersheds_list, self.geo_blockgroups_list = self.get_geo_files()
        self.data_cso, self.data_ejs = self.load_data()
        # TODO should add these results to the database
        self.data_cso = self.assign_cso_data_to_census_blocks(self.data_cso, self.geo_blockgroups_list)
        self.data_ejs = assign_ej_data_to_geo_bins_with_strtree(self.data_ejs, self.geo_towns_list, self.geo_watersheds_list, self.geo_blockgroups_list)
        self.data_ins_g_bg, self.data_ins_g_muni_j, self.data_ins_g_ws_j, self.data_egs_merge, self.df_watershed_level, self.df_town_level = \
            self.apply_pop_weighted_avg(self.data_cso, self.data_ejs)
        
        # Make maps
        if self.make_maps:
            self.make_map_discharge_volumes(
                self.data_cso, self.geo_watersheds_list, self.data_ins_g_bg, self.data_ins_g_muni_j, self.data_ins_g_ws_j)
            self.make_map_ej_characteristics(
                self.data_egs_merge, self.data_cso, self.df_town_level, self.df_watershed_level, self.geo_watersheds_list)
        
        # Make charts
        if self.make_charts:
            self.make_chart_summary_ej_characteristics_watershed(self.df_watershed_level)
            self.make_chart_summary_ej_characteristics_town(self.df_town_level)
            self.make_chart_ej_cso_comparison(self.data_egs_merge, self.data_ins_g_ws_j, self.df_watershed_level)
            # Make town-level comparison XXXX
            self.make_chart_ej_cso_comparison(self.data_egs_merge, self.data_ins_g_muni_j, self.df_town_level, 
                                              level_name='municipality', lookup_col='Town')
            # Make census block-level comparison
            self.make_chart_ej_cso_comparison(self.data_egs_merge, self.data_ins_g_bg, self.data_egs_merge.set_index('ID'), 
                                              level_name='Census block', lookup_col='ID')
        
        # Regression modeling
        if self.make_regression:
            self.fits = {}
            for col, col_label in (
                ('MINORPCT', 'Fraction of population identifying as non-white'),
                ('LOWINCPCT', 'Fraction of population with income less than twice the Federal poverty limit'),
                ('LINGISOPCT', 'Fraction of population in households whose adults speak English less than "very well"'),
                ):
                fit, fit_par, stan_dat, pop_data = self.fit_stan_model(col, self.data_egs_merge, self.df_watershed_level, self.data_ins_g_ws_j)
                self.regression_plot_beta_posterior(fit_par, col, plot_path=self.fig_path + f'{self.output_slug}_stanfit_beta_'+col+'.png')
                self.regression_plot_model_draws(fit_par, col_label, self.fig_path + f'{self.output_slug}_stanfit_'+col+'.png', stan_dat, pop_data)
                self.fits[col] = {'fit_par': fit_par, 'stan_dat': stan_dat, 'pop_data': pop_data}
    
if __name__ == '__main__':
    csoa = CSOAnalysis()
    csoa.run_analysis()
