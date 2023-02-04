"""Generate folium-based map visualizations and pystan regression model fits for CSO discharge distributions using
NECIR CSO data.

NOTE - this code was updated in 2023 to use pystan 3 conventions

NOTE - if you run into pystan errors when executing this script in a conda environment, try using 
[this solution](https://github.com/stan-dev/pystan/issues/294#issuecomment-988791438)
to update the C compilers in the env.
```
conda install -c conda-forge c-compiler cxx-compiler
```
"""

import pandas as pd
import numpy as np
import folium
import json
from shapely.geometry import shape, Point
from sqlalchemy import create_engine
import chartjs
import stan

import matplotlib as mpl
from matplotlib import pyplot as plt
from matplotlib import cm

COLOR_CYCLE = [c['color'] for c in list(mpl.rcParams['axes.prop_cycle'])]
FIG_PATH = '../docs/assets/figures/'

## Establish file to export facts
FACT_FILE = '../docs/data/facts_NECIR_CSO.yml'
with open(FACT_FILE, 'w') as f: f.write('')

OUT_PATH = '../docs/assets/maps/'


##########################
## Function defs
##########################

def hex2rgb(hexcode):
    # See http://www.psychocodes.in/rgb-to-hex-conversion-and-hex-to-rgb-conversion-in-python.html
    #rgb = tuple(map(ord,hexcode[1:].decode('hex')))
    # See https://stackoverflow.com/a/29643643
    rgb = tuple(int(hexcode.lstrip('#')[i:i+2], 16) for i in (0, 2 ,4))
    return rgb

def get_geo_files() -> tuple[dict, dict, dict]:
    """Load and return geo json files.
    """
    geo_path = '../docs/assets/geo_json/'
    geo_towns = geo_path+'TOWNSSURVEY_POLYM_geojson_simple.json'
    geo_watersheds = geo_path+'watshdp1_geojson_simple.json'
    geo_blockgroups = geo_path+'cb_2017_25_bg_500k.json'

    geo_towns_dict = json.load(open(geo_towns))['features']
    geo_watersheds_dict = json.load(open(geo_watersheds))['features']
    geo_blockgroups_dict = json.load(open(geo_blockgroups))['features']
    
    return geo_towns_dict, geo_watersheds_dict, geo_blockgroups_dict

def safe_float(x):
    try:
        return float(x)
    except:
        return np.nan

def load_data -> ():
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
        print(('No block group found for CSO #', str(cso_i)))


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
        print(('No Town found for Block Group #', str(cso_i)))
    ## Loop over watersheds
    for watershed_feature in geo_watersheds_dict:
        watershed_polygon = shape(watershed_feature['geometry'])
        if watershed_polygon.contains(point):
            bg_mapping.loc[feature['properties']['GEOID'], 'Watershed'] = watershed_feature['properties']['NAME'] 
    ## Warn if a watershed was not found
    if bg_mapping.loc[feature['properties']['GEOID'], 'Town'] is np.nan:
        print(('No Town found for Block Group #', str(cso_i)))

data_ejs = pd.merge(data_ejs, bg_mapping, left_on = 'ID', right_index=True, how='left')


#############################
## Calculate population weighted averages for EJ characteristics
#############################

## Get counts by block group
data_ins_g_bg = data_cso.groupby('BlockGroup').sum()[['2011_Discharges_MGal', '2011_Discharge_N']]
data_ins_g_bg_j = pd.merge(data_ins_g_bg, data_ejs, left_index=True, right_on ='ID', how='left')

## Get counts by municipality
data_ins_g_muni_j = pd.merge(data_cso, data_ejs, left_on='BlockGroup', right_on='ID', how='outer')\
                    .groupby('Town').sum()[['2011_Discharges_MGal', '2011_Discharge_N']].fillna(0)

## Get counts by watershed
data_ins_g_ws_j = pd.merge(data_cso, data_ejs, left_on='BlockGroup', right_on='ID', how='outer')\
                    .groupby('Watershed').sum()[['2011_Discharges_MGal', '2011_Discharge_N']].fillna(0)


data_egs_merge = pd.merge(
    data_ins_g_bg_j.groupby('ID')[['2011_Discharge_N', '2011_Discharges_MGal']].sum(),
    data_ejs, left_index = True, right_on='ID', how='outer')

def pop_weighted_average(x, cols):
    w = x['ACSTOTPOP']
    out = []
    for col in cols:
        out += [np.sum(w * x[col].values) / np.sum(w)]
    return pd.Series(data = out, index=cols)

df_watershed_level = data_egs_merge.groupby('Watershed').apply(lambda x: pop_weighted_average(x, ['MINORPCT', 'LOWINCPCT', 'LINGISOPCT', 'OVER64PCT', 'VULSVI6PCT']))

df_town_level = data_egs_merge.groupby('Town').apply(lambda x: pop_weighted_average(x, ['MINORPCT', 'LOWINCPCT', 'LINGISOPCT', 'OVER64PCT', 'VULSVI6PCT']))


#############################
## Map of discharge volumes with layers for watershed, town, and census block group with CSO points
#############################

## Map total discharge volume
map_1 = folium.Map(
    location=[42.29, -71.74], 
    zoom_start=8.2,
    tiles='Stamen Terrain',
    )

## Draw choropleth layer for census blocks
map_1.choropleth(
    geo_data=geo_blockgroups, 
    name='Census Block Groups',
    data=data_ins_g_bg['2011_Discharges_MGal'],
    key_on='feature.properties.GEOID',
    legend_name='Block Group: Total volume of discharge (2011; Millions of gallons)',
    threshold_scale = list(np.nanpercentile(data_ins_g_bg['2011_Discharges_MGal'], [0,25,50,75,100])),  
    fill_color='BuGn', fill_opacity=0.7, line_opacity=0.3, highlight=True,
    )

## Draw Choropleth layer for towns
map_1.choropleth(
    geo_data=geo_towns, 
    name='Municipalities',
    data=data_ins_g_muni_j['2011_Discharges_MGal'],
    key_on='feature.properties.TOWN',
    legend_name='Municipality: Total volume of discharge (2011; Millions of gallons)',
    threshold_scale = [0]+list(np.nanpercentile(data_ins_g_muni_j['2011_Discharges_MGal'][data_ins_g_muni_j['2011_Discharges_MGal'] > 0], [25,50,75,100])),  
    fill_color='PuRd', fill_opacity=0.7, line_opacity=0.3, highlight=True,
    )

## Draw Choropleth layer for watersheds
map_1.choropleth(
    geo_data=geo_watersheds, 
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


#############################
## Map of EJ racial characteristics with layers for watershed, town, and census block group with CSO points
#############################

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
        geo_data=geo_blockgroups, 
        name='Census Block Groups',
        data=data_egs_merge[col],
        key_on='feature.properties.GEOID',
        legend_name='Block Group: '+col_label,
        threshold_scale = list(np.nanpercentile(data_egs_merge[col], [0,25,50,75,100])),  
        fill_color='BuGn', fill_opacity=0.7, line_opacity=0.3, highlight=True,
        )

    ## Draw Choropleth layer for towns
    map_2.choropleth(
        geo_data=geo_towns, 
        name='Municipalities',
        data=df_town_level[col],
        key_on='feature.properties.TOWN',
        legend_name='Municipality: '+col_label,
        threshold_scale = list(np.nanpercentile(df_town_level[col], [0,25,50,75,100])),  
        fill_color='PuRd', fill_opacity=0.7, line_opacity=0.3, highlight=True,
        )

    ## Draw Choropleth layer for watersheds
    map_2.choropleth(
        geo_data=geo_watersheds, 
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


#############################
## Summary of EJ characteristics of geographic areas
#############################

## By watershed
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

mychart.jekyll_write('../docs/_includes/charts/EJSCREEN_demographics_watershed.html')




## By town
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

mychart.jekyll_write('../docs/_includes/charts/EJSCREEN_demographics_municipality.html')


#############################
## Comparison of EJ and CSO characteristics by geographic areas
#############################

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

    ## Boostrapped weighted mean function
    def weight_mean(x, weights, N=1000):
        avgs = np.zeros(N)
        nonan_sel = (np.isnan(x) == 0) & (np.isnan(weights) == 0)
        x = x[nonan_sel]
        weights = weights[nonan_sel]
        for i in range(N):
            sel = np.random.randint(len(x), size=len(x))
            avgs[i] = np.average(x[sel], weights=weights[sel])
        return np.mean(avgs), np.std(avgs)

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

    mychart.jekyll_write('../docs/_includes/charts/NECIR_EJSCREEN_correlation_bywatershed_'+col+'.html')


#############################
## Regression model
#############################

stan_model = """
data {
    int<lower=0> J;         // number of watersheds
    vector<lower=0>[J] x;   // EJ parameter
    vector<lower=0>[J] y;   // CSO discharge
    vector<lower=0>[J] p;   // population (normalized)
}
transformed data {
    real<lower=0> s_y;
    
    s_y = sd(y);
}
parameters {
    real<lower=0> alpha;    // Multiplicative offset
    real beta;              // Exponent
    real<lower=0> sigma;    // Error model scaler
}
transformed parameters {
    vector[J] theta;        // Regression estimate
    
    for (i in 1:J) {
        theta[i] = alpha * pow(x[i], beta);
    }
}
model {
    sigma ~ normal(0, 4);
    alpha ~ normal(0, 10*s_y);
    beta ~ normal(0, 4);
    y ~ normal(theta, sigma * s_y * sqrt(inv(p)));
}
"""

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
    
    ## Fit Stan model
    stan_dat = {
        'J': len(x),
        'x': list(x),
        'y': list(y),
        'p': list(pop / np.mean(pop))
        }
    
    print(f'Building stan model for {col}')
    sm = stan.build(stan_model, data=stan_dat)
    fit = sm.sampling(num_samples=10000, num_chains=10)
    fit_par = fit.to_frame()
    
    ## Stan fit diagnostic output
    #s = fit.summary()
    #summary = pd.DataFrame(s['summary'], columns=s['summary_colnames'], index=s['summary_rownames'])
    #print(col)
    #print(summary)
    
    ## Plot beta posterior
    plt.figure()
    ph = 2**fit['beta']
    plt.hist(ph, bins=100, range=[0,6])
    plt.xlabel("2x growth ratio -- " + col)
    plt.ylabel('Posterior samples')
    plt.savefig(FIG_PATH+'NECIR_CSO_stanfit_beta_'+col+'.png', dpi=200)
    
    ## Plot fitted model draws
    plt.figure()
    N = len(fit_par['beta'])
    for i,n in enumerate(np.random.randint(0, N, 20)):
        px = np.linspace(min(x), max(x), 1000)
        plt.plot(px, fit_par.loc['alpha', n]*px**fit_par.loc['beta', n], color='r', alpha=0.3, 
                 label = 'Posterior draw' if i==0 else None, zorder=1)
    
    plt.xlabel(col_label, wrap=True)
    plt.ylabel('CSO discharge (2011; Mgal)')
    
    plt.scatter(x, y, marker='o', c=pop/1e3, cmap=cm.Blues, label='Watersheds', zorder=2)
    plt.colorbar(label='Population (1000s)')
    plt.legend(loc=2)
    plt.savefig(FIG_PATH+'NECIR_CSO_stanfit_'+col+'.png', dpi=200, bbox_inches='tight')
    
    ## Output summary dependence statistics
    with open(FACT_FILE, 'a') as f:
        f.write(f'depend_cso_{col}: {np.median(ph):0.1f} times (90% confidence interval '
                f'{np.percentile(ph, 5):0.1f} to {np.percentile(ph, 95):0.1f} times)\n')
