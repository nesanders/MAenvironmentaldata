"""Generate charts for the EPA 303(d) Integrated List of Waters analysis.

Produces dashboard charts (called with prefix='dash_' by dashboard_charts.py)
and analysis-post charts (called without prefix from __main__ block).

Dashboard charts (4):
  {prefix}EPA303d_impaired_trend      — Impaired AU count by cycle and water type
  {prefix}EPA303d_causes_breakdown    — Top impairment causes (most recent cycle)
  {prefix}EPA303d_cso_impaired        — Annual CSO volume by 303(d) status
  {prefix}EPA303d_tmdl_trend          — Cumulative TMDL progress by cycle

Analysis-post charts (4, no prefix):
  EPA303d_tmdl_map                   — Folium map: TMDL status of 2022 assessment units
  EPA303d_watershed_impairment       — Top watersheds by impaired AU count
  EPA303d_persistence                — Cohort chart: persistent vs. new impaired AUs
  EPA303d_bacterial_sources          — Source attribution for bacterial impairments

See docs/_posts/2026-04-11-ma-impaired-waters-303d.md for the analysis post.
"""

from __future__ import absolute_import
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import chartjs


# ─── colour palette ───────────────────────────────────────────────────────────
BLUE   = 'rgba(54, 110, 179, 0.85)'
RED    = 'rgba(200, 60, 60, 0.85)'
ORANGE = 'rgba(230, 140, 40, 0.85)'
GREEN  = 'rgba(60, 170, 80, 0.85)'
GREY   = 'rgba(150, 150, 150, 0.6)'
PURPLE = 'rgba(130, 80, 200, 0.85)'

WATER_TYPE_COLORS = {
    'RIVER':         'rgba(54, 110, 179, 0.85)',
    'FRESHWATER LAKE': 'rgba(60, 170, 80, 0.85)',
    'ESTUARY':       'rgba(230, 140, 40, 0.85)',
    'COASTAL':       'rgba(130, 80, 200, 0.85)',
    'WETLAND':       'rgba(150, 150, 150, 0.7)',
}


def _to_float_list(series):
    """Convert pandas Series / numpy array to list of Python floats for JSON safety."""
    return [float(v) if pd.notna(v) else None for v in series]


def generate_charts(engine, prefix=''):
    """Generate 303(d) impaired waters charts.

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

    # ── 1. Impaired water count trend by cycle and water type ─────────────────
    print('Chart 1: Impaired trend...')

    # Count distinct impaired AUs per cycle × waterType
    # "Impaired" = category 5 (TMDL needed) or 4A/4B/4C (TMDL exists)
    df_impaired = df[df['category'].isin(['4A', '4B', '4C', '5'])].copy()
    # Normalise FRESHWATER LAKE variants
    df_impaired['waterType'] = df_impaired['waterType'].str.strip().str.upper()
    df_impaired['waterType'] = df_impaired['waterType'].replace({
        'LAKE': 'FRESHWATER LAKE',
        'LAKE/POND': 'FRESHWATER LAKE',
        'FRESHWATER LAKE/POND': 'FRESHWATER LAKE',
    })
    main_types = ['RIVER', 'FRESHWATER LAKE', 'ESTUARY', 'COASTAL', 'WETLAND']
    df_impaired['waterTypeGroup'] = df_impaired['waterType'].where(
        df_impaired['waterType'].isin(main_types), other='OTHER'
    )

    pivot = (df_impaired
             .groupby(['reportingCycle', 'waterTypeGroup'])['auId']
             .nunique()
             .unstack(fill_value=0))

    # Keep main types in a consistent order
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
    mychart.jekyll_write(
        f'../docs/_includes/charts/{prefix}EPA303d_impaired_trend.html'
    )

    # ── 2. Top impairment causes (most recent cycle) ───────────────────────────
    print('Chart 2: Causes breakdown...')

    df_causes = (df[(df['reportingCycle'] == latest_cycle) &
                    (df['attainment'] == 'Not Supporting') &
                    (df['cause'].notna())]
                 .groupby('cause')['auId']
                 .nunique()
                 .sort_values(ascending=False)
                 .head(15))

    mychart = chartjs.chart(
        f'Top Causes of MA Water Impairment ({latest_cycle})', 'Bar', 700, 500
    )
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
    mychart.jekyll_write(
        f'../docs/_includes/charts/{prefix}EPA303d_causes_breakdown.html'
    )

    # ── 3. Annual CSO volume by 303(d) impairment status ─────────────────────
    print('Chart 3: CSO impaired...')

    # Join CSO events to 303d status via mapping table
    cso_merged = cso.merge(mapping, left_on='waterBody', right_on='csoWaterBody', how='left')

    # Get "Not Supporting" status for latest cycle
    df_latest_status = (df[df['reportingCycle'] == latest_cycle]
                        [['waterbody', 'attainment']]
                        .drop_duplicates()
                        .copy())
    # Prioritise "Not Supporting" if any AU for that waterbody is Not Supporting
    def aggregate_status(group):
        if 'Not Supporting' in group.values:
            return 'Not Supporting'
        if 'Fully Supporting' in group.values:
            return 'Fully Supporting'
        return group.iloc[0]
    status_by_wb = df_latest_status.groupby('waterbody')['attainment'].agg(aggregate_status)

    cso_merged['impairmentStatus'] = cso_merged['waterbody303d'].map(status_by_wb)
    cso_merged['impairmentStatus'] = cso_merged['impairmentStatus'].fillna('Not Matched')

    # Aggregate by year and status
    cso_merged['Year'] = pd.to_numeric(cso_merged['Year'], errors='coerce')
    cso_merged['volumnOfEvent'] = pd.to_numeric(cso_merged['volumnOfEvent'], errors='coerce').fillna(0)
    cso_g = (cso_merged
             .groupby(['Year', 'impairmentStatus'])['volumnOfEvent']
             .sum()
             .unstack(fill_value=0)
             / 1e9)  # convert gallons → billions

    cso_years = [int(y) for y in sorted(cso_g.index.dropna())]
    cso_g = cso_g.reindex(cso_years)

    status_order = ['Not Supporting', 'Fully Supporting', 'Not Matched']
    status_colors = {
        'Not Supporting': RED,
        'Fully Supporting': GREEN,
        'Not Matched': GREY,
    }

    mychart = chartjs.chart('CSO Discharge Volume by 303(d) Impairment Status', 'Bar', 700, 420)
    mychart.set_labels([str(y) for y in cso_years])
    for status in status_order:
        if status not in cso_g.columns:
            continue
        mychart.add_dataset(
            _to_float_list(cso_g[status]),
            status,
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
    mychart.jekyll_write(
        f'../docs/_includes/charts/{prefix}EPA303d_cso_impaired.html'
    )

    # ── 4. TMDL progress over cycles ─────────────────────────────────────────
    print('Chart 4: TMDL trend...')

    # Count distinct impaired AUs with TMDL (hasTmdl=1) vs. without (category 5) per cycle
    df_imp_only = df[df['category'].isin(['4A', '4B', '4C', '5'])].copy()
    tmdl_pivot = (df_imp_only
                  .groupby(['reportingCycle', 'hasTmdl'])['auId']
                  .nunique()
                  .unstack(fill_value=0))

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
    mychart.jekyll_write(
        f'../docs/_includes/charts/{prefix}EPA303d_tmdl_trend.html'
    )

    # ── 5. Facts YAML ─────────────────────────────────────────────────────────
    print('Writing facts YAML...')

    n_cycles = len(cycles)
    df_imp = df[df['category'].isin(['4A', '4B', '4C', '5'])].copy()
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
    tmdl_pivot_facts = (df_imp.groupby(['reportingCycle', 'hasTmdl'])['auId']
                        .nunique().unstack(fill_value=0))
    tmdl_with_earliest = int(tmdl_pivot_facts.get(1, pd.Series(0, index=tmdl_pivot_facts.index)).get(earliest_cycle, 0))
    tmdl_without_earliest = int(tmdl_pivot_facts.get(0, pd.Series(0, index=tmdl_pivot_facts.index)).get(earliest_cycle, 0))
    tmdl_pct_earliest = round(100 * tmdl_with_earliest / impaired_earliest, 1) if impaired_earliest > 0 else 0.0
    tmdl_with_latest = int(tmdl_pivot_facts.get(1, pd.Series(0, index=tmdl_pivot_facts.index)).get(latest_cycle, 0))
    tmdl_without_latest = int(tmdl_pivot_facts.get(0, pd.Series(0, index=tmdl_pivot_facts.index)).get(latest_cycle, 0))
    tmdl_pct_latest = round(100 * tmdl_with_latest / impaired_latest, 1) if impaired_latest > 0 else 0.0
    # Net TMDLs completed per 2-year cycle (average)
    tmdl_has_series = tmdl_pivot_facts.get(1, pd.Series(0, index=tmdl_pivot_facts.index))
    net_tmdls_per_cycle = tmdl_has_series.diff().dropna()
    avg_net_tmdl_per_cycle = int(round(float(net_tmdls_per_cycle.mean()), 0))
    # Years to clear backlog at average pace (each cycle = 2 years)
    years_to_clear_backlog = int(round(tmdl_without_latest / avg_net_tmdl_per_cycle * 2, 0)) if avg_net_tmdl_per_cycle > 0 else 9999
    year_backlog_cleared = latest_cycle + years_to_clear_backlog

    # CSO volume by 303(d) status
    cso_merged2 = cso.merge(mapping, left_on='waterBody', right_on='csoWaterBody', how='left')
    df_latest_status2 = (df[df['reportingCycle'] == latest_cycle]
                         [['waterbody', 'attainment']].drop_duplicates().copy())
    status_by_wb2 = df_latest_status2.groupby('waterbody')['attainment'].agg(aggregate_status)
    cso_merged2['impairmentStatus'] = cso_merged2['waterbody303d'].map(status_by_wb2).fillna('Not Matched')
    cso_merged2['volumnOfEvent'] = pd.to_numeric(cso_merged2['volumnOfEvent'], errors='coerce').fillna(0)

    total_by_status = cso_merged2.groupby('impairmentStatus')['volumnOfEvent'].sum()
    vol_not_supporting = float(total_by_status.get('Not Supporting', 0)) / 1e9
    vol_not_matched = float(total_by_status.get('Not Matched', 0)) / 1e9
    vol_total_matched = float(total_by_status.drop('Not Matched', errors='ignore').sum()) / 1e9
    vol_total = float(total_by_status.sum()) / 1e9
    pct_vol_impaired_of_matched = round(100 * vol_not_supporting / vol_total_matched, 1) if vol_total_matched > 0 else 0.0
    pct_vol_impaired_of_total = round(100 * vol_not_supporting / vol_total, 1) if vol_total > 0 else 0.0

    # Mapping coverage
    n_cso_mapped = int(mapping.shape[0])
    n_cso_unique_wb = cso['waterBody'].dropna().nunique()

    # ── Persistence facts ─────────────────────────────────────────────────────
    aus_earliest = set(df_imp[df_imp['reportingCycle'] == earliest_cycle]['auId'])
    aus_latest = set(df_imp[df_imp['reportingCycle'] == latest_cycle]['auId'])
    n_persistent = len(aus_earliest & aus_latest)
    n_delisted = len(aus_earliest - aus_latest)
    n_newly_added = len(aus_latest - aus_earliest)
    pct_persistent = int(round(100 * n_persistent / len(aus_earliest), 0)) if aus_earliest else 0
    pct_delisted = int(round(100 * n_delisted / len(aus_earliest), 0)) if aus_earliest else 0
    # AUs appearing in every single cycle
    au_cycle_counts = df_imp.groupby('auId')['reportingCycle'].nunique()
    n_in_all_cycles = int((au_cycle_counts == n_cycles).sum())

    # ── Size-weighted facts ───────────────────────────────────────────────────
    rivers_imp = df_imp[df_imp['waterType'] == 'RIVER'].drop_duplicates(subset=['reportingCycle', 'auId'])
    lakes_imp = (df_imp[df_imp['waterType'].str.contains('LAKE', na=False)]
                 .drop_duplicates(subset=['reportingCycle', 'auId']))
    river_miles_by_cycle = rivers_imp.groupby('reportingCycle')['auSize'].sum()
    lake_acres_by_cycle = lakes_imp.groupby('reportingCycle')['auSize'].sum()
    river_miles_earliest = int(river_miles_by_cycle[earliest_cycle].round(0))
    river_miles_latest = int(river_miles_by_cycle[latest_cycle].round(0))
    river_miles_pct_change = int(round(100 * (river_miles_latest - river_miles_earliest) / river_miles_earliest, 0))
    lake_acres_earliest = int(lake_acres_by_cycle[earliest_cycle].round(0))
    lake_acres_latest = int(lake_acres_by_cycle[latest_cycle].round(0))

    # ── Swimming use failures ─────────────────────────────────────────────────
    pcr_fail = int(df[(df['designatedUse'] == 'Primary Contact Recreation') &
                      (df['attainment'] == 'Not Supporting') &
                      (df['reportingCycle'] == latest_cycle)]['auId'].nunique())
    pcr_assessed = int(df[(df['designatedUse'] == 'Primary Contact Recreation') &
                          (df['reportingCycle'] == latest_cycle) &
                          (df['attainment'].isin(['Not Supporting', 'Fully Supporting']))
                          ]['auId'].nunique())
    pct_pcr_failing = round(100 * pcr_fail / pcr_assessed, 0) if pcr_assessed > 0 else 0

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
        'pct_pcr_failing': int(pct_pcr_failing),
    }

    facts_lines = [f'{k}: {v}\n' for k, v in facts.items()]
    with open('../docs/data/facts_EPA303d.yml', 'w') as fh:
        fh.writelines(facts_lines)
    print('Facts written to ../docs/data/facts_EPA303d.yml')

    print(f'Dashboard charts written (prefix={prefix!r}).')


def generate_post_charts(engine):
    """Generate analysis-post charts (no prefix, local run only).

    Includes a folium map and two new analytical charts:
      - EPA303d_persistence: cohort chart showing persistent vs. new impaired AUs
      - EPA303d_bacterial_sources: source attribution for bacterial impairments
    Folium map requires folium; excluded from CI dashboard.
    """
    import folium

    print('Loading data for post charts...')
    df = pd.read_sql_query('SELECT * FROM EPA_303d_Impairments', engine)
    latest_cycle = int(df['reportingCycle'].max())
    earliest_cycle = int(df['reportingCycle'].min())
    cycles = sorted(df['reportingCycle'].unique())
    df_imp = df[df['category'].isin(['4A', '4B', '4C', '5'])].copy()

    # ── Watershed impairment bar chart ────────────────────────────────────────
    print('Post chart: Watershed impairment...')

    df_ws = (df[(df['reportingCycle'] == latest_cycle) &
                (df['category'].isin(['4A', '4B', '4C', '5']))]
             .groupby('watershed')['auId']
             .nunique()
             .sort_values(ascending=False)
             .head(12))

    mychart = chartjs.chart(
        f'MA Watersheds by Impaired Water Count ({latest_cycle})', 'Bar', 700, 450
    )
    mychart.set_labels(df_ws.index.tolist())
    mychart.add_dataset(
        _to_float_list(df_ws),
        'Impaired assessment units',
        backgroundColor=f"'{BLUE}'",
    )
    mychart.set_params(
        JSinline=0,
        ylabel='Watershed',
        xlabel='Impaired assessment units',
        scaleBeginAtZero=1,
    )
    mychart.jekyll_write('../docs/_includes/charts/EPA303d_watershed_impairment.html')

    # ── Persistence of impairment (cohort chart) ──────────────────────────────
    print('Post chart: Persistence...')

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
    mychart.jekyll_write('../docs/_includes/charts/EPA303d_persistence.html')

    # ── Bacterial impairment source attribution ───────────────────────────────
    print('Post chart: Bacterial sources...')

    bact = df[(df['reportingCycle'] == latest_cycle) &
              (df['cause'].fillna('').str.upper().str.contains('FECAL|COLI')) &
              (df['attainment'] == 'Not Supporting') &
              (df['source'].notna())].copy()

    # Normalise case variations (some cycles use ALL CAPS, others Title Case)
    bact['source_norm'] = bact['source'].str.title()
    src_counts = (bact.groupby('source_norm')['auId']
                  .nunique()
                  .sort_values(ascending=False)
                  .head(10))

    mychart = chartjs.chart(
        f'Sources of Bacterial Water Impairment ({latest_cycle})', 'Bar', 700, 480
    )
    mychart.set_labels(src_counts.index.tolist())
    mychart.add_dataset(
        _to_float_list(src_counts),
        'Assessment units with fecal coliform or E. coli impairment',
        backgroundColor=f"'{RED}'",
    )
    mychart.set_params(
        JSinline=0,
        ylabel='Attributed source',
        xlabel='Impaired assessment units',
        scaleBeginAtZero=1,
    )
    mychart.jekyll_write('../docs/_includes/charts/EPA303d_bacterial_sources.html')

    # ── TMDL status map (folium) ──────────────────────────────────────────────
    print('Post chart: TMDL map...')

    # Get per-AU summary: impaired or not, has TMDL or not
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

    # We don't have lat/lon in our flat DBF data.
    # Fall back to watershed centroid approach: use the CSO_WatershedMapping
    # to place a marker per watershed with aggregate counts.
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
                  .agg(
                      n_impaired=('auId', 'count'),
                      n_with_tmdl=('hasTmdl', 'sum'),
                  )
                  .reset_index())

    m = folium.Map(location=[42.15, -71.8], zoom_start=8,
                   tiles='CartoDB positron')

    for _, row in ws_summary.iterrows():
        coords = watershed_centroids.get(row['watershed'])
        if coords is None:
            continue
        pct_tmdl = int(100 * row['n_with_tmdl'] / row['n_impaired']) if row['n_impaired'] > 0 else 0
        color = 'green' if pct_tmdl >= 50 else ('orange' if pct_tmdl >= 25 else 'red')
        folium.CircleMarker(
            location=coords,
            radius=max(6, min(22, row['n_impaired'] / 5)),
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.6,
            popup=folium.Popup(
                f"<b>{row['watershed']}</b><br>"
                f"Impaired AUs: {int(row['n_impaired'])}<br>"
                f"With TMDL: {int(row['n_with_tmdl'])} ({pct_tmdl}%)",
                max_width=200,
            ),
            tooltip=row['watershed'],
        ).add_to(m)

    map_path = '../docs/assets/maps/EPA303d_tmdl_map.html'
    m.save(map_path)
    print(f'Map saved to {map_path}')

    print('Post charts done.')


if __name__ == '__main__':
    engine = create_engine('sqlite:///../get_data/AMEND.db')
    generate_charts(engine, prefix='')
    generate_post_charts(engine)
