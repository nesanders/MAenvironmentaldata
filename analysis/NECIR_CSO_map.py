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
import logging
from typing import Any, Dict, List, Optional, Tuple

import chartjs
import geopandas as gpd
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
    logging.info('Opening SQL engine')
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
        return town_feature['TOWN'] 
    else:
        return None

def lookup_watershed_for_feature(watershed_feature, point) -> Optional[str]:
    """Try to assign an input feature to a watershed
    """
    town_polygon = shape(watershed_feature['geometry'])
    if town_polygon.contains(point):
        return watershed_feature['NAME']
    else:
        return None

def pop_weighted_average(x, cols):
    w = x['ACSTOTPOP']
    out = []
    for col in cols:
        out += [np.sum(w * x[col].values) / np.sum(w)]
    return pd.Series(data = out, index=cols)

# This CRS as defined in the .prj file obtained from 
# https://www.census.gov/geographies/mapping-files/time-series/geo/carto-boundary-file.html
# It is provided as ('GEOGCS["GCS_North_American_1983",DATUM["D_North_American_1983",'
    # 'SPHEROID["GRS_1980",6378137,298.257222101]],PRIMEM["Greenwich",0],UNIT["Degree",'
    # '0.017453292519943295]]')
# Per the following resource, this corresponds to "EPSG:4326": https://gis.stackexchange.com/a/248081
DEFAULT_BLOCKGROUP_CRS = "EPSG:4326"

def smooth_discharge(x: pd.DataFrame, avg_cols: list[str]):
    """Calculate a smoothed discharge value by taking a weighted average of rows in a `df` for 
    each col in `avg_cols`, weighting by the number of times a CSO appears across BlockGroups 
    (to avoid double counting).
    
    The input df `x` should be a set of CSO rows falling within a given Census BG.
    """
    output = {}
    for col in avg_cols:
        output[col] = np.average(x[col], weights=x['cso_duplication'])
    output['num_buffered_csos'] = len(x)
    return pd.Series(output)

def cast_df_to_epsg_3310(gdf: gpd.GeoDataFrame, latitude: str='Latitude', longitude: str='Longitude', crs: str='EPSG:4326'
) -> gpd.GeoDataFrame:
    """Cast a `pd.DataFrame` to a `gpd.GeoDataFrame` with the EPSG:3310 metric CRS (coordinate system).
    
    The default `crs` EPSG:4326 is the default CRS used by e.g. Google Maps, https://gis.stackexchange.com/a/327036
    """
    return gpd.GeoDataFrame(gdf, geometry=gpd.points_from_xy(gdf[longitude], gdf[latitude]), crs=crs).to_crs(epsg=3310)

METERS_PER_MILE = 1609.34
def _assign_cso_data_to_census_blocks_with_geopandas(data_cso: pd.DataFrame, data_ejs: pd.DataFrame, geo_blockgroups_df: gpd.GeoDataFrame, 
    latitude: str='Latitude', longitude: str='Longitude', use_radius: Optional[float]=None,
    discharge_cols: tuple[str, str]=('2011_Discharges_MGal', '2011_Discharge_N')) -> pd.DataFrame:
    """Add a new 'BlockGroup' column to `data_cso` assigning CSOs to Census block groups using geopandas
    operations.
    
    When using `use_radius` (not `None`), the output will instead be `geo_blockgroups_df` with columns added for the smoothed
    sum of CSO discharges from CSOs within the specified radius for each blockgroup, via `smooth_discharge`.
    """
    logging.info(f'Assigning CSO data to Census Blocks with {use_radius=}')
    data_cso = data_cso.copy()
    # Convert both to metric projects
    utm_cso_df = cast_df_to_epsg_3310(data_cso, latitude, longitude)
    utm_bg_df = geo_blockgroups_df.to_crs(epsg=3310)
    # Limit assignment to BGs with EJ data
    utm_bg_df = utm_bg_df[utm_bg_df['GEOID'].isin(data_ejs['ID'])]
    
    if use_radius is not None:
        # We create a use_radius-sized buffer around the CSO, then match on the overlap with the BGs
        # Some statistics - 
        # when using a 0.5 mile radius, CSOs overlap on average with 9.4 BGs, with a min of 3 and max of 18
        # when using a 2 mile radius, CSOs overlap on average with 27 BGs, with a min of 10 and max of 71
        utm_cso_buf_geom = utm_cso_df.buffer(use_radius * METERS_PER_MILE)
        utm_cso_buf_df = utm_cso_df.set_geometry(utm_cso_buf_geom)
        utm_merge_df = utm_bg_df.sjoin(utm_cso_buf_df, how='left', predicate='intersects')
        
        logging.info(f'Total number of CSOs: N={len(data_cso)}')
        logging.info(f'Total number of CSOs-BlockGroup pairs within {use_radius=}: N={len(utm_merge_df)}')
        
        cso_duplication = utm_merge_df.groupby('cso_id')['GEOID'].count()
        utm_merge_df['cso_duplication'] = cso_duplication.reindex(utm_merge_df['cso_id']).values
        # NOTE - need to make these averaging columns user editable
        smoothed_discharge_df = utm_merge_df.groupby('GEOID').apply(smooth_discharge, discharge_cols)
        
        for col in discharge_cols:
            utm_bg_df[col] = smoothed_discharge_df[col].reindex(utm_bg_df['GEOID']).values
        
        # Preserve lat / long
        utm_merge_df[[latitude, longitude]] = utm_merge_df.centroid.to_crs('WGS 84').get_coordinates()[['y', 'x']].values
        
        return utm_merge_df
    
    else:
        # We do a nearest join to allow or the small number of cases where there is not a direct intersection in the geometries,
        # i.e. as in MWR205 outfall at the dam.
        utm_merge_df = utm_cso_df.sjoin_nearest(utm_bg_df, how='left')
        data_cso['GEOID'] = utm_merge_df['GEOID'].values
        return data_cso

@memory.cache
def assign_ej_data_to_geo_bins_with_geopandas(data_ejs: pd.DataFrame, geo_towns_df: gpd.GeoDataFrame, 
    geo_watersheds_df: gpd.GeoDataFrame, geo_blockgroups_df: gpd.GeoDataFrame, latitude: str='Latitude', 
    longitude: str='Longitude') -> pd.DataFrame:
    """Return a version of `data_ejs` with added 'Town', 'Watershed', and 'Census Block' columns.
    
    The EJ dataframe is indexed on census blockgroups, so we first merge in the block group geometry and
    then lookup the town and watershed info.
    """    
    logging.info('Adding Town and Watershed labels to EJ data')
    # Convert both to metric projections
    utm_towns_df = geo_towns_df.to_crs(epsg=3310)
    utm_watersheds_df = geo_watersheds_df.to_crs(epsg=3310)
    utm_blockgroups_df = geo_blockgroups_df.to_crs(epsg=3310)
    
    # Only assign to Census BGs with EJ data (right join). This retains 85% of BGs. 
    data_ejs_cbg_merge = utm_blockgroups_df.merge(data_ejs, left_on='GEOID', right_on='ID', how='right')
    data_ejs_centroids = gpd.GeoDataFrame(geometry=data_ejs_cbg_merge.centroid.values, index=data_ejs_cbg_merge['GEOID'])

    data_ejs_out = data_ejs.copy().set_index('ID')
    for geo_type, geo_df, geo_key in [
            ('Town', utm_towns_df, 'TOWN'), 
            ('Watershed', utm_watersheds_df, 'NAME')
        ]:
        data_ejs_out[geo_type] = '[UNKNOWN]'
        result_df = geo_df.sjoin(data_ejs_centroids, predicate='contains')
        # Parse the results
        for cbg_id in data_ejs_cbg_merge['GEOID']:
            result_set = result_df.loc[result_df['index_right'] == cbg_id]
            if len(result_set) == 0:
                logging.info(f'No {geo_type} found for Census Block Group #{cbg_id}')
                continue
            ## Warn if multiple towns were found
            elif len(result_set) > 1:
                logging.info(f'N={len(result_set)} {geo_type}s were found for Census Block Group #{cbg_id}; will pick the first')
            
            data_ejs_out.loc[(cbg_id,), geo_type] = result_set.iloc[0][geo_key]

    return data_ejs_out.reset_index()

@memory.cache
def _apply_pop_weighted_avg(data_cso: pd.DataFrame, data_ejs: pd.DataFrame, discharge_vol_col: str, discharge_count_col: str,
    output_prefix: Optional[str]=None
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Calculate population weighted averages for EJ characteristics, averaging over block group, watershed, and town.
    
    Returns
    -------
    pd.DataFrame
        Table of discharge volumes and counts per outfall.
    pd.DataFrame
        Table of discharge volumes and counts per Town.
    pd.DataFrame
        Table of discharge volumes and counts per Watershed.
    pd.DataFrame
        Table of discharge volumes and counts per outfall with EJ statistics.
    pd.DataFrame
        Table of discharge volumes and counts per Town with population weighted average.
    pd.DataFrame
        Table of discharge volumes and counts per Watershed with population weighted average.
    """
    logging.info('Calculating population weighted averages')
    
    id_col = 'GEOID'
    
    ## Get counts by block group
    data_ins_g_bg = data_cso.groupby(id_col)[[discharge_vol_col, discharge_count_col]].sum()
    data_ins_g_bg_j = pd.merge(data_ins_g_bg, data_ejs, left_index=True, right_on ='ID', how='left')
    data_egs_merge = pd.merge(
        data_ins_g_bg_j.groupby('ID')[[discharge_count_col, discharge_vol_col]].sum(),
        data_ejs, left_index = True, right_on='ID', how='outer')

    ## Get counts by municipality
    data_ins_g_muni_j = pd.merge(data_cso, data_ejs, left_on=id_col, right_on='ID', how='outer')\
                        .groupby('Town')[[discharge_vol_col, discharge_count_col]].sum().fillna(0)

    ## Get counts by watershed
    data_ins_g_ws_j = pd.merge(data_cso, data_ejs, left_on=id_col, right_on='ID', how='outer')\
                        .groupby('Watershed')[[discharge_vol_col, discharge_count_col]].sum().fillna(0)
    # If requested, save out a file
    if output_prefix is not None and 'waterBody' in data_ejs:
        pd.merge(data_cso, data_ejs, left_on=id_col, right_on='ID', how='outer').groupby(['Watershed', 'waterBody', 'cso_id'])['DischargeVolume'].sum()\
            .to_csv(output_prefix+'_discharge_per_waterbody.csv')
    # NOTE you can check that MWR205 exists with code like
    # pd.merge(data_cso, data_ejs, left_on=id_col, right_on='ID', how='outer').set_index('cso_id').loc['MWR205']
    # 250173501031 is the preferred census block, but does not exist in the EJ data file, so we end up with the nearby 250250406001 instead
    # pd.merge(data_cso, data_ejs, left_on=id_col, right_on='ID', how='outer').set_index('GEOID').loc['250173501031']

    df_watershed_level = data_egs_merge.groupby('Watershed').apply(
        lambda x: pop_weighted_average(x, ['MINORPCT', 'LOWINCPCT', 'LINGISOPCT']))

    df_town_level = data_egs_merge.groupby('Town').apply(
        lambda x: pop_weighted_average(x, ['MINORPCT', 'LOWINCPCT', 'LINGISOPCT']))
    
    return data_ins_g_bg, data_ins_g_muni_j, data_ins_g_ws_j, data_egs_merge, df_watershed_level, df_town_level

# -------------------------
# Analysis class
# -------------------------

class CSOAnalysis():
    """Class containing methods and attributes related to CSO EJ analysis.
    """
    
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
        fact_file: Optional[str]=None,
        data_path: str='../docs/data/',
        out_path: str='../docs/assets/maps/',
        fig_path: str='../docs/assets/figures/',
        stan_model_code: str='discharge_regression_model.stan',
        geo_towns_path: str='../docs/assets/geo_json/TOWNSSURVEY_POLYM_geojson_simple.json',
        geo_watershed_path: str='../docs/assets/geo_json/watshdp1_geojson_simple.json',
        geo_blockgroups_path: str='../docs/assets/geo_json/cb_2017_25_bg_500k.json',
        make_maps: bool=True,
        make_charts: bool=True,
        make_regression: bool=True,
        cbg_smooth_radius: Optional[float]=None
    ):
        """Initialize parameters
        
        Parameters
        ----------
        fact_file: Optional[str]
            Path of yml file to write calculated results to, by default '../docs/data/facts_{output_slug}.yml',
        data_path: str,
            Path of dirctory to write data outputs to, by default 'fact_file: str='../docs/data/'
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
            NOTE: These can be downloaded from e.g. https://www.census.gov/geographies/mapping-files/time-series/geo/carto-boundary-file.html
        make_maps: bool
            Whether or not to execute the functions to generate maps, by default True,
        make_charts: bool
            Whether or not to execute the functions to generate charts, by default True,
        make_regression: bool
            Whether or not to execute the functions to generate regression models, by default True
        cbg_smooth_radius: Optional[float]
            If not None, then the CSO discharge data for each census block group will be smoothed over this radius in miles, by default=None
        """
        # Establish file to export facts
        if fact_file is None:
            self.fact_file = f'../docs/data/facts_{self.output_slug}.yml'
        else:
            self.fact_file = fact_file
        # Location to write out map and figure assets
        self.data_path = data_path
        self.out_path = out_path
        self.fig_path = fig_path
        # Location of Stan regression model code
        self.stan_model_code = stan_model_code
        # Location of input geo json data
        self.geo_towns_path = geo_towns_path
        self.geo_watershed_path = geo_watershed_path
        self.geo_blockgroups_path = geo_blockgroups_path
        self.make_maps = make_maps
        self.make_charts = make_charts
        self.make_regression = make_regression
        self.cbg_smooth_radius = cbg_smooth_radius
 
    
    # -------------------------
    # Data loading methods
    # -------------------------
    
    def get_geo_files(self) -> Tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame]:
        """Load and return geo json files.
        """
        geo_towns_df = gpd.GeoDataFrame.from_file(self.geo_towns_path)
        geo_watersheds_df = gpd.GeoDataFrame.from_file(self.geo_watershed_path)
        geo_blockgroups_df = gpd.GeoDataFrame.from_file(self.geo_blockgroups_path)
        geo_dfs = (geo_towns_df, geo_watersheds_df, geo_blockgroups_df)
        for gdf in geo_dfs:
            gdf.set_crs(DEFAULT_BLOCKGROUP_CRS)
        return geo_dfs

    
    def load_data_cso(self) -> pd.DataFrame:
        """Load NECIR 2011 CSO data
        """
        logging.info('Loading NECIR 2011 CSO data')
        disk_engine = get_engine()
        data_cso = pd.read_sql_query('SELECT * FROM NECIR_CSO_2011', disk_engine)
        data_cso[self.discharge_vol_col] = data_cso[self.discharge_vol_col].apply(safe_float)
        data_cso[self.discharge_count_col] = data_cso[self.discharge_count_col].apply(safe_float)
        data_cso.rename(columns={'index': 'cso_id'}, inplace=True)
        return data_cso
    
    @staticmethod
    def load_data_ej(ejscreen_year: int=2017) -> pd.DataFrame:
        """Load EJSCREEN data for a specified year.
        """
        logging.info('Loading EJSCREEN data')
        disk_engine = get_engine()
        data_ejs = pd.read_sql_query(f'SELECT * FROM EPA_EJSCREEN_{ejscreen_year}', disk_engine)
        data_ejs['ID'] = data_ejs['ID'].astype(str)
        return data_ejs

    def load_data(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Load all data, CSO and EJ.
        """
        logging.info('Loading all data')
        data_cso = self.load_data_cso()
        data_ejs = self.load_data_ej()
        return data_cso, data_ejs

    # -------------------------
    # Data transforming methods
    # -------------------------

    def assign_cso_data_to_census_blocks(self, 
        data_cso: pd.DataFrame, data_ejs: pd.DataFrame, geo_blockgroups_df: gpd.GeoDataFrame, use_radius: Optional[float]=None
    ) -> pd.DataFrame:
        """Add a new 'BlockGroup' column to `data_cso` assigning CSOs to Census block groups.
        """
        return _assign_cso_data_to_census_blocks_with_geopandas(data_cso, data_ejs, geo_blockgroups_df, self.latitude_col, self.longitude_col, use_radius,
            discharge_cols=(self.discharge_vol_col, self.discharge_count_col))
    
    def apply_pop_weighted_avg(self, data_cso: pd.DataFrame, data_ejs: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Calculate population weighted averages for EJ characteristics, averaging over block group, watershed, and town.
        """
        return _apply_pop_weighted_avg(data_cso, data_ejs, self.discharge_vol_col, self.discharge_count_col, output_prefix=self.data_path + f'{self.output_slug}')

    # -------------------------
    # Mapping functions
    # -------------------------
    
    def make_map_discharge_volumes(self, data_cso: pd.DataFrame, geo_watersheds_df: gpd.GeoDataFrame, data_ins_g_bg: pd.DataFrame, 
        data_ins_g_muni_j: pd.DataFrame, data_ins_g_ws_j: pd.DataFrame):
        """
        Map of discharge volumes with layers for watershed, town, and census block group with CSO points
        """
        logging.info('Making map of discharge volumes')
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
        for fid, feature in geo_watersheds_df.iterrows():
            pos = feature['geometry'].centroid.coords.xy
            pos = (pos[1][0], pos[0][0])
            folium.Marker(pos, icon=folium.features.DivIcon(
                icon_size=(150,36),
                icon_anchor=(7,20),
                html='<div style="font-size: 12pt; color: blue; opacity: 0.3">{}</div>'.format(feature['NAME']),
                )).add_to(map_1)

        ## Add a layer control
        folium.LayerControl(collapsed=False).add_to(map_1)

        ## Save to html
        map_1.save(self.out_path + f'{self.output_slug}_map_total.html')

    def make_map_ej_characteristics(self, data_egs_merge: pd.DataFrame, data_cso: pd.DataFrame, 
        df_town_level: pd.DataFrame, df_watershed_level: pd.DataFrame, geo_watersheds_df: gpd.GeoDataFrame):
        """Map of EJ characteristics with layers for watershed, town, and census block group with CSO points
        """
        logging.info('Making map of EJ characteristics')
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
            for fid, feature in geo_watersheds_df.iterrows():
                pos = shape(feature['geometry']).centroid.coords.xy
                pos = (pos[1][0], pos[0][0])
                folium.Marker(pos, icon=folium.features.DivIcon(
                    icon_size=(150,36),
                    icon_anchor=(7,20),
                    html='<div style="font-size: 12pt; color: blue; opacity: 0.3">{}</div>'.format(feature['NAME']),
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
        logging.info('Making map of EJ characteristics per watershed')
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
        logging.info('Making summary chart of EJ data by town')
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
        logging.info('Making comparison plot of EJ and CSO data')
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
                custom_tooltips = f"""
                            mode: 'single',
                            callbacks: {{
                                label: function(tooltipItems, data) {{ 
                                    var title = '';
                                    
                                    if (tooltipItems.datasetIndex == 0) {{
                                        title = point_label[tooltipItems.index];
                                    }} else {{
                                        title = data.datasets[tooltipItems.datasetIndex].label;
                                    }}
                                    return [title, 
                                            'Total volume of discharge: ' + Number(tooltipItems.yLabel).toFixed(2) + ' Millions of gallons', 
                                            '{col_label}: ' + Number(tooltipItems.xLabel).toFixed(2), 
                                            'Population: ' + pop_data[tooltipItems.index]
                                           ];
                                }}
                            }}
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
                'var point_label = ["' + '","'.join(l) + '"];')
            mychart.add_extra_code(
                'var pop_data = [' + ', '.join('"{:,}"'.format(x) for x in pop) + '];')

            mychart.jekyll_write(f'../docs/_includes/charts/{self.output_slug}_EJSCREEN_correlation_by{level_name}_{col}.html')


    # -------------------------
    # Regression modeling methods
    # -------------------------
    
    def fit_stan_model(self, col: str, data_egs_merge: pd.DataFrame, level_df: pd.DataFrame, 
        df_cso_level: pd.DataFrame, level_col: str='Watershed') -> Tuple[stan.fit.Fit, pd.DataFrame, dict, np.ndarray]:
        """Fit Stan model for a particular EJ characteristic (`col`)
        """
        logging.info(f'Building stan model for {col}')
        ## Lookup base values - Census group block level
        l = data_egs_merge[level_col].unique()
        l = l[pd.isnull(l) == 0]
        pop = data_egs_merge.groupby(level_col)['ACSTOTPOP'].sum().loc[l].values
        x = level_df[col].loc[l].values
        y = df_cso_level[self.discharge_vol_col].reindex(l).fillna(0).values
        # Filter out unpopulated blocks
        sel_unpop = pop < 50
        if sum(y[sel_unpop]) > 0:
            logging.warning(f"Unpopulated geographic levels have nonzero: discharge\n"
                            f"N={len(y[sel_unpop][y[sel_unpop] > 0])} have "
                            f"total discharge volume {sum(y[sel_unpop])}")
        
        ## Fit Stan model
        stan_dat = {
            'J': len(x[~sel_unpop]),
            'x': list(x[~sel_unpop]),
            'y': list(y[~sel_unpop]),
            'p': list(pop[~sel_unpop] / np.mean(pop[~sel_unpop]))
            }
        assert np.isnan(stan_dat['x']).sum() + np.isnan(stan_dat['y']).sum() == 0,\
            "NaN values appeared in input x or y"
        
        sm = stan.build(open(self.stan_model_code).read(), data=stan_dat)
        if stan_dat['J'] > 100:
            num_samples = 1000 # WARNING set to 5000 for full run
            logging.info(f"Large dataset N={stan_dat['J']}; running smaller sample size")
        else:
            num_samples = 1000 # WARNING set to 5000 for full run
        fit = sm.sample(num_samples=num_samples, num_chains=10)
        fit_par = fit.to_frame()
        
        return fit, fit_par, stan_dat, pop[~sel_unpop]
        
    ## Stan fit diagnostic output
    #s = fit.summary()
    #summary = pd.DataFrame(s['summary'], columns=s['summary_colnames'], index=s['summary_rownames'])
    #logging.info(col)
    #logging.info(summary)
    
    def regression_plot_beta_posterior(self, fit_par: pd.DataFrame, col: str, plot_path: str):
        """Plot a beta posterior histogram for the regression model. Also output some summary statistics
        to the `fact_file`.
        """
        logging.info('Plotting regression beta posterior')
        plt.figure()
        ph = 2**fit_par['beta']
        plt.hist(ph, bins=100, range=[0,6])
        plt.xlabel("2x growth ratio -- " + col)
        plt.ylabel('Posterior samples')
        plt.savefig(plot_path, dpi=200)
    
    def summary_statistics(self, fit_par: pd.DataFrame, col: str, level: str):
        """Output summary dependence statistics."""
        ph = 2**fit_par['beta']
        with open(self.fact_file, 'a') as f:
            f.write(f'depend_cso_{col}_{level}: {np.median(ph):0.1f} times (90% probability interval '
                    f'{np.percentile(ph, 5):0.1f} to {np.percentile(ph, 95):0.1f} times)\n')
    
    def regression_plot_model_draws(self, fit_par: pd.DataFrame, col_label: str, plot_path: str, stan_dat: dict, 
        pop_data: np.ndarray, level_col: str='Watershed'):
        """Plot fitted exponential model draws from the regression model posterior.
        """
        logging.info('Plotting sample regression model draws')
        
        x = stan_dat['x']
        y = stan_dat['y']
        
        plt.figure()
        N = len(fit_par['beta'])
        for i, n in enumerate(np.random.randint(0, N, 20)):
            px = np.linspace(min(x), max(x), 1000)
            plt.plot(px, fit_par.loc[n, 'alpha'] * px**fit_par.loc[n, 'beta'], color='r', alpha=0.3, 
                    label = 'Posterior draw' if i==0 else None, zorder=2)
        
        plt.xlabel(col_label, wrap=True)
        plt.ylabel(f'CSO discharge ({self.cso_data_year}; Mgal)')
        
        plt.scatter(x, y, marker='o', c=pop_data / 1e3, cmap=cm.Blues, label=level_col, zorder=1)
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
        self.geo_towns_df, self.geo_watersheds_df, self.geo_blockgroups_df = self.get_geo_files()
        self.data_cso, self.data_ejs = self.load_data()
        # TODO should add these results to the database
        self.data_cso = self.assign_cso_data_to_census_blocks(self.data_cso, self.data_ejs, self.geo_blockgroups_df, use_radius=self.cbg_smooth_radius)
        self.data_ejs = assign_ej_data_to_geo_bins_with_geopandas(self.data_ejs, self.geo_towns_df, self.geo_watersheds_df, self.geo_blockgroups_df)
        self.data_ins_g_bg, self.data_ins_g_muni_j, self.data_ins_g_ws_j, self.data_egs_merge, self.df_watershed_level, self.df_town_level = \
            self.apply_pop_weighted_avg(self.data_cso, self.data_ejs)
        
        self.data_cso.to_csv(self.data_path + f'{self.output_slug}_data_cso.csv')
        self.data_ins_g_bg.to_csv(self.data_path + f'{self.output_slug}_data_ins_g_bg.csv')
        self.data_ins_g_muni_j.to_csv(self.data_path + f'{self.output_slug}_data_ins_g_muni_j.csv')
        self.data_egs_merge.to_csv(self.data_path + f'{self.output_slug}_data_egs_merge.csv.gz')
        self.df_watershed_level.to_csv(self.data_path + f'{self.output_slug}_df_watershed_level.csv')
        self.df_town_level.to_csv(self.data_path + f'{self.output_slug}_df_town_level.csv')
        
        # Make maps
        if self.make_maps:
            self.make_map_discharge_volumes(
                self.data_cso, self.geo_watersheds_df, self.data_ins_g_bg, self.data_ins_g_muni_j, self.data_ins_g_ws_j)
            self.make_map_ej_characteristics(
                self.data_egs_merge, self.data_cso, self.df_town_level, self.df_watershed_level, self.geo_watersheds_df)
        
        # Make charts
        if self.make_charts:
            self.make_chart_summary_ej_characteristics_watershed(self.df_watershed_level)
            self.make_chart_summary_ej_characteristics_town(self.df_town_level)
            self.make_chart_ej_cso_comparison(self.data_egs_merge, self.data_ins_g_ws_j, self.df_watershed_level)
            # Make town-level comparison
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
                self.fits[col] = {}
                for level_col, level_demo_df, level_cso_df in [
                    ('Watershed', self.df_watershed_level, self.data_ins_g_ws_j), 
                    ('Town', self.df_town_level, self.data_ins_g_muni_j), 
                    ('ID', self.data_egs_merge.set_index('ID'), self.data_ins_g_bg)]:
                    fit, fit_par, stan_dat, pop_data = self.fit_stan_model(col, self.data_egs_merge, level_demo_df, 
                        level_cso_df, level_col=level_col)
                    self.regression_plot_beta_posterior(fit_par, col, plot_path=self.fig_path + f'{self.output_slug}_{level_col}_stanfit_beta_'+col+'.png')
                    self.summary_statistics(fit_par, col, level_col)
                    self.regression_plot_model_draws(fit_par, col_label, self.fig_path + f'{self.output_slug}_{level_col}_stanfit_'+col+'.png', stan_dat, 
                        pop_data, level_col=level_col)
                    self.fits[col][level_col] = {'fit_par': fit_par, 'stan_dat': stan_dat, 'pop_data': pop_data}

if __name__ == '__main__':
    csoa = CSOAnalysis()
    csoa.run_analysis()
