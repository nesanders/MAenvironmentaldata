"""Generate charts for the MS4 annual report compliance analysis.

Dashboard charts (called with prefix='dash_' by dashboard_charts.py):
  {prefix}MS4_compliance_trajectory  — MCM inspection counts by report year
  {prefix}MS4_idde_activity          — Illicit discharges found/eliminated by report year
  {prefix}MS4_mapping_progress       — System mapping completion distribution

Analysis-post charts (no prefix, generate_post_charts):
  MS4_tmdl_progress                  — TMDL reduction achieved vs. allocation
  MS4_mcm_effort_scatter             — MCM1 activity counts vs. municipality population
  MS4_idde_vs_cso                    — IDDE activity in CSO vs. non-CSO municipalities
  MS4_ej_idde_scatter                — IDDE screening rate vs. EJ percentile
  MS4_ej_mcm4_scatter                — MCM4 inspections per capita vs. EJ percentile

Data files written:
  docs/data/facts_MS4.yml            — Key facts for Jekyll post templates
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
from sqlalchemy import create_engine
import chartjs

# ─── colours ──────────────────────────────────────────────────────────────────
BLUE   = 'rgba(54, 110, 179, 0.85)'
RED    = 'rgba(200, 60, 60, 0.85)'
ORANGE = 'rgba(230, 140, 40, 0.85)'
GREEN  = 'rgba(60, 170, 80, 0.85)'
GREY   = 'rgba(150, 150, 150, 0.6)'
PURPLE = 'rgba(130, 80, 200, 0.85)'
TEAL   = 'rgba(30, 160, 160, 0.85)'

CHART_DIR = '../docs/_includes/charts'
FACTS_YML = '../docs/data/facts_MS4.yml'


def _year_labels(years):
    """Return string labels for each year; marks the most recent year as partial if >= 2026."""
    labels = [str(y) for y in years]
    if years and years[-1] >= 2026:
        labels[-1] += ' (partial)'
    return labels


def _load_ms4(engine):
    df = pd.read_sql_query(
        "SELECT * FROM MS4_AnnualReports WHERE extraction_confidence != 'low'",
        engine,
    )
    # Exclude non-traditional MS4s (MAR042 prefix — institutional permittees)
    df = df[~df['permit_number'].fillna('').str.startswith('MAR042')]
    df['report_year'] = pd.to_numeric(df['report_year'], errors='coerce')
    return df


def _write_facts(df, tmdl):
    n_reports = len(df)
    n_munis = df['municipality_normalized'].nunique()
    total_illicit = int(df['mcm3_illicit_found'].sum(skipna=True))
    total_eliminated = int(df['mcm3_illicit_eliminated'].sum(skipna=True))
    n_tmdl_quantitative = int(
        tmdl[tmdl['reduction_achieved_lbs_per_year'].notna()]['municipality'].nunique()
    )
    with open(FACTS_YML, 'w') as f:
        f.write(f'n_reports: {n_reports}\n')
        f.write(f'n_municipalities: {n_munis}\n')
        f.write(f'total_illicit_found: {total_illicit}\n')
        f.write(f'total_illicit_eliminated: {total_eliminated}\n')
        f.write(f'n_municipalities_tmdl_quantitative: {n_tmdl_quantitative}\n')
    print(f'Facts written to {FACTS_YML}')


# ─── Dashboard charts ─────────────────────────────────────────────────────────

def generate_charts(engine, prefix=''):
    """Generate MS4 dashboard charts.

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine
    prefix : str
        Filename prefix (e.g. 'dash_' for dashboard charts)
    """
    print('Loading MS4 data...')
    df = _load_ms4(engine)
    tmdl = pd.read_sql_query('SELECT * FROM MS4_TMDL', engine)

    _write_facts(df, tmdl)

    years = sorted(df['report_year'].dropna().astype(int).unique())
    year_labels = _year_labels(years)

    # ── 1. Participation rate: fraction of municipalities active per MCM ────────
    print('Chart 1: Participation rate...')

    n_munis_per_year = {y: df[df['report_year'] == y]['municipality_normalized'].nunique() for y in years}
    df_period = df[df['mcm3_count_type'] == 'current_period']

    participation_metrics = [
        ('MCM3 Outfall Screening',    df_period, 'mcm3_outfalls_screened'),
        ('MCM4 Construction Inspections', df,     'mcm4_sites_inspected'),
        ('MCM6 Facility Inspections', df,          'mcm6_facilities_inspected'),
    ]
    colors = [ORANGE, BLUE, GREEN]

    mychart = chartjs.chart(
        'MS4 MCM Participation Rate by Report Year (% of Municipalities Reporting Activity)',
        'Line', 700, 380,
    )
    mychart.set_labels(year_labels)

    for (label, src, col), color in zip(participation_metrics, colors):
        vals = [
            round(100 * (src[(src['report_year'] == y) & (src[col].fillna(0) > 0)]
                         ['municipality_normalized'].nunique()) / max(n_munis_per_year[y], 1), 1)
            for y in years
        ]
        mychart.add_dataset(
            vals, label,
            borderColor=f"'{color}'",
            backgroundColor=f"'{color}'",
            fill="false",
            tension=0.3,
        )

    mychart.set_params(
        js_inline=0,
        xlabel='Report Year (FY)',
        ylabel='% of Municipalities with Non-Zero Activity',
        legend=True,
    )
    mychart.jekyll_write(f'{CHART_DIR}/{prefix}MS4_participation_rate.html')

    # ── 2. IDDE activity: illicit discharges found and eliminated ─────────────
    print('Chart 2: IDDE activity...')

    df_cp = df[df['mcm3_count_type'] == 'current_period']
    found_by_year = [
        int(df_cp[df_cp['report_year'] == y]['mcm3_illicit_found'].sum(skipna=True))
        for y in years
    ]
    elim_by_year = [
        int(df_cp[df_cp['report_year'] == y]['mcm3_illicit_eliminated'].sum(skipna=True))
        for y in years
    ]
    mychart = chartjs.chart(
        'MS4 Illicit Discharge Detection & Elimination by Report Year',
        'Bar', 700, 380,
    )
    mychart.set_labels(year_labels)
    mychart.add_dataset(found_by_year, 'Illicit Discharges Found', backgroundColor=f"'{RED}'")
    mychart.add_dataset(elim_by_year, 'Illicit Discharges Eliminated', backgroundColor=f"'{ORANGE}'")
    mychart.set_params(
        js_inline=0,
        xlabel='Report Year (FY)',
        ylabel='Total Count (all municipalities)',
        legend=True,
    )
    mychart.jekyll_write(f'{CHART_DIR}/{prefix}MS4_idde_activity.html')

    # ── 3. System mapping progress distribution ────────────────────────────────
    print('Chart 3: Mapping progress...')

    df_map = df[df['system_mapping_pct_display'].notna()].copy()
    df_map['report_year'] = df_map['report_year'].astype(int)
    df_map['pct'] = df_map['system_mapping_pct_display'].clip(upper=100)

    brackets = [
        ('0–25% mapped',          0,   25,  'rgba(200,60,60,0.8)'),
        ('25–50% mapped',         25,  50,  'rgba(230,140,40,0.8)'),
        ('50–75% mapped',         50,  75,  'rgba(255,210,60,0.8)'),
        ('75–99% mapped',         75,  100, 'rgba(120,190,90,0.8)'),
        ('Fully mapped (100%)',   100, 101, 'rgba(40,150,60,0.85)'),
    ]

    mychart = chartjs.chart(
        'MS4 Stormwater System Mapping Completion by Report Year',
        'Bar', 700, 400,
    )
    mychart.set_labels(year_labels)

    for label, lo, hi, color in brackets:
        mask = (df_map['pct'] >= lo) & (df_map['pct'] < hi)
        vals = [
            int((mask & (df_map['report_year'] == y)).sum())
            for y in years
        ]
        mychart.add_dataset(vals, label, backgroundColor=f"'{color}'")

    mychart.set_params(
        js_inline=0,
        xlabel='Report Year (FY)',
        ylabel='Number of Municipalities',
        legend=True,
        stacked=True,
    )
    mychart.jekyll_write(f'{CHART_DIR}/{prefix}MS4_mapping_progress.html')

    print('Dashboard charts done.')


# ─── Analysis-post charts ─────────────────────────────────────────────────────

def generate_post_charts(engine):
    """Generate analysis-post-only MS4 charts (TMDL, EJ, CSO cross-dataset)."""
    print('Loading MS4 data for post charts...')
    df = _load_ms4(engine)
    tmdl = pd.read_sql_query(
        "SELECT t.source_url, t.municipality, t.municipality_normalized, t.report_year, "
        "t.waterbody, t.pollutant, t.reduction_achieved_lbs_per_year, "
        "t.wasteload_allocation_lbs_per_year "
        "FROM MS4_TMDL t "
        "JOIN MS4_AnnualReports r ON t.source_url = r.source_url "
        "WHERE r.tmdl_municipality_specific = 1",
        engine,
    )
    years = sorted(df['report_year'].dropna().astype(int).unique())
    year_labels = _year_labels(years)

    # ── 4. MCM3 outfall screening rate (municipalities with both total and screened) ──
    print('Chart 4: MCM3 screening rate...')

    df_scr = df[
        df['mcm3_outfalls_total'].notna() &
        df['mcm3_outfalls_screened'].notna() &
        (df['mcm3_outfalls_total'] > 0) &
        (df['mcm3_count_type'] == 'current_period')
    ].copy()
    df_scr['screening_rate'] = (
        df_scr['mcm3_outfalls_screened'] / df_scr['mcm3_outfalls_total'] * 100
    ).clip(upper=100)

    scr_median = [round(df_scr[df_scr['report_year'] == y]['screening_rate'].median(), 1) for y in years]
    scr_p25    = [round(df_scr[df_scr['report_year'] == y]['screening_rate'].quantile(0.25), 1) for y in years]
    scr_p75    = [round(df_scr[df_scr['report_year'] == y]['screening_rate'].quantile(0.75), 1) for y in years]
    mychart = chartjs.chart(
        'MCM3 Outfall Screening Rate by Year (Municipalities Reporting Both Total and Screened)',
        'Line', 700, 380,
    )
    mychart.set_labels(year_labels)
    mychart.add_dataset(scr_p25, 'p25', borderColor=f"'{GREY}'", backgroundColor=f"'{GREY}'",
                        fill="false", tension=0.3, pointRadius=2)
    mychart.add_dataset(scr_median, 'Median', borderColor=f"'{BLUE}'", backgroundColor=f"'{BLUE}'",
                        fill="false", tension=0.3, pointRadius=5, borderWidth=3)
    mychart.add_dataset(scr_p75, 'p75', borderColor=f"'{GREY}'", backgroundColor=f"'{GREY}'",
                        fill="false", tension=0.3, pointRadius=2)
    mychart.set_params(
        js_inline=0,
        xlabel='Report Year (FY)',
        ylabel='Outfalls Screened / Total (%)',
        legend=True,
    )
    mychart.jekyll_write(f'{CHART_DIR}/MS4_mcm3_screening_rate.html')

    # ── 5. TMDL phosphorus reduction, stacked by municipality ─────────────────
    print('Chart 5: TMDL progress...')

    tmdl_q = tmdl[
        tmdl['reduction_achieved_lbs_per_year'].notna() &
        (tmdl['pollutant'] == 'Phosphorus')
    ].copy()
    tmdl_q['report_year'] = pd.to_numeric(tmdl_q['report_year'], errors='coerce')

    # Top 14 municipalities by total phosphorus reduction; rest → 'Other'
    top_munis = (
        tmdl_q.groupby('municipality_normalized')['reduction_achieved_lbs_per_year']
        .sum().nlargest(14).index.tolist()
    )
    muni_colors = [
        BLUE, RED, GREEN, ORANGE, PURPLE, TEAL,
        'rgba(180,100,40,0.85)', 'rgba(220,80,180,0.85)',
        'rgba(80,180,220,0.85)', 'rgba(100,200,100,0.85)',
        'rgba(200,160,40,0.85)', 'rgba(140,60,140,0.85)',
        'rgba(60,140,200,0.85)', 'rgba(200,100,80,0.85)',
    ]

    mychart = chartjs.chart(
        'MS4 Phosphorus TMDL Reduction Achieved by Municipality (lbs/yr)',
        'Bar', 700, 440,
    )
    mychart.set_labels(year_labels)

    for muni, color in zip(top_munis, muni_colors):
        vals = [
            tmdl_q[(tmdl_q['report_year'] == y) & (tmdl_q['municipality_normalized'] == muni)][
                'reduction_achieved_lbs_per_year'
            ].sum()
            for y in years
        ]
        label = muni.title()
        mychart.add_dataset(vals, label, backgroundColor=f"'{color}'")

    # 'Other' bar
    other_vals = [
        tmdl_q[
            (tmdl_q['report_year'] == y) &
            (~tmdl_q['municipality_normalized'].isin(top_munis))
        ]['reduction_achieved_lbs_per_year'].sum()
        for y in years
    ]
    mychart.add_dataset(other_vals, 'Other', backgroundColor=f"'{GREY}'")

    mychart.set_params(
        js_inline=0,
        xlabel='Report Year (FY)',
        ylabel='Phosphorus Reduction Achieved (lbs/yr)',
        legend=True,
        stacked=True,
    )
    mychart.jekyll_write(f'{CHART_DIR}/MS4_tmdl_progress.html')

    # ── 5. IDDE in CSO municipalities: stacked bar by municipality ────────────
    print('Chart 5: IDDE vs CSO municipalities...')

    cso_munis = set(pd.read_sql_query(
        "SELECT DISTINCT municipality FROM MAEEADP_CSO WHERE eventType LIKE 'CSO%'",
        engine,
    )['municipality'].str.upper())

    df_cp = df[df['mcm3_count_type'] == 'current_period'].copy()
    df_cp_cso = df_cp[df_cp['municipality_normalized'].isin(cso_munis)].copy()

    # Order by total illicit found descending for consistent color assignment
    cso_order = (
        df_cp_cso.groupby('municipality_normalized')['mcm3_illicit_found']
        .sum().sort_values(ascending=False).index.tolist()
    )
    cso_colors = [RED, ORANGE, BLUE, GREEN, PURPLE, TEAL,
                  'rgba(180,100,40,0.85)', 'rgba(220,80,180,0.85)',
                  'rgba(80,180,220,0.85)', 'rgba(100,200,100,0.85)',
                  'rgba(200,160,40,0.85)', 'rgba(140,60,140,0.85)']

    mychart = chartjs.chart(
        'Illicit Discharges Found in CSO Municipalities by Year',
        'Bar', 700, 400,
    )
    mychart.set_labels(year_labels)

    for muni, color in zip(cso_order, cso_colors):
        vals = [
            int(df_cp_cso[
                (df_cp_cso['report_year'] == y) &
                (df_cp_cso['municipality_normalized'] == muni)
            ]['mcm3_illicit_found'].sum(skipna=True))
            for y in years
        ]
        mychart.add_dataset(vals, muni.title(), backgroundColor=f"'{color}'")

    mychart.set_params(
        js_inline=0,
        xlabel='Report Year (FY)',
        ylabel='Illicit Discharges Found (total)',
        legend=True,
        stacked=True,
    )
    mychart.jekyll_write(f'{CHART_DIR}/MS4_idde_vs_cso.html')

    # ── 6. EJ: IDDE screening rate vs. EJ percentile ─────────────────────────
    print('Chart 6: EJ scatter...')
    _generate_ej_charts()

    print('Post charts done.')


def _generate_ej_charts():
    """EJ scatter plots placeholder — deferred until municipal-level EJ lookup is available.

    EJSCREEN data is at census block group level with CNTY_NAME (county), not municipality.
    A direct MS4 municipality → EJSCREEN join would require a pre-computed spatial lookup
    table (town polygon → block group aggregation). Flagged as future work.
    """
    print('  EJ charts: deferred — no direct municipality→EJSCREEN join available. '
          'Requires spatial aggregation of block-group data to town boundaries.')


if __name__ == '__main__':
    engine = create_engine('sqlite:///../get_data/AMEND.db')
    generate_charts(engine, prefix='')
    generate_post_charts(engine)
