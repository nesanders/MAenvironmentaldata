"""Generate charts for the EPA 303(d) Integrated List of Waters analysis.

Produces dashboard charts (called with prefix='dash_' by dashboard_charts.py)
and analysis-post charts (called without prefix from __main__ block).

Dashboard charts (6):
  {prefix}EPA303d_impaired_trend      — Impaired AU count by cycle and water type
  {prefix}EPA303d_causes_breakdown    — Top impairment causes (most recent cycle)
  {prefix}EPA303d_cso_impaired        — Annual CSO volume by 303(d) status
  {prefix}EPA303d_tmdl_trend          — Cumulative TMDL progress by cycle
  {prefix}EPA303d_persistence         — Persistent vs. newly listed impaired AUs
  {prefix}EPA303d_causes_trend        — Top impairment causes across all cycles

Analysis-post charts (4, no prefix):
  EPA303d_tmdl_map                   — Folium map: TMDL status of 2022 assessment units
  EPA303d_watershed_impairment       — Top watersheds by impaired AU count, stacked by water type
  EPA303d_bacterial_sources          — Source attribution for bacterial impairments
  EPA303d_cso_bact_cdf               — CDF: bacterial impairment fraction, CSO vs. non-CSO waterways

Data files written:
  docs/data/facts_EPA303d.yml        — Key facts for use in Jekyll post templates
  docs/data/EPA_303d_delisted.csv    — AUs impaired in earliest cycle but removed by latest cycle

See docs/_posts/2026-04-11-ma-impaired-waters-303d.md for the analysis post.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
from sqlalchemy import create_engine
import chartjs


# ─── colour palette ───────────────────────────────────────────────────────────
BLUE   = 'rgba(54, 110, 179, 0.85)'
RED    = 'rgba(200, 60, 60, 0.85)'
ORANGE = 'rgba(230, 140, 40, 0.85)'
GREEN  = 'rgba(60, 170, 80, 0.85)'
GREY   = 'rgba(150, 150, 150, 0.6)'
PURPLE = 'rgba(130, 80, 200, 0.85)'
TEAL   = 'rgba(30, 160, 160, 0.85)'

WATER_TYPE_COLORS = {
    'RIVER':           'rgba(54, 110, 179, 0.85)',
    'FRESHWATER LAKE': 'rgba(60, 170, 80, 0.85)',
    'ESTUARY':         'rgba(230, 140, 40, 0.85)',
    'COASTAL':         'rgba(130, 80, 200, 0.85)',
    'WETLAND':         'rgba(150, 150, 150, 0.7)',
}

# Line colours for causes-trend chart (up to 8 causes)
CAUSE_COLORS = [
    'rgba(200, 60, 60, 0.9)',    # red
    'rgba(54, 110, 179, 0.9)',   # blue
    'rgba(60, 170, 80, 0.9)',    # green
    'rgba(230, 140, 40, 0.9)',   # orange
    'rgba(130, 80, 200, 0.9)',   # purple
    'rgba(30, 160, 160, 0.9)',   # teal
    'rgba(180, 100, 50, 0.9)',   # brown
    'rgba(220, 80, 180, 0.9)',   # pink
]


_CHARTJS_CDN = "<script src='https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js'></script>"


def _write_cso_cdf_html(outpath, cso_points, noncso_fracs):
    """Write a ranked-distribution chart as a Jekyll-compatible HTML file.

    X axis: percentile rank of waterway (0–100%).
    Y axis: bacterial impairment fraction (bacterial-impaired AUs / assessed AUs).

    CSO waterways shown as labeled dots; non-CSO as a smooth grey line.
    Reading the chart: at any x-percentile, the y value shows the bacterial
    fraction for that ranked waterway — CSO line shifted upward = worse impairment.

    Parameters
    ----------
    outpath : str
        Output file path.
    cso_points : list of dict
        Each dict: {fraction, name, n_bact, n_assessed}.  Sorted ascending by fraction.
    noncso_fracs : list of float
        Sorted ascending.
    """
    import json

    n_cso = len(cso_points)
    n_noncso = len(noncso_fracs)

    # Flipped axes: x = percentile rank, y = bacterial fraction
    cso_data_js = json.dumps([
        {'x': round((i + 1) / n_cso, 4),
         'y': round(float(pt['fraction']), 4),
         'wbname': pt['name'],
         'nbact': int(pt['n_bact']),
         'nassessed': int(pt['n_assessed'])}
        for i, pt in enumerate(cso_points)
    ])
    noncso_data_js = json.dumps([
        {'x': round((i + 1) / n_noncso, 4), 'y': round(float(f), 4)}
        for i, f in enumerate(noncso_fracs)
    ])

    canvas_id = 'EPA303d_cso_bact_cdf'
    html = f"""{{% raw  %}}
<html>
<head>{_CHARTJS_CDN}</head>
<body>
<div style="width:700px;height:480px;max-width:99%" class="chartjs">
<canvas id="{canvas_id}" height="480" width="700"></canvas>
<script>
Chart.defaults.font.size = 12;
var chart_data = {{
    type: 'scatter',
    data: {{
        datasets: [
            {{
                label: 'Non-CSO waterways (n={n_noncso})',
                data: {noncso_data_js},
                borderColor: 'rgba(150,150,150,0.55)',
                backgroundColor: 'rgba(0,0,0,0)',
                showLine: true,
                pointRadius: 0,
                borderWidth: 2.5,
                tension: 0
            }},
            {{
                label: 'CSO-receiving waterways (n={n_cso})',
                data: {cso_data_js},
                borderColor: 'rgba(200,60,60,0.85)',
                backgroundColor: 'rgba(200,60,60,0.8)',
                showLine: true,
                fill: false,
                pointRadius: 5,
                pointHoverRadius: 7,
                borderWidth: 2,
                tension: 0
            }}
        ]
    }},
    options: {{
        scales: {{
            x: {{
                type: 'linear',
                min: 0,
                max: 1,
                title: {{
                    display: true,
                    text: 'Waterways ranked by bacterial impairment fraction (percentile)'
                }},
                ticks: {{ callback: function(v) {{ return (v*100)+'%'; }} }}
            }},
            y: {{
                min: 0,
                max: 1,
                title: {{
                    display: true,
                    text: 'Fraction of assessed AUs with bacterial impairment'
                }},
                ticks: {{ callback: function(v) {{ return (v*100)+'%'; }} }}
            }}
        }},
        plugins: {{
            legend: {{ display: true }},
            tooltip: {{
                bodyFont: {{ size: 11 }},
                callbacks: {{
                    label: function(context) {{
                        var pt = context.raw;
                        if (pt.wbname !== undefined) {{
                            return pt.wbname + ' \u2014 ' + pt.nbact + '/' + pt.nassessed
                                   + ' assessed AUs (' + (pt.x*100).toFixed(0) + '% bacterial)';
                        }}
                        return (pt.x*100).toFixed(0) + '% bacterial impairment';
                    }}
                }}
            }}
        }}
    }}
}};
{{
    var ctx = document.getElementById("{canvas_id}").getContext("2d");
    var mychart = new Chart(ctx, chart_data);
}}
</script>
</div>
</body>
</html>
{{% endraw  %}}
"""
    with open(outpath, 'w') as f:
        f.write(html)



def _to_float_list(series):
    """Convert pandas Series / numpy array to list of Python floats for JSON safety."""
    return [float(v) if pd.notna(v) else None for v in series]


def _normalise_water_type(series):
    """Normalise waterType variants to a consistent set."""
    s = series.str.strip().str.upper()
    return s.replace({
        'LAKE': 'FRESHWATER LAKE',
        'LAKE/POND': 'FRESHWATER LAKE',
        'FRESHWATER LAKE/POND': 'FRESHWATER LAKE',
    })


def generate_charts(engine, prefix=''):
    """Generate 303(d) impaired waters charts (dashboard + post).

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine
        Database connection engine pointing at AMEND.db
    prefix : str, default ''
        Filename prefix (e.g. 'dash_' for dashboard charts)
    """
    print('Loading 303(d) data...')
    df = pd.read_sql_query('SELECT * FROM EPA_303d_Impairments', engine)
    cso = pd.read_sql_query('SELECT waterBody, volumnOfEvent, Year FROM MAEEADP_CSO', engine)
    mapping = pd.read_sql_query('SELECT * FROM CSO_303d_Mapping', engine)

    latest_cycle = int(df['reportingCycle'].max())
    earliest_cycle = int(df['reportingCycle'].min())
    cycles = sorted(df['reportingCycle'].unique())
    print(f'Cycles: {cycles}, latest: {latest_cycle}')

    df_imp = df[df['category'].isin(['4A', '4B', '4C', '5'])].copy()
    df_imp['waterType'] = _normalise_water_type(df_imp['waterType'])

    # ── 1. Impaired water count trend by cycle and water type ─────────────────
    print('Chart 1: Impaired trend...')

    main_types = ['RIVER', 'FRESHWATER LAKE', 'ESTUARY', 'COASTAL', 'WETLAND']
    df_imp['waterTypeGroup'] = df_imp['waterType'].where(
        df_imp['waterType'].isin(main_types), other='OTHER'
    )
    pivot = (df_imp
             .groupby(['reportingCycle', 'waterTypeGroup'])['auId']
             .nunique()
             .unstack(fill_value=0))
    type_order = [t for t in main_types if t in pivot.columns] + \
                 [c for c in pivot.columns if c not in main_types]

    mychart = chartjs.chart('MA 303(d) Impaired Waters by Type', 'Bar', 700, 420)
    mychart.set_labels([str(c) for c in pivot.index.tolist()])
    for wtype in type_order:
        if wtype not in pivot.columns:
            continue
        color = WATER_TYPE_COLORS.get(wtype, GREY)
        mychart.add_dataset(
            _to_float_list(pivot[wtype]),
            wtype.title(),
            backgroundColor=f"'{color}'",
            stack="'type'",
        )
    mychart.set_params(
        JSinline=0,
        ylabel='Impaired assessment units (distinct)',
        xlabel='Reporting cycle',
        scaleBeginAtZero=1,
        stacked=1,
    )
    mychart.jekyll_write(f'../docs/_includes/charts/{prefix}EPA303d_impaired_trend.html')

    # ── 2. Top impairment causes (most recent cycle) ───────────────────────────
    print('Chart 2: Causes breakdown...')

    df_causes = (df[(df['reportingCycle'] == latest_cycle) &
                    (df['attainment'] == 'Not Supporting') &
                    (df['cause'].notna())]
                 .groupby('cause')['auId']
                 .nunique()
                 .sort_values(ascending=False)
                 .head(15))

    mychart = chartjs.chart(f'Top Causes of MA Water Impairment ({latest_cycle})', 'Bar', 700, 500)
    mychart.set_labels(df_causes.index.str.title().tolist())
    mychart.add_dataset(
        _to_float_list(df_causes),
        f'Impaired assessment units ({latest_cycle})',
        backgroundColor=f"'{BLUE}'",
    )
    mychart.set_params(
        JSinline=0,
        ylabel='Impairment cause',
        xlabel='Impaired assessment units (distinct)',
        scaleBeginAtZero=1,
    )
    mychart.jekyll_write(f'../docs/_includes/charts/{prefix}EPA303d_causes_breakdown.html')

    # ── 3. Annual CSO volume by 303(d) impairment status ─────────────────────
    print('Chart 3: CSO impaired...')

    cso_merged = cso.merge(mapping, left_on='waterBody', right_on='csoWaterBody', how='left')
    df_latest_status = (df[df['reportingCycle'] == latest_cycle]
                        [['waterbody', 'attainment']].drop_duplicates().copy())

    def _aggregate_status(group):
        if 'Not Supporting' in group.values:
            return 'Not Supporting'
        if 'Fully Supporting' in group.values:
            return 'Fully Supporting'
        return group.iloc[0]

    status_by_wb = df_latest_status.groupby('waterbody')['attainment'].agg(_aggregate_status)
    cso_merged['impairmentStatus'] = cso_merged['waterbody303d'].map(status_by_wb).fillna('Not Matched')
    cso_merged['Year'] = pd.to_numeric(cso_merged['Year'], errors='coerce')
    cso_merged['volumnOfEvent'] = pd.to_numeric(cso_merged['volumnOfEvent'], errors='coerce').fillna(0)

    cso_g = (cso_merged
             .groupby(['Year', 'impairmentStatus'])['volumnOfEvent']
             .sum()
             .unstack(fill_value=0)
             / 1e9)
    cso_years = [int(y) for y in sorted(cso_g.index.dropna())]
    cso_g = cso_g.reindex(cso_years)

    status_order = ['Not Supporting', 'Fully Supporting', 'Not Matched']
    status_labels = {
        'Not Supporting': 'Confirmed impaired (Not Supporting)',
        'Fully Supporting': 'Fully Supporting',
        'Not Matched': 'Status unknown (no 303d match)',
    }
    status_colors = {'Not Supporting': RED, 'Fully Supporting': GREEN, 'Not Matched': GREY}

    mychart = chartjs.chart('CSO Discharge Volume by 303(d) Impairment Status', 'Bar', 700, 420)
    mychart.set_labels([str(y) for y in cso_years])
    for status in status_order:
        if status not in cso_g.columns:
            continue
        mychart.add_dataset(
            _to_float_list(cso_g[status]),
            status_labels[status],
            backgroundColor=f"'{status_colors[status]}'",
            stack="'status'",
        )
    mychart.set_params(
        JSinline=0,
        ylabel='Discharge volume (billion gallons)',
        xlabel='Year',
        scaleBeginAtZero=1,
        stacked=1,
    )
    mychart.jekyll_write(f'../docs/_includes/charts/{prefix}EPA303d_cso_impaired.html')

    # ── 4. TMDL progress over cycles ─────────────────────────────────────────
    print('Chart 4: TMDL trend...')

    tmdl_pivot = (df_imp.groupby(['reportingCycle', 'hasTmdl'])['auId']
                  .nunique().unstack(fill_value=0))

    mychart = chartjs.chart('MA 303(d): TMDL Progress Over Time', 'Bar', 700, 420)
    mychart.set_labels([str(c) for c in tmdl_pivot.index.tolist()])
    if 1 in tmdl_pivot.columns:
        mychart.add_dataset(
            _to_float_list(tmdl_pivot[1]),
            'Has cleanup plan (TMDL or equivalent)',
            backgroundColor=f"'{GREEN}'",
            stack="'tmdl'",
        )
    if 0 in tmdl_pivot.columns:
        mychart.add_dataset(
            _to_float_list(tmdl_pivot[0]),
            'No cleanup plan (Category 5)',
            backgroundColor=f"'{RED}'",
            stack="'tmdl'",
        )
    mychart.set_params(
        JSinline=0,
        ylabel='Impaired assessment units',
        xlabel='Reporting cycle',
        scaleBeginAtZero=1,
        stacked=1,
    )
    mychart.jekyll_write(f'../docs/_includes/charts/{prefix}EPA303d_tmdl_trend.html')

    # ── 5. Persistence of impairment ─────────────────────────────────────────
    print('Chart 5: Persistence...')

    aus_earliest = set(df_imp[df_imp['reportingCycle'] == earliest_cycle]['auId'])
    persistent_counts = []
    new_since_earliest_counts = []
    for cycle in cycles:
        cycle_aus = set(df_imp[df_imp['reportingCycle'] == cycle]['auId'])
        persistent_counts.append(len(cycle_aus & aus_earliest))
        new_since_earliest_counts.append(len(cycle_aus - aus_earliest))

    mychart = chartjs.chart('MA 303(d): Persistence of Impaired Waters', 'Bar', 700, 420)
    mychart.set_labels([str(c) for c in cycles])
    mychart.add_dataset(
        [float(v) for v in persistent_counts],
        f'Listed as impaired in {earliest_cycle} (original cohort)',
        backgroundColor=f"'{RED}'",
        stack="'cohort'",
    )
    mychart.add_dataset(
        [float(v) for v in new_since_earliest_counts],
        f'First listed after {earliest_cycle}',
        backgroundColor=f"'{ORANGE}'",
        stack="'cohort'",
    )
    mychart.set_params(
        JSinline=0,
        ylabel='Impaired assessment units',
        xlabel='Reporting cycle',
        scaleBeginAtZero=1,
        stacked=1,
    )
    mychart.jekyll_write(f'../docs/_includes/charts/{prefix}EPA303d_persistence.html')

    # ── 6. Top impairment causes over time (line chart) ───────────────────────
    print('Chart 6: Causes trend...')

    # Select top 8 causes from most recent cycle; track across all cycles
    top8_causes = (df[(df['reportingCycle'] == latest_cycle) &
                      (df['attainment'] == 'Not Supporting') &
                      (df['cause'].notna())]
                   .groupby('cause')['auId'].nunique()
                   .sort_values(ascending=False)
                   .head(8).index.tolist())

    mychart = chartjs.chart('Top Impairment Causes Across Reporting Cycles', 'Line', 700, 440)
    mychart.set_labels([str(c) for c in cycles])
    for i, cause in enumerate(top8_causes):
        counts = []
        for cycle in cycles:
            # Case-insensitive match to handle ALL-CAPS variations across cycles
            mask = ((df['reportingCycle'] == cycle) &
                    (df['attainment'] == 'Not Supporting') &
                    (df['cause'].str.upper() == cause.upper()))
            counts.append(float(df[mask]['auId'].nunique()))
        color = CAUSE_COLORS[i % len(CAUSE_COLORS)]
        mychart.add_dataset(
            counts,
            cause.title(),
            borderColor=f"'{color}'",
            backgroundColor=f"'rgba(0,0,0,0)'",
            fill='false',
            pointRadius='4',
        )
    mychart.set_params(
        JSinline=0,
        ylabel='Impaired assessment units (distinct)',
        xlabel='Reporting cycle',
        scaleBeginAtZero=1,
    )
    mychart.jekyll_write(f'../docs/_includes/charts/{prefix}EPA303d_causes_trend.html')

    # ── 7. Facts YAML ─────────────────────────────────────────────────────────
    print('Writing facts YAML...')

    n_cycles = len(cycles)
    impaired_by_cycle = df_imp.groupby('reportingCycle')['auId'].nunique()
    impaired_earliest = int(impaired_by_cycle[earliest_cycle])
    impaired_latest = int(impaired_by_cycle[latest_cycle])
    impaired_pct_change = round(100 * (impaired_latest - impaired_earliest) / impaired_earliest, 1)

    # Top causes
    top_cause = (df[(df['reportingCycle'] == latest_cycle) &
                    (df['attainment'] == 'Not Supporting') &
                    (df['cause'].notna())]
                 .groupby('cause')['auId'].nunique()
                 .sort_values(ascending=False))
    top_cause_1 = top_cause.index[0].title() if len(top_cause) > 0 else 'N/A'
    top_cause_1_n = int(top_cause.iloc[0]) if len(top_cause) > 0 else 0
    top_cause_2 = top_cause.index[1].title() if len(top_cause) > 1 else 'N/A'
    top_cause_2_n = int(top_cause.iloc[1]) if len(top_cause) > 1 else 0
    top_cause_3 = top_cause.index[2].title() if len(top_cause) > 2 else 'N/A'
    top_cause_3_n = int(top_cause.iloc[2]) if len(top_cause) > 2 else 0

    # TMDL progress
    tmdl_pf = (df_imp.groupby(['reportingCycle', 'hasTmdl'])['auId']
               .nunique().unstack(fill_value=0))
    tmdl_with_earliest = int(tmdl_pf.get(1, pd.Series(0, index=tmdl_pf.index)).get(earliest_cycle, 0))
    tmdl_without_earliest = int(tmdl_pf.get(0, pd.Series(0, index=tmdl_pf.index)).get(earliest_cycle, 0))
    tmdl_pct_earliest = round(100 * tmdl_with_earliest / impaired_earliest, 1) if impaired_earliest > 0 else 0.0
    tmdl_with_latest = int(tmdl_pf.get(1, pd.Series(0, index=tmdl_pf.index)).get(latest_cycle, 0))
    tmdl_without_latest = int(tmdl_pf.get(0, pd.Series(0, index=tmdl_pf.index)).get(latest_cycle, 0))
    tmdl_pct_latest = round(100 * tmdl_with_latest / impaired_latest, 1) if impaired_latest > 0 else 0.0
    tmdl_has_series = tmdl_pf.get(1, pd.Series(0, index=tmdl_pf.index))
    avg_net_tmdl_per_cycle = int(round(float(tmdl_has_series.diff().dropna().mean()), 0))
    years_to_clear_backlog = (int(round(tmdl_without_latest / avg_net_tmdl_per_cycle * 2, 0))
                              if avg_net_tmdl_per_cycle > 0 else 9999)
    year_backlog_cleared = latest_cycle + years_to_clear_backlog

    # CSO volume by 303(d) status
    cso_m2 = cso.merge(mapping, left_on='waterBody', right_on='csoWaterBody', how='left')
    cso_m2['impairmentStatus'] = cso_m2['waterbody303d'].map(status_by_wb).fillna('Not Matched')
    cso_m2['volumnOfEvent'] = pd.to_numeric(cso_m2['volumnOfEvent'], errors='coerce').fillna(0)
    total_by_status = cso_m2.groupby('impairmentStatus')['volumnOfEvent'].sum()
    vol_not_supporting = float(total_by_status.get('Not Supporting', 0)) / 1e9
    vol_not_matched = float(total_by_status.get('Not Matched', 0)) / 1e9
    vol_total_matched = float(total_by_status.drop('Not Matched', errors='ignore').sum()) / 1e9
    vol_total = float(total_by_status.sum()) / 1e9
    pct_vol_impaired_of_matched = round(100 * vol_not_supporting / vol_total_matched, 1) if vol_total_matched > 0 else 0.0
    pct_vol_impaired_of_total = round(100 * vol_not_supporting / vol_total, 1) if vol_total > 0 else 0.0

    n_cso_mapped = int(mapping.shape[0])
    n_cso_unique_wb = cso['waterBody'].dropna().nunique()

    # Unmapped CSO waterBodies (for post explanation)
    all_cso_wb = set(cso['waterBody'].dropna().unique())
    mapped_wb = set(mapping['csoWaterBody'])
    n_cso_not_matched = len(all_cso_wb - mapped_wb)

    # TMDL survival cohort facts (for post text)
    cat5_cohort = set(df_imp[(df_imp['reportingCycle'] == earliest_cycle) &
                              (df_imp['category'] == '5')]['auId'])
    n_cohort_cat5 = len(cat5_cohort)
    got_tmdl_ever = df_imp[(df_imp['auId'].isin(cat5_cohort)) &
                           (df_imp['hasTmdl'] == 1)]['auId'].nunique()
    still_no_tmdl = n_cohort_cat5 - got_tmdl_ever
    pct_still_no_tmdl = int(round(100 * still_no_tmdl / n_cohort_cat5, 0)) if n_cohort_cat5 > 0 else 0

    # Persistence
    aus_latest = set(df_imp[df_imp['reportingCycle'] == latest_cycle]['auId'])
    n_persistent = len(aus_earliest & aus_latest)
    n_delisted = len(aus_earliest - aus_latest)
    n_newly_added = len(aus_latest - aus_earliest)
    pct_persistent = int(round(100 * n_persistent / len(aus_earliest), 0)) if aus_earliest else 0
    pct_delisted = int(round(100 * n_delisted / len(aus_earliest), 0)) if aus_earliest else 0
    au_cycle_counts = df_imp.groupby('auId')['reportingCycle'].nunique()
    n_in_all_cycles = int((au_cycle_counts == n_cycles).sum())

    # Size-weighted
    rivers_imp = df_imp[df_imp['waterType'] == 'RIVER'].drop_duplicates(subset=['reportingCycle', 'auId'])
    lakes_imp = (df_imp[df_imp['waterType'] == 'FRESHWATER LAKE']
                 .drop_duplicates(subset=['reportingCycle', 'auId']))
    river_miles_by_cycle = rivers_imp.groupby('reportingCycle')['auSize'].sum()
    lake_acres_by_cycle = lakes_imp.groupby('reportingCycle')['auSize'].sum()
    river_miles_earliest = int(river_miles_by_cycle.get(earliest_cycle, pd.Series([0])).round(0))
    river_miles_latest = int(river_miles_by_cycle.get(latest_cycle, pd.Series([0])).round(0))
    river_miles_pct_change = int(round(100 * (river_miles_latest - river_miles_earliest) / river_miles_earliest, 0))
    lake_acres_earliest = int(lake_acres_by_cycle.get(earliest_cycle, pd.Series([0])).round(0))
    lake_acres_latest = int(lake_acres_by_cycle.get(latest_cycle, pd.Series([0])).round(0))

    # Swimming use
    pcr_fail = int(df[(df['designatedUse'] == 'Primary Contact Recreation') &
                      (df['attainment'] == 'Not Supporting') &
                      (df['reportingCycle'] == latest_cycle)]['auId'].nunique())
    pcr_assessed = int(df[(df['designatedUse'] == 'Primary Contact Recreation') &
                          (df['reportingCycle'] == latest_cycle) &
                          (df['attainment'].isin(['Not Supporting', 'Fully Supporting']))
                          ]['auId'].nunique())
    pct_pcr_failing = int(round(100 * pcr_fail / pcr_assessed, 0)) if pcr_assessed > 0 else 0

    facts = {
        'latest_cycle': latest_cycle,
        'earliest_cycle': earliest_cycle,
        'n_cycles': n_cycles,
        'impaired_earliest': impaired_earliest,
        'impaired_latest': impaired_latest,
        'impaired_pct_change': impaired_pct_change,
        'top_cause_1': top_cause_1,
        'top_cause_1_n': top_cause_1_n,
        'top_cause_2': top_cause_2,
        'top_cause_2_n': top_cause_2_n,
        'top_cause_3': top_cause_3,
        'top_cause_3_n': top_cause_3_n,
        'tmdl_with_earliest': tmdl_with_earliest,
        'tmdl_without_earliest': tmdl_without_earliest,
        'tmdl_pct_earliest': tmdl_pct_earliest,
        'tmdl_with_latest': tmdl_with_latest,
        'tmdl_without_latest': tmdl_without_latest,
        'tmdl_pct_latest': tmdl_pct_latest,
        'avg_net_tmdl_per_cycle': avg_net_tmdl_per_cycle,
        'years_to_clear_backlog': years_to_clear_backlog,
        'year_backlog_cleared': year_backlog_cleared,
        'n_cso_mapped': n_cso_mapped,
        'n_cso_unique_wb': n_cso_unique_wb,
        'n_cso_not_matched': n_cso_not_matched,
        'vol_not_supporting_bgal': round(vol_not_supporting, 1),
        'vol_not_matched_bgal': round(vol_not_matched, 1),
        'vol_total_bgal': round(vol_total, 1),
        'pct_vol_impaired_of_matched': pct_vol_impaired_of_matched,
        'pct_vol_impaired_of_total': pct_vol_impaired_of_total,
        'n_persistent': n_persistent,
        'n_delisted': n_delisted,
        'n_newly_added': n_newly_added,
        'pct_persistent': pct_persistent,
        'pct_delisted': pct_delisted,
        'n_in_all_cycles': n_in_all_cycles,
        'river_miles_earliest': river_miles_earliest,
        'river_miles_latest': river_miles_latest,
        'river_miles_pct_change': river_miles_pct_change,
        'lake_acres_earliest': lake_acres_earliest,
        'lake_acres_latest': lake_acres_latest,
        'pcr_fail': pcr_fail,
        'pcr_assessed': pcr_assessed,
        'pct_pcr_failing': pct_pcr_failing,
        'n_cohort_cat5': n_cohort_cat5,
        'still_no_tmdl': still_no_tmdl,
        'pct_still_no_tmdl': pct_still_no_tmdl,
    }
    # Keys where large integers should be comma-formatted for display in the post
    _COMMA_FORMAT_KEYS = {
        'river_miles_earliest', 'river_miles_latest',
        'lake_acres_earliest', 'lake_acres_latest',
        'pcr_fail', 'pcr_assessed',
        'impaired_earliest', 'impaired_latest',
        'tmdl_with_earliest', 'tmdl_without_earliest',
        'tmdl_with_latest', 'tmdl_without_latest',
        'n_in_all_cycles', 'n_persistent', 'n_delisted', 'n_newly_added',
        'n_cohort_cat5', 'still_no_tmdl',
    }

    def _fmt(k, v):
        if k in _COMMA_FORMAT_KEYS and isinstance(v, int) and v >= 1000:
            return f'"{v:,}"'  # quoted string so YAML parsers don't trip on commas
        return v

    # ── 8. Delisted waterbodies CSVs (split by 2022 status) ──────────────────
    # NOTE: facts YAML is written after this block so group counts can be included.
    print('Writing delisted waterbodies CSVs...')

    delisted_aus = aus_earliest - aus_latest

    # 2022 status for each delisted AU (any category present in latest cycle)
    status_2022 = (df[df['reportingCycle'] == latest_cycle]
                   .groupby('auId')['category'].first())

    def _status_group(au_id):
        if au_id not in status_2022.index:
            return 'removed'
        cat = status_2022[au_id]
        return 'cat2' if cat == '2' else 'cat3'

    # Last cycle each AU appeared as impaired
    last_listed = (df_imp[df_imp['auId'].isin(delisted_aus)]
                   .groupby('auId')['reportingCycle'].max()
                   .rename('Last Listed'))
    # Causes from the earliest cycle
    causes_earliest = (df[(df['reportingCycle'] == earliest_cycle) &
                          (df['auId'].isin(delisted_aus)) &
                          df['cause'].notna()]
                       .groupby('auId')['cause']
                       .apply(lambda x: '; '.join(sorted(set(x))))
                       .rename('Causes'))

    base_df = (df_imp[(df_imp['reportingCycle'] == earliest_cycle) &
                      (df_imp['auId'].isin(delisted_aus))]
               .drop_duplicates(subset=['auId'])
               [['auId', 'waterbody', 'watershed', 'waterType', 'auSize', 'sizeUnit']]
               .set_index('auId')
               .join(last_listed)
               .join(causes_earliest)
               .reset_index())
    base_df['_group'] = base_df['auId'].map(_status_group)
    base_df['Size'] = base_df['auSize'].round(1)
    base_df['Last Listed'] = base_df['Last Listed'].astype(int)
    base_df = base_df.sort_values(['watershed', 'waterbody'])
    base_df = base_df.rename(columns={
        'auId': 'Assessment Unit',
        'waterbody': 'Waterbody',
        'watershed': 'Watershed',
        'waterType': 'Type',
        'sizeUnit': 'Unit',
    })
    cols = ['Assessment Unit', 'Waterbody', 'Watershed', 'Type', 'Size', 'Unit',
            'Last Listed', 'Causes']

    groups = {'removed': 'EPA_303d_delisted_removed',
              'cat2':    'EPA_303d_delisted_cat2',
              'cat3':    'EPA_303d_delisted_cat3'}
    counts = {}
    for grp, fname in groups.items():
        sub = base_df[base_df['_group'] == grp][cols]
        sub.to_csv(f'../docs/data/{fname}.csv', index=False)
        counts[grp] = len(sub)
        print(f'  {fname}.csv: {len(sub)} rows')

    # Keep legacy file for backwards compat (all three combined)
    base_df[cols].to_csv('../docs/data/EPA_303d_delisted.csv', index=False)

    # Add group counts to facts, then write YAML
    facts['n_delisted_removed'] = counts['removed']
    facts['n_delisted_cat2'] = counts['cat2']
    facts['n_delisted_cat3'] = counts['cat3']

    with open('../docs/data/facts_EPA303d.yml', 'w') as fh:
        fh.writelines([f'{k}: {_fmt(k, v)}\n' for k, v in facts.items()])
    print('Facts written to ../docs/data/facts_EPA303d.yml')

    print(f'Dashboard charts written (prefix={prefix!r}).')


def generate_post_charts(engine):
    """Generate analysis-post charts (no prefix, local run only).

    Includes folium map (requires folium) and additional analytical charts.
    Excluded from CI dashboard.
    """
    import folium

    print('Loading data for post charts...')
    df = pd.read_sql_query('SELECT * FROM EPA_303d_Impairments', engine)
    mapping = pd.read_sql_query('SELECT * FROM CSO_303d_Mapping', engine)

    latest_cycle = int(df['reportingCycle'].max())
    df_imp = df[df['category'].isin(['4A', '4B', '4C', '5'])].copy()
    df_imp['waterType'] = _normalise_water_type(df_imp['waterType'])

    # ── Watershed impairment stacked bar by water type ────────────────────────
    print('Post chart: Watershed impairment (stacked by type)...')

    main_types = ['RIVER', 'FRESHWATER LAKE', 'ESTUARY', 'COASTAL', 'WETLAND']
    df_ws = df_imp[df_imp['reportingCycle'] == latest_cycle].copy()
    df_ws['waterTypeGroup'] = df_ws['waterType'].where(
        df_ws['waterType'].isin(main_types), other='OTHER'
    )

    # Watersheds with ≥ 10 impaired AUs (captures all meaningful ones, including Mystic)
    ws_counts = df_ws.groupby('watershed')['auId'].nunique().sort_values(ascending=False)
    top_ws = ws_counts[ws_counts >= 10].index.tolist()

    ws_pivot = (df_ws[df_ws['watershed'].isin(top_ws)]
                .groupby(['watershed', 'waterTypeGroup'])['auId']
                .nunique()
                .unstack(fill_value=0)
                .reindex(top_ws))

    type_order = [t for t in main_types if t in ws_pivot.columns] + \
                 [c for c in ws_pivot.columns if c not in main_types]

    mychart = chartjs.chart(
        f'MA Watersheds: Impaired Waters by Type ({latest_cycle})', 'Bar', 700, 620
    )
    mychart.set_labels(top_ws)
    for wtype in type_order:
        if wtype not in ws_pivot.columns:
            continue
        color = WATER_TYPE_COLORS.get(wtype, GREY)
        mychart.add_dataset(
            _to_float_list(ws_pivot[wtype]),
            wtype.title(),
            backgroundColor=f"'{color}'",
            stack="'type'",
        )
    mychart.set_params(
        JSinline=0,
        ylabel='Watershed',
        xlabel='Impaired assessment units',
        scaleBeginAtZero=1,
        stacked=1,
    )
    mychart.jekyll_write('../docs/_includes/charts/EPA303d_watershed_impairment.html')

    # ── Bacterial impairment source attribution ───────────────────────────────
    print('Post chart: Bacterial sources...')

    bact = df[(df['reportingCycle'] == latest_cycle) &
              (df['cause'].fillna('').str.upper().str.contains('FECAL|COLI')) &
              (df['attainment'] == 'Not Supporting') &
              (df['source'].notna())].copy()
    bact['source_norm'] = bact['source'].str.title()
    src_counts = (bact.groupby('source_norm')['auId']
                  .nunique()
                  .sort_values(ascending=False)
                  .head(10))

    mychart = chartjs.chart(
        f'Sources of Bacterial Water Impairment ({latest_cycle})', 'HorizontalBar', 700, 680
    )
    mychart.set_labels(src_counts.index.tolist())
    mychart.add_dataset(
        _to_float_list(src_counts),
        'Assessment units with fecal coliform or E. coli impairment',
        backgroundColor=f"'{RED}'",
    )
    mychart.set_params(
        JSinline=0,
        ylabel='',
        xlabel='Impaired assessment units',
        scaleBeginAtZero=1,
    )
    mychart.set_tick_wrap(23, axis='y')
    mychart.jekyll_write('../docs/_includes/charts/EPA303d_bacterial_sources.html')

    # ── CDF: bacterial impairment fraction, CSO vs. non-CSO waterways ─────────
    print('Post chart: CSO bacterial impairment CDF...')

    # Bacterial impairment fraction = bacterial-impaired AUs / assessed AUs, per waterway
    df_2022 = df[df['reportingCycle'] == latest_cycle]
    cso_wbs = set(mapping['waterbody303d'])

    assessed = (df_2022[df_2022['category'] != '3']
                .groupby('waterbody')['auId'].nunique().rename('n_assessed'))
    bact_imp = (df_2022[
        (df_2022['attainment'] == 'Not Supporting') &
        (df_2022['cause'].fillna('').str.upper().str.contains('FECAL|COLI'))
    ].groupby('waterbody')['auId'].nunique().rename('n_bact'))

    combo = pd.concat([assessed, bact_imp], axis=1)
    combo = combo[combo['n_assessed'] >= 1].copy()
    combo['n_bact'] = combo['n_bact'].fillna(0).astype(int)
    combo['frac_bact'] = combo['n_bact'] / combo['n_assessed']
    combo['has_cso'] = combo.index.isin(cso_wbs)

    cso_df = combo[combo['has_cso']].sort_values('frac_bact')
    cso_points = [
        {'fraction': row['frac_bact'],
         'name': wb,
         'n_bact': row['n_bact'],
         'n_assessed': row['n_assessed']}
        for wb, row in cso_df.iterrows()
    ]

    noncso_fracs = sorted(combo[~combo['has_cso']]['frac_bact'].tolist())

    _write_cso_cdf_html(
        '../docs/_includes/charts/EPA303d_cso_bact_cdf.html',
        cso_points,
        noncso_fracs,
    )

    # ── TMDL status map (folium) ──────────────────────────────────────────────
    print('Post chart: TMDL map...')

    df_map = (df[df['reportingCycle'] == latest_cycle]
              .groupby('auId')
              .agg(
                  waterbody=('waterbody', 'first'),
                  watershed=('watershed', 'first'),
                  waterType=('waterType', 'first'),
                  category=('category', 'first'),
                  hasTmdl=('hasTmdl', 'max'),
              )
              .reset_index())

    watershed_centroids = {
        'Blackstone': (42.085, -71.700),
        'Boston Harbor': (42.330, -71.010),
        'Buzzards Bay': (41.740, -70.820),
        'Cape Cod': (41.800, -70.300),
        'Charles': (42.180, -71.280),
        'Chicopee': (42.130, -72.540),
        'Concord': (42.460, -71.370),
        'Connecticut': (42.250, -72.610),
        'Deerfield': (42.640, -72.750),
        'French': (42.140, -71.850),
        'Hoosic': (42.700, -73.220),
        'Housatonic': (42.280, -73.310),
        'Ipswich': (42.680, -71.200),
        'Merrimack': (42.760, -71.470),
        'Mt Hope Bay': (41.730, -71.240),
        'Mystic': (42.400, -71.090),
        'Nashua': (42.590, -71.600),
        'North Coastal': (42.600, -70.860),
        'Quinebaug': (42.100, -71.980),
        'South Coastal': (41.660, -70.590),
        'Taunton': (41.900, -71.100),
        'Ten Mile': (41.980, -71.420),
        'Ware': (42.270, -72.260),
    }

    ws_summary = (df_map[df_map['category'].isin(['4A', '4B', '4C', '5'])]
                  .groupby('watershed')
                  .agg(n_impaired=('auId', 'count'), n_with_tmdl=('hasTmdl', 'sum'))
                  .reset_index())

    m = folium.Map(location=[42.15, -71.8], zoom_start=8, tiles='CartoDB positron')
    for _, row in ws_summary.iterrows():
        coords = watershed_centroids.get(row['watershed'])
        if coords is None:
            continue
        pct_tmdl = int(100 * row['n_with_tmdl'] / row['n_impaired']) if row['n_impaired'] > 0 else 0
        color = 'green' if pct_tmdl >= 50 else ('orange' if pct_tmdl >= 25 else 'red')
        folium.CircleMarker(
            location=coords,
            radius=max(6, min(22, row['n_impaired'] / 5)),
            color=color, fill=True, fill_color=color, fill_opacity=0.6,
            popup=folium.Popup(
                f"<b>{row['watershed']}</b><br>"
                f"Impaired AUs: {int(row['n_impaired'])}<br>"
                f"With TMDL: {int(row['n_with_tmdl'])} ({pct_tmdl}%)",
                max_width=200,
            ),
            tooltip=row['watershed'],
        ).add_to(m)

    m.save('../docs/assets/maps/EPA303d_tmdl_map.html')
    print('Map saved.')

    # ── Bacterial impairment rate by pollution source category ────────────────
    print('Post chart: Bacterial impairment by source group...')

    df_2022_src = df[df['reportingCycle'] == latest_cycle].copy()
    cso_wbs = set(mapping['waterbody303d'])

    # Classify each Not Supporting row by its dominant source type
    ns = df_2022_src[
        (df_2022_src['attainment'] == 'Not Supporting') &
        df_2022_src['source'].notna()
    ].copy()
    ns['source_up'] = ns['source'].str.upper()

    CSO_PAT    = 'COMBINED SEWER'
    MS4_PAT    = ('MUNICIPAL SEPARATE STORM|DISCHARGES FROM MUNICIPAL SEPARATE|'
                  'UNSPECIFIED URBAN|ILLICIT CONNECT|'
                  'MUNICIPAL POINT SOURCE|MUNICIPAL .URBANIZED|'
                  'WET WEATHER DISCHARGE')
    SEPTIC_PAT = 'ON-SITE TREATMENT|SEPTIC|DECENTRALIZED'
    AG_PAT     = 'AGRICULTURE|CROP|GRAZING|PASTURE|LIVESTOCK|MANURE'

    ns['src_group'] = 'Other / Unknown'
    ns.loc[ns['source_up'].str.contains(AG_PAT,     regex=True), 'src_group'] = 'Agriculture'
    ns.loc[ns['source_up'].str.contains(SEPTIC_PAT, regex=True), 'src_group'] = 'Septic / on-site systems'
    ns.loc[ns['source_up'].str.contains(MS4_PAT,    regex=True), 'src_group'] = 'MS4 / urban stormwater'
    ns.loc[ns['source_up'].str.contains(CSO_PAT,    regex=True), 'src_group'] = 'CSO / wet weather'

    # Assessed AUs per waterbody (exclude Category 3 — insufficient data)
    assessed_src = (df_2022_src[df_2022_src['category'] != '3']
                    .groupby('waterbody')['auId'].nunique())

    groups = [
        ('CSO / wet weather',        True,  None),       # only CSO waterways
        ('MS4 / urban stormwater',   False, 'MS4 / urban stormwater'),
        ('Septic / on-site systems', False, 'Septic / on-site systems'),
        ('Agriculture',              False, 'Agriculture'),
        ('Other / Unknown',          False, 'Other / Unknown'),
    ]

    labels_out, bact_rates, n_wbs_out = [], [], []
    for label, cso_only, grp_name in groups:
        if cso_only:
            wbs = list(cso_wbs)
        else:
            wbs_with_grp = ns[ns['src_group'] == grp_name]['waterbody'].unique()
            wbs = [w for w in wbs_with_grp if w not in cso_wbs]

        total_assessed = int(assessed_src[assessed_src.index.isin(wbs)].sum())
        bact_aus = int(df_2022_src[
            (df_2022_src['waterbody'].isin(wbs)) &
            (df_2022_src['category'].isin(['4A', '4B', '4C', '5'])) &
            (df_2022_src['cause'].fillna('').str.upper().str.contains('FECAL|COLI'))
        ]['auId'].nunique())

        rate = round(100.0 * bact_aus / total_assessed, 1) if total_assessed > 0 else 0.0
        labels_out.append(label)
        bact_rates.append(rate)
        n_wbs_out.append(len(wbs))
        print(f'  {label}: {len(wbs)} waterways, {bact_aus}/{total_assessed} AUs = {rate}%')

    # Colour: red for CSO, blue for MS4, shades of grey for others
    bar_colors = [
        'rgba(200,60,60,0.85)',
        'rgba(54,110,179,0.85)',
        'rgba(100,150,100,0.75)',
        'rgba(180,140,60,0.75)',
        'rgba(150,150,150,0.65)',
    ]
    colors_js = '[' + ','.join(f"'{c}'" for c in bar_colors) + ']'

    # Build labels with waterway counts
    display_labels = [
        f'{lbl} (n={n})' for lbl, n in zip(labels_out, n_wbs_out)
    ]

    mychart = chartjs.chart(
        'Bacterial Impairment Rate by Predominant Pollution Source (2022)',
        'Bar', 700, 440
    )
    mychart.set_labels(display_labels)
    mychart.add_dataset(
        [float(r) for r in bact_rates],
        '',
        backgroundColor=colors_js,
    )
    mychart.set_params(
        JSinline=0,
        ylabel='% of AUs with bacterial impairment',
        xlabel='Pollution source category',
        scaleBeginAtZero=1,
        legend=0,
    )
    mychart.jekyll_write('../docs/_includes/charts/EPA303d_bacterial_source_groups.html')

    # ── TMDL acquisition survival: 2010 Cat-5 cohort ──────────────────────────
    print('Post chart: TMDL survival (2010 Cat-5 cohort)...')

    cycles = sorted(df['reportingCycle'].unique())
    earliest_cycle = int(cycles[0])

    # AUs that were Cat 5 (no TMDL) in the earliest cycle
    cat5_earliest = set(df[(df['reportingCycle'] == earliest_cycle) &
                           (df['category'] == '5')]['auId'])
    n_cohort = len(cat5_earliest)

    # For each subsequent cycle, count how many have still never had a TMDL
    still_waiting = []
    for cyc in cycles:
        got_tmdl_by_now = df[(df['auId'].isin(cat5_earliest)) &
                             (df['reportingCycle'] <= cyc) &
                             (df['hasTmdl'] == 1)]['auId'].nunique()
        still_waiting.append(float(n_cohort - got_tmdl_by_now))

    pct_still_waiting = [round(100 * v / n_cohort, 1) for v in still_waiting]

    mychart = chartjs.chart(
        f'TMDL Progress for {earliest_cycle} Category-5 Cohort ({n_cohort} AUs)',
        'Line', 700, 400,
    )
    mychart.set_labels([str(c) for c in cycles])
    mychart.add_dataset(
        pct_still_waiting,
        f'AUs first listed Category 5 in {earliest_cycle} still without a cleanup plan',
        borderColor=f"'{RED}'",
        backgroundColor=f"'rgba(200,60,60,0.08)'",
        fill='true',
        pointRadius='5',
    )
    mychart.set_params(
        JSinline=0,
        ylabel='% still without TMDL',
        xlabel='Reporting cycle',
        scaleBeginAtZero=1,
    )
    mychart.jekyll_write('../docs/_includes/charts/EPA303d_tmdl_survival.html')
    print(f'Survival chart done: {pct_still_waiting[-1]}% still waiting by {cycles[-1]}')

    print('Post charts done.')


if __name__ == '__main__':
    engine = create_engine('sqlite:///../get_data/AMEND.db')
    generate_charts(engine, prefix='')
    generate_post_charts(engine)
