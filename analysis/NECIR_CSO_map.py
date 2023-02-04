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
"""

import json
from typing import Any, Optional, Tuple

import chartjs
import folium
from joblib import Parallel, delayed, Memory
import matplotlib as mpl
from matplotlib import pyplot as plt
from matplotlib import cm
import pandas as pd
import numpy as np
from shapely.geometry import shape, Point
import sqlalchemy
import stan

# Colors to use in plots
COLOR_CYCLE = [c['color'] for c in list(mpl.rcParams['axes.prop_cycle'])]

## Establish file to export facts
FACT_FILE = '../docs/data/facts_NECIR_CSO.yml'

# Location to write out map and figure assets
OUT_PATH = '../docs/assets/maps/'
FIG_PATH = '../docs/assets/figures/'

# Location of Stan regression model code
STAN_MODEL_CODE = open('discharge_regression_model.stan').read()

# Location of input geo json data
GEO_PATH = '../docs/assets/geo_json/'
GEO_TOWNS_PATH = GEO_PATH + 'TOWNSSURVEY_POLYM_geojson_simple.json'
GEO_WATERSHEDS_PATH = GEO_PATH + 'watshdp1_geojson_simple.json'
GEO_BLOCKGROUPS_PATH = GEO_PATH + 'cb_2017_25_bg_500k.json'

# Create a joblib cache
memory = Memory('necir_cso_data_cache', verbose=1)
    

# -------------------------
# Convenience functions
# -------------------------

def hex2rgb(hexcode: str) -> Tuple[int, int, int]:
    """Convert a hex color to RGB tuple)
    See http://www.psychocodes.in/rgb-to-hex-conversion-and-hex-to-rgb-conversion-in-python.html
    See https://stackoverflow.com/a/29643643
    """
    rgb = tuple(int(hexcode.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    return rgb

def get_geo_files() -> Tuple[dict, dict, dict, dict]:
    """Load and return geo json files.
    """
    geo_towns_dict = json.load(open(GEO_TOWNS_PATH))['features']
    geo_watersheds_dict = json.load(open(GEO_WATERSHEDS_PATH))['features']
    geo_blockgroups_dict = json.load(open(GEO_BLOCKGROUPS_PATH))['features']
    return geo_towns_dict, geo_watersheds_dict, geo_blockgroups_dict

def safe_float(x: Any) -> float:
    """Return a float if possible, or else a np.nan value.
    """
    try:
        return float(x)
    except:
        return np.nan

# -------------------------
# Data loading functions
# -------------------------

def get_engine() -> sqlalchemy.engine.Engine:
    """Establish a sqlite database connection
    """
    print('Opening SQL engine')
    return sqlalchemy.create_engine('sqlite:///../get_data/AMEND.db')

def load_data_cso() -> pd.DataFrame:
    """Load NECIR 2011 CSO data
    """
    print('Loading NECIR 2011 CSO data')
    disk_engine = get_engine()
    data_cso = pd.read_sql_query('SELECT * FROM NECIR_CSO_2011', disk_engine)
    data_cso['2011_Discharges_MGal'] = data_cso['2011_Discharges_MGal'].apply(safe_float)
    data_cso['2011_Discharge_N'] = data_cso['2011_Discharge_N'].apply(safe_float)
    return data_cso

def load_data_ej() -> pd.DataFrame:
    """Load EJSCREEN data
    """
    print('Loading EJSCREEN data')
    disk_engine = get_engine()
    data_ejs = pd.read_sql_query('SELECT * FROM EPA_EJSCREEN_2017', disk_engine)
    data_ejs['ID'] = data_ejs['ID'].astype(str)
    return data_ejs

def load_data() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load all data, CSO and EJ.
    """
    print('Loading all data')
    data_cso = load_data_cso()
    data_ejs = load_data_ej()
    return data_cso, data_ejs

# -------------------------
# Data transforming functions
# -------------------------

@memory.cache
def assign_cso_data_to_census_blocks(data_cso: pd.DataFrame, geo_blockgroups_dict: dict) -> pd.DataFrame:
    """Add a new 'BlockGroup' column to `data_cso` assigning CSOs to Census block groups.
    """
    print('Assigning CSO data to census blocks')
    data_out = data_cso.copy()
    ## Loop over Census block groups
    data_out['BlockGroup'] = np.nan
    ## Loop over CSO outfalls
    for cso_i in range(len(data_out)):
        point = Point(data_out.iloc[cso_i]['Longitude'], data_out.iloc[cso_i]['Latitude'])
        for feature in geo_blockgroups_dict:
            polygon = shape(feature['geometry'])
            if polygon.contains(point):
                data_out.loc[cso_i, 'BlockGroup'] = feature['properties']['GEOID'] 
        ## Warn if a blockgroup was not found
        if data_out.loc[cso_i, 'BlockGroup'] is np.nan:
            print(('No block group found for CSO #', str(cso_i)))
    return data_out

def pick_non_null(x: list) -> Optional[str]:
    """Return the first non-null value from a list, if any.
    """
    for val in x:
        if val is not None:
            return val
    return None

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

@memory.cache
def assign_ej_data_to_geo_bins(data_ejs: pd.DataFrame, geo_towns_dict: dict, geo_watersheds_dict: dict, 
    geo_blockgroups_dict: dict) -> pd.DataFrame:
    """Return a version of `data_ejs` with added 'Town' and 'Watershed' columns.
    
    NOTE: this runs in parallel with `joblib`
    TODO joblib doesn't actually seem to be achieving a lot of speedup; it would probably work better if done in batches
    """
    print('Adding Town and Watershed labels to EJ data')
    ## Loop over Census block groups
    bg_mapping = pd.DataFrame(
        index=[geo_blockgroups_dict[i]['properties']['GEOID'] for i in range(len(geo_blockgroups_dict))], 
        columns=['Town','Watershed'])
    ## Loop over block groups
    for feature in geo_blockgroups_dict:
        polygon = shape(feature['geometry'])
        point = polygon.centroid
        ## Loop over towns
        bg_mapping.loc[feature['properties']['GEOID'], 'Town'] = pick_non_null(
            Parallel(n_jobs=-1)(delayed(lookup_town_for_feature)(town_feature, point) for town_feature in geo_towns_dict))
        ## Warn if a town was not found
        if bg_mapping.loc[feature['properties']['GEOID'], 'Town'] is np.nan:
            print(f"No Town found for GEOID {feature['properties']['GEOID']}")
        ## Loop over watersheds
        bg_mapping.loc[feature['properties']['GEOID'], 'Watershed'] = pick_non_null(
            Parallel(n_jobs=-1)(delayed(lookup_watershed_for_feature)(watershed_feature, point) for watershed_feature in geo_watersheds_dict))
        ## Warn if a watershed was not found
        if bg_mapping.loc[feature['properties']['GEOID'], 'Watershed'] is np.nan:
            print(f"No Watershed found for GEOID {feature['properties']['GEOID']}")

    data_ejs = pd.merge(data_ejs, bg_mapping, left_on = 'ID', right_index=True, how='left')
    return data_ejs

def pop_weighted_average(x, cols):
    w = x['ACSTOTPOP']
    out = []
    for col in cols:
        out += [np.sum(w * x[col].values) / np.sum(w)]
    return pd.Series(data = out, index=cols)

@memory.cache
def apply_pop_weighted_avg(data_cso: pd.DataFrame, data_ejs: pd.DataFrame, 
    discharge_vol_col: str='2011_Discharges_MGal', discharge_count_col: str='2011_Discharge_N'
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

    df_watershed_level = data_egs_merge.groupby('Watershed').apply(lambda x: pop_weighted_average(x, ['MINORPCT', 'LOWINCPCT', 'LINGISOPCT', 'OVER64PCT', 'VULSVI6PCT']))

    df_town_level = data_egs_merge.groupby('Town').apply(lambda x: pop_weighted_average(x, ['MINORPCT', 'LOWINCPCT', 'LINGISOPCT', 'OVER64PCT', 'VULSVI6PCT']))
    
    return data_ins_g_bg, data_ins_g_muni_j, data_ins_g_ws_j, data_egs_merge, df_watershed_level, df_town_level

# -------------------------
# Mapping functions
# -------------------------

def make_map_discharge_volumes(data_cso: pd.DataFrame, geo_watersheds_dict: dict, data_ins_g_bg: pd.DataFrame, 
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

    ## Draw choropleth layer for census blocks
    map_1.choropleth(
        geo_data=GEO_BLOCKGROUPS_PATH, 
        name='Census Block Groups',
        data=data_ins_g_bg['2011_Discharges_MGal'],
        key_on='feature.properties.GEOID',
        legend_name='Block Group: Total volume of discharge (2011; Millions of gallons)',
        threshold_scale = list(np.nanpercentile(data_ins_g_bg['2011_Discharges_MGal'], [0,25,50,75,100])),  
        fill_color='BuGn', fill_opacity=0.7, line_opacity=0.3, highlight=True,
        )

    ## Draw Choropleth layer for towns
    map_1.choropleth(
        geo_data=GEO_TOWNS_PATH, 
        name='Municipalities',
        data=data_ins_g_muni_j['2011_Discharges_MGal'],
        key_on='feature.properties.TOWN',
        legend_name='Municipality: Total volume of discharge (2011; Millions of gallons)',
        threshold_scale = [0]+list(np.nanpercentile(data_ins_g_muni_j['2011_Discharges_MGal'][data_ins_g_muni_j['2011_Discharges_MGal'] > 0], [25,50,75,100])),  
        fill_color='PuRd', fill_opacity=0.7, line_opacity=0.3, highlight=True,
        )

    ## Draw Choropleth layer for watersheds
    map_1.choropleth(
        geo_data=GEO_WATERSHEDS_PATH, 
        name='Watersheds',
        data=data_ins_g_ws_j['2011_Discharges_MGal'],
        key_on='feature.properties.NAME',
        legend_name='Watershed: Total volume of discharge (2011; Millions of gallons)',
        threshold_scale = list(np.nanpercentile(data_ins_g_ws_j['2011_Discharges_MGal'], [0,25,50,75,100])),  
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
        Discharge volume (2011): {vol} (Millions of gallons)<br>
        Discharge frequency (2011): {N} discharges<br>
        </p>
        """.format(
                address = cso['Nearest_Pipe_Address'],
                body = cso['DischargesBody'],
                muni = cso['Municipality'],
                vol = cso['2011_Discharges_MGal'],
                N = cso['2011_Discharges_MGal'],
            )
        iframe = folium.IFrame(html=html, width=400, height=200)
        popup = folium.Popup(iframe, max_width=500)
        folium.RegularPolygonMarker(
                location=(cso['Latitude'], cso['Longitude']), 
                popup=popup, 
                number_of_sides=8, 
                radius=6, 
                color='green',
                fill_color='green',
            ).add_to(map_1)

    ## Add labels for watersheds
    for feature in geo_watersheds_dict:
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
    map_1.save(OUT_PATH+'NECIR_CSO_map_total.html')


def make_map_ej_characteristics(data_egs_merge: pd.DataFrame, data_cso: pd.DataFrame, 
    df_town_level: pd.DataFrame, df_watershed_level: pd.DataFrame, geo_watersheds_dict: dict):
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

        ## Draw choropleth layer for census blocks
        map_2.choropleth(
            geo_data=GEO_BLOCKGROUPS_PATH, 
            name='Census Block Groups',
            data=data_egs_merge[col],
            key_on='feature.properties.GEOID',
            legend_name='Block Group: '+col_label,
            threshold_scale = list(np.nanpercentile(data_egs_merge[col], [0,25,50,75,100])),  
            fill_color='BuGn', fill_opacity=0.7, line_opacity=0.3, highlight=True,
            )

        ## Draw Choropleth layer for towns
        map_2.choropleth(
            geo_data=GEO_TOWNS_PATH, 
            name='Municipalities',
            data=df_town_level[col],
            key_on='feature.properties.TOWN',
            legend_name='Municipality: '+col_label,
            threshold_scale = list(np.nanpercentile(df_town_level[col], [0,25,50,75,100])),  
            fill_color='PuRd', fill_opacity=0.7, line_opacity=0.3, highlight=True,
            )

        ## Draw Choropleth layer for watersheds
        map_2.choropleth(
            geo_data=GEO_WATERSHEDS_PATH, 
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
            Discharge volume (2011): {vol} (Millions of gallons)<br>
            Discharge frequency (2011): {N} discharges<br>
            </p>
            """.format(
                    address = cso['Nearest_Pipe_Address'],
                    body = cso['DischargesBody'],
                    muni = cso['Municipality'],
                    vol = cso['2011_Discharges_MGal'],
                    N = cso['2011_Discharges_MGal'],
                )
            iframe = folium.IFrame(html=html, width=400, height=200)
            popup = folium.Popup(iframe, max_width=500)
            folium.RegularPolygonMarker(
                    location=(cso['Latitude'], cso['Longitude']), 
                    popup=popup, 
                    number_of_sides=8, 
                    radius=6, 
                    color='green',
                    fill_color='green',
                ).add_to(map_2)

        ## Add labels for watersheds
        for feature in geo_watersheds_dict:
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
        map_2.save(OUT_PATH+'NECIR_CSO_map_EJ_'+col+'.html')



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


def make_chart_summary_ej_characteristics_town(df_town_level: pd.DataFrame, 
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
    mychart.set_params(JSinline = 0, ylabel = 'Fraction of households', xlabel='Municipality',
        scaleBeginAtZero=1, x_autoskip=True)

    mychart.jekyll_write(outpath)

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

def make_chart_ej_cso_comparison(data_egs_merge: pd.DataFrame, data_ins_g_ws_j: pd.DataFrame, 
    df_watershed_level: pd.DataFrame, outpath: str='../docs/_includes/charts/NECIR_EJSCREEN_correlation_bywatershed_{}.html'):
    """Comparison of EJ and CSO characteristics by geographic areas
    """
    print('Making comparison plot of EJ and CSO data')
    for i, col, col_label in (
        (0, 'MINORPCT', 'Fraction of population identifying as non-white'),
        (1, 'LOWINCPCT', 'Fraction of population with income less than twice the Federal poverty limit'),
        (2, 'LINGISOPCT', 'Fraction of population in households whose adults speak English less than "very well"'),
        ):
        ## Lookup base values - Census group block level
        l = data_egs_merge.Watershed.unique()
        l = l[pd.isnull(l) == 0]
        pop = data_egs_merge.groupby('Watershed')['ACSTOTPOP'].sum().loc[l].values
        x = df_watershed_level[col].loc[l].values
        y = data_ins_g_ws_j['2011_Discharges_MGal'].loc[l].values

        ## Calculate binned values
        x_bins = np.nanpercentile(x, list(np.linspace(0,100,5)))
        x_bin_cent = [np.mean([x_bins[i], x_bins[i+1]]) for i in range(len(x_bins) - 1)]
        x_bin_id = pd.cut(x, x_bins, labels=False)
        y_bin = np.array([
            weight_mean(y[x_bin_id == i], pop[x_bin_id == i])
            for i in range(len(x_bins) - 1)]).T

        ## Establish chart
        mychart = chartjs.chart("CSO discharge volume vs EJ characteristics by watershed: "+col, "Scatter", 640, 480)

        ## Add individual-level dataset
        mychart.add_dataset(
            np.array([x, y]).T, 
            dataset_label="Individual watersheds",
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
            ylabel = 'Total volume of discharge (2011; Millions of gallons)', 
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

        mychart.jekyll_write(outpath.format(col))


# -------------------------
# Regression modeling functions
# -------------------------

def fit_stan_model(col: str, data_egs_merge: pd.DataFrame, df_watershed_level: pd.DataFrame, 
    data_ins_g_ws_j: pd.DataFrame) -> Tuple[stan.fit.Fit, pd.DataFrame, dict, np.ndarray]:
    """Fit Stan model for a particular EJ characteristic (`col`)
    """
    print(f'Building stan model for {col}')
    ## Lookup base values - Census group block level
    l = data_egs_merge.Watershed.unique()
    l = l[pd.isnull(l) == 0]
    pop = data_egs_merge.groupby('Watershed')['ACSTOTPOP'].sum().loc[l].values
    x = df_watershed_level[col].loc[l].values
    y = data_ins_g_ws_j['2011_Discharges_MGal'].loc[l].values
    
    ## Fit Stan model
    stan_dat = {
        'J': len(x),
        'x': list(x),
        'y': list(y),
        'p': list(pop / np.mean(pop))
        }
    
    sm = stan.build(STAN_MODEL_CODE, data=stan_dat)
    fit = sm.sample(num_samples=10000, num_chains=10)
    fit_par = fit.to_frame()
    
    return fit, fit_par, stan_dat, pop
    
## Stan fit diagnostic output
#s = fit.summary()
#summary = pd.DataFrame(s['summary'], columns=s['summary_colnames'], index=s['summary_rownames'])
#print(col)
#print(summary)
    
def regression_plot_beta_posterior(fit_par: pd.DataFrame, col: str, plot_path: str, fact_file: str=FACT_FILE):
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
    with open(fact_file, 'a') as f:
        f.write(f'depend_cso_{col}: {np.median(ph):0.1f} times (90% confidence interval '
                f'{np.percentile(ph, 5):0.1f} to {np.percentile(ph, 95):0.1f} times)\n')

def regression_plot_model_draws(fit_par: pd.DataFrame, col_label: str, plot_path: str, stan_dat: dict, 
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
    plt.ylabel('CSO discharge (2011; Mgal)')
    
    plt.scatter(x, y, marker='o', c=pop_data / 1e3, cmap=cm.Blues, label='Watersheds', zorder=2)
    plt.colorbar(label='Population (1000s)')
    plt.legend(loc=2)
    plt.savefig(plot_path, dpi=200, bbox_inches='tight')

# -------------------------
# Main logic
# -------------------------

def main():
    """Load all data and generate all plots and analysis.
    """
    # Clear out the fact file
    open(FACT_FILE, 'w').close()
    
    # Data ETL
    geo_towns_dict, geo_watersheds_dict, geo_blockgroups_dict = get_geo_files()
    data_cso, data_ejs = load_data()
    # TODO should add these results to the database, not just the local (`memory`) cache
    data_cso = assign_cso_data_to_census_blocks(data_cso, geo_blockgroups_dict)
    data_ejs = assign_ej_data_to_geo_bins(data_ejs, geo_towns_dict, geo_watersheds_dict, geo_blockgroups_dict)
    data_ins_g_bg, data_ins_g_muni_j, data_ins_g_ws_j, data_egs_merge, df_watershed_level, df_town_level = apply_pop_weighted_avg(data_cso, data_ejs)
    
    # Make maps
    make_map_discharge_volumes(data_cso, geo_watersheds_dict, data_ins_g_bg, data_ins_g_muni_j, data_ins_g_ws_j)
    make_map_ej_characteristics(data_egs_merge, data_cso, df_town_level, df_watershed_level, geo_watersheds_dict)
    
    # Make charts
    make_chart_summary_ej_characteristics_watershed(df_watershed_level)
    make_chart_summary_ej_characteristics_town(df_town_level)
    make_chart_ej_cso_comparison(data_egs_merge, data_ins_g_ws_j, df_watershed_level)
    
    # Regression modeling
    for col, col_label in (
        ('MINORPCT', 'Fraction of population identifying as non-white'),
        ('LOWINCPCT', 'Fraction of population with income less than twice the Federal poverty limit'),
        ('LINGISOPCT', 'Fraction of population in households whose adults speak English less than "very well"'),
        ):
        fit, fit_par, stan_dat, pop_data = fit_stan_model(col, data_egs_merge, df_watershed_level, data_ins_g_ws_j)
        regression_plot_beta_posterior(fit_par, col, plot_path=FIG_PATH+'NECIR_CSO_stanfit_beta_'+col+'.png')
        regression_plot_model_draws(fit_par, col_label, FIG_PATH+'NECIR_CSO_stanfit_'+col+'.png', stan_dat, pop_data)
    
if __name__ == '__main__':
    main()
