"""Generate charts for the MA environmental lobbying analysis.

Dashboard charts (called with prefix='dash_' by dashboard_charts.py):
  {prefix}lobbying_spend_trend      — Annual lobbying spend on environmental bills, stacked by sector
  {prefix}lobbying_top_employers    — Top 15 employer spenders in most recent complete year
  {prefix}lobbying_bill_intensity   — Unique bills lobbied per year + pass rate
  {prefix}lobbying_vs_enforcement   — Dual-axis: lobbying spend vs. enforcement action count

Analysis-post charts (no prefix, generate_post_charts):
  lobbying_spend_vs_budget          — Lobbying spend overlaid on DEP budget (dual-axis)
  lobbying_bill_pass_by_spend_tier  — Bill pass rate by lobbying intensity tier

Data files written:
  docs/data/facts_lobbying.yml      — Key facts for Jekyll post templates
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import chartjs

BLUE   = 'rgba(54, 110, 179, 0.85)'
RED    = 'rgba(200, 60, 60, 0.85)'
ORANGE = 'rgba(230, 140, 40, 0.85)'
GREEN  = 'rgba(60, 170, 80, 0.85)'
GREY   = 'rgba(150, 150, 150, 0.6)'
PURPLE = 'rgba(130, 80, 200, 0.85)'
TEAL   = 'rgba(30, 160, 160, 0.85)'
YELLOW = 'rgba(220, 180, 0, 0.85)'

SECTOR_COLORS = [BLUE, ORANGE, GREEN, RED, PURPLE, TEAL, YELLOW, GREY]

CHART_DIR = '../docs/_includes/charts'
FACTS_YML = '../docs/data/facts_lobbying.yml'


def _load_data(engine) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load all four lobbying/legislature tables. Returns empty DataFrames if not yet populated."""
    def _safe_read(query):
        try:
            return pd.read_sql_query(query, engine)
        except Exception:
            return pd.DataFrame()

    employers = _safe_read('SELECT * FROM MA_Lobbying_Employers')
    lobbyists = _safe_read('SELECT * FROM MA_Lobbying_Lobbyists')
    lobby_bills = _safe_read('SELECT * FROM MA_Lobbying_Bills')
    leg_bills = _safe_read('SELECT * FROM MA_Legislature_Bills')
    return employers, lobbyists, lobby_bills, leg_bills


def _env_bills(lobby_bills: pd.DataFrame, leg_bills: pd.DataFrame) -> pd.DataFrame:
    """Return lobby_bills rows joined to environmentally relevant legislature bills."""
    if leg_bills.empty or lobby_bills.empty:
        return pd.DataFrame()
    env = leg_bills[leg_bills['is_environmental'] == 1][['bill_number', 'general_court',
                                                          'title', 'passed']].copy()
    return lobby_bills.merge(env, on=['bill_number', 'general_court'], how='inner')


def _annual_env_spend(employers: pd.DataFrame, lobby_bills: pd.DataFrame,
                      leg_bills: pd.DataFrame) -> pd.DataFrame:
    """Annual total employer spend for employers who lobbied at least one environmental bill."""
    if employers.empty or lobby_bills.empty:
        return pd.DataFrame()
    env_lb = _env_bills(lobby_bills, leg_bills)
    if env_lb.empty:
        # Fallback: use all bills if scoring hasn't run yet
        env_lb = lobby_bills.copy()
    env_employers = env_lb[['entity_name', 'year']].drop_duplicates()
    merged = employers.merge(env_employers, on=['entity_name', 'year'], how='inner')
    return (
        merged.groupby('year')['compensation']
        .sum()
        .reset_index()
        .sort_values('year')
    )


def generate_charts(engine, prefix=''):
    """Generate dashboard lobbying charts.

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine
    prefix : str
        Filename prefix (e.g. 'dash_' for dashboard charts).
    """
    employers, lobbyists, lobby_bills, leg_bills = _load_data(engine)

    if employers.empty:
        print('MA lobbying data not yet available — skipping lobbying charts.')
        return

    employers['year'] = pd.to_numeric(employers['year'], errors='coerce').astype('Int64')
    if not lobby_bills.empty:
        lobby_bills['year'] = pd.to_numeric(lobby_bills['year'], errors='coerce').astype('Int64')
        lobby_bills['general_court'] = pd.to_numeric(
            lobby_bills['general_court'], errors='coerce').astype('Int64')

    # ── Chart 1: Annual spend trend ───────────────────────────────────────────
    spend_trend = _annual_env_spend(employers, lobby_bills, leg_bills)

    if not spend_trend.empty:
        years = spend_trend['year'].dropna().astype(int).tolist()
        spend_m = (spend_trend['compensation'] / 1e6).tolist()

        c = chartjs.Chart(
            'Annual MA Lobbying Spend on Environmental Bills',
            'Bar', width=700, height=380,
        )
        c.set_labels([str(y) for y in years])
        c.add_dataset(spend_m, 'Total spend ($M)', backgroundColor=f"'{BLUE}'")
        c.set_params(
            js_inline=False,
            ylabel='Lobbying spend ($M)',
            xlabel='Year',
        )
        c.jekyll_write(f'{CHART_DIR}/{prefix}lobbying_spend_trend.html')
        print(f'Wrote {prefix}lobbying_spend_trend.html')

    # ── Chart 2: Top employers in most recent year ────────────────────────────
    most_recent_year = int(employers['year'].dropna().max())
    # Use second-most-recent year if most-recent looks like a partial year
    # (fewer than half the employer count of the prior year)
    year_counts = employers.groupby('year').size()
    if len(year_counts) >= 2:
        penultimate = int(sorted(year_counts.index)[-2])
        if year_counts[most_recent_year] < year_counts[penultimate] * 0.5:
            most_recent_year = penultimate

    top_employers = (
        employers[employers['year'] == most_recent_year]
        .nlargest(15, 'compensation')[['entity_name', 'compensation']]
        .sort_values('compensation')  # ascending for horizontal bar
    )

    if not top_employers.empty:
        c = chartjs.Chart(
            f'Top 15 MA Lobbying Employers — {most_recent_year}',
            'HorizontalBar', width=700, height=440,
        )
        c.set_labels(top_employers['entity_name'].tolist())
        spend_k = (top_employers['compensation'] / 1e3).tolist()
        c.add_dataset(spend_k, 'Spend ($K)', backgroundColor=f"'{ORANGE}'")
        c.set_params(js_inline=False, xlabel='Lobbying spend ($K)')
        c.jekyll_write(f'{CHART_DIR}/{prefix}lobbying_top_employers.html')
        print(f'Wrote {prefix}lobbying_top_employers.html')

    # ── Chart 3: Bill intensity — unique bills lobbied + pass rate ────────────
    if not lobby_bills.empty and not leg_bills.empty:
        env_lb = _env_bills(lobby_bills, leg_bills)
        if env_lb.empty:
            env_lb = lobby_bills.copy()
            env_lb['passed'] = np.nan

        bills_per_year = (
            env_lb.groupby('year')['bill_number']
            .nunique()
            .reset_index(name='n_bills')
            .sort_values('year')
        )
        pass_rate_per_year = (
            env_lb.drop_duplicates(subset=['bill_number', 'general_court', 'year'])
            .groupby('year')['passed']
            .mean()
            .reset_index(name='pass_rate')
        )
        bill_intensity = bills_per_year.merge(pass_rate_per_year, on='year', how='left')

        years_bi = bill_intensity['year'].dropna().astype(int).tolist()
        n_bills = bill_intensity['n_bills'].tolist()
        pass_pct = (bill_intensity['pass_rate'].fillna(0) * 100).tolist()

        c = chartjs.Chart(
            'Environmental Bills Lobbied per Year',
            'Bar', width=700, height=380,
        )
        c.set_labels([str(y) for y in years_bi])
        c.add_dataset(n_bills, 'Unique bills lobbied', backgroundColor=f"'{TEAL}'",
                      yAxisID="'y'")
        c.add_dataset(pass_pct, 'Pass rate (%)', backgroundColor=f"'{GREEN}'",
                      type="'line'", yAxisID="'y1'")
        c.set_params(
            js_inline=False,
            ylabel='Bills lobbied',
            xlabel='Year',
            y2nd=1,
            y2nd_title='Pass rate (%)',
        )
        c.jekyll_write(f'{CHART_DIR}/{prefix}lobbying_bill_intensity.html')
        print(f'Wrote {prefix}lobbying_bill_intensity.html')

    # ── Chart 4: Lobbying spend vs. enforcement count (dual-axis) ─────────────
    try:
        enf = pd.read_sql_query(
            "SELECT strftime('%Y', EnforcementDate) AS year, COUNT(*) AS n_actions "
            "FROM MAEEADP_Enforcement "
            "WHERE EnforcementType NOT IN ("
            "  'Notice Of Non-Compliance','Field Notice Of Non Compliance',"
            "  'BOIL ORDER','Federal Administrative Order Against PWS',"
            "  'Federal Notice Of Noncompliance Against PWS'"
            ") GROUP BY 1",
            engine,
        )
        enf['year'] = pd.to_numeric(enf['year'], errors='coerce').astype('Int64')
    except Exception:
        enf = pd.DataFrame()

    if not spend_trend.empty and not enf.empty:
        merged = spend_trend.merge(enf, on='year', how='inner')
        merged = merged.sort_values('year')
        years_vs = merged['year'].astype(int).tolist()
        spend_m_vs = (merged['compensation'] / 1e6).tolist()
        n_enf = merged['n_actions'].tolist()

        c = chartjs.Chart(
            'MA Lobbying Spend vs. Enforcement Actions',
            'Bar', width=700, height=380,
        )
        c.set_labels([str(y) for y in years_vs])
        c.add_dataset(spend_m_vs, 'Lobbying spend ($M)', backgroundColor=f"'{BLUE}'",
                      yAxisID="'y'")
        c.add_dataset(n_enf, 'Enforcement actions', backgroundColor=f"'{RED}'",
                      type="'line'", yAxisID="'y1'")
        c.set_params(
            js_inline=False,
            ylabel='Lobbying spend ($M)',
            xlabel='Year',
            y2nd=1,
            y2nd_title='Enforcement actions',
        )
        c.jekyll_write(f'{CHART_DIR}/{prefix}lobbying_vs_enforcement.html')
        print(f'Wrote {prefix}lobbying_vs_enforcement.html')

    # ── Chart 5: Lobbying spend by topic cluster (stacked bar by year) ───────────
    _chart_spend_by_cluster(employers, lobby_bills, prefix)

    _write_facts(employers, spend_trend, most_recent_year)


def _chart_spend_by_cluster(employers: pd.DataFrame, lobby_bills: pd.DataFrame, prefix: str):
    """Stacked bar: annual employer spend broken down by bill topic cluster.

    Requires MA_lobbying_bills_scored.csv and MA_bill_cluster_labels.csv.
    Gracefully skipped if clustering hasn't been run yet.
    """
    scored_path = '../docs/data/MA_lobbying_bills_scored.csv'
    labels_path = '../docs/data/MA_bill_cluster_labels.csv'
    try:
        scored = pd.read_csv(scored_path, index_col=0)
        cluster_labels = pd.read_csv(labels_path)
    except FileNotFoundError:
        print('  Cluster data not yet available — skipping cluster spend chart.')
        return

    if scored['cluster_id'].eq(-1).all():
        print('  Cluster IDs not yet assigned — skipping cluster spend chart.')
        return

    # Join cluster_id onto lobby_bills via bill_number + general_court
    scored['bill_number'] = pd.to_numeric(scored['bill_number'], errors='coerce')
    scored['general_court'] = pd.to_numeric(scored['general_court'], errors='coerce')
    lb = lobby_bills.merge(
        scored[['bill_number', 'general_court', 'cluster_id']],
        on=['bill_number', 'general_court'], how='left'
    )
    lb = lb.dropna(subset=['cluster_id'])
    lb['cluster_id'] = lb['cluster_id'].astype(int)

    # Join employer compensation: match entity_name + year
    lb_emp = lb.merge(employers[['entity_name', 'year', 'compensation']],
                      on=['entity_name', 'year'], how='left')

    # Annual spend per cluster (divide compensation equally across clusters
    # lobbied by each entity in that year to avoid double-counting)
    clusters_per_entity_year = (
        lb_emp.groupby(['entity_name', 'year'])['cluster_id']
        .nunique()
        .reset_index(name='n_clusters')
    )
    lb_emp = lb_emp.merge(clusters_per_entity_year, on=['entity_name', 'year'])
    lb_emp['spend_share'] = lb_emp['compensation'] / lb_emp['n_clusters']

    spend_by_cluster = (
        lb_emp.groupby(['year', 'cluster_id'])['spend_share']
        .sum()
        .reset_index()
    )

    # Build cluster label map
    label_map = dict(zip(cluster_labels['cluster_id'], cluster_labels['label']))
    spend_by_cluster['label'] = spend_by_cluster['cluster_id'].map(label_map).fillna('Other')

    years = sorted(spend_by_cluster['year'].dropna().astype(int).unique())
    # Top clusters by total spend across all years
    top_clusters = (
        spend_by_cluster.groupby('cluster_id')['spend_share']
        .sum()
        .nlargest(10)
        .index.tolist()
    )

    c = chartjs.Chart(
        'MA Lobbying Spend by Topic Cluster',
        'Bar', width=700, height=420,
    )
    c.set_labels([str(y) for y in years])

    colors = SECTOR_COLORS
    for i, cid in enumerate(top_clusters):
        subset = spend_by_cluster[spend_by_cluster['cluster_id'] == cid]
        year_spend = {int(r['year']): r['spend_share'] / 1e6
                      for _, r in subset.iterrows()}
        data = [year_spend.get(y, 0) for y in years]
        label = label_map.get(cid, f'Cluster {cid}')
        c.add_dataset(data, label,
                      backgroundColor=f"'{colors[i % len(colors)]}'",
                      stack="'topic'")

    c.set_params(
        js_inline=False,
        ylabel='Lobbying spend ($M)',
        xlabel='Year',
        stacked=True,
    )
    c.jekyll_write(f'{CHART_DIR}/{prefix}lobbying_spend_by_cluster.html')
    print(f'Wrote {prefix}lobbying_spend_by_cluster.html')


def generate_post_charts(engine, prefix=''):
    """Generate analysis-post lobbying charts (not suitable for weekly CI)."""
    employers, lobbyists, lobby_bills, leg_bills = _load_data(engine)

    if employers.empty:
        print('MA lobbying data not yet available — skipping post charts.')
        return

    employers['year'] = pd.to_numeric(employers['year'], errors='coerce').astype('Int64')

    # ── Post chart 1: Lobbying spend vs. DEP budget ───────────────────────────
    try:
        budget = pd.read_sql_query(
            'SELECT Year, DEPAdministration_inf_float FROM MassBudget_summary', engine
        )
        budget['Year'] = pd.to_numeric(budget['Year'], errors='coerce').astype('Int64')
    except Exception:
        budget = pd.DataFrame()

    spend_trend = _annual_env_spend(employers, lobby_bills, leg_bills)

    if not spend_trend.empty and not budget.empty:
        merged = spend_trend.merge(budget, left_on='year', right_on='Year', how='inner')
        merged = merged.sort_values('year')
        years_sb = merged['year'].astype(int).tolist()
        spend_m = (merged['compensation'] / 1e6).tolist()
        budget_m = (merged['DEPAdministration_inf_float'] / 1e6).tolist()

        c = chartjs.Chart(
            'MA Lobbying Spend vs. DEP Budget (inflation-adjusted)',
            'Bar', width=700, height=400,
        )
        c.set_labels([str(y) for y in years_sb])
        c.add_dataset(spend_m, 'Industry lobbying spend ($M)', backgroundColor=f"'{ORANGE}'",
                      yAxisID="'y'")
        c.add_dataset(budget_m, 'DEP admin budget ($M, inflation-adj.)',
                      backgroundColor=f"'{BLUE}'", type="'line'", yAxisID="'y1'")
        c.set_params(
            js_inline=False,
            ylabel='Lobbying spend ($M)',
            xlabel='Year',
            y2nd=1,
            y2nd_title='DEP budget ($M)',
        )
        c.jekyll_write(f'{CHART_DIR}/{prefix}lobbying_spend_vs_budget.html')
        print(f'Wrote {prefix}lobbying_spend_vs_budget.html')

    # ── Post chart 2: Bill pass rate by lobbying intensity tier ───────────────
    if not lobby_bills.empty and not leg_bills.empty:
        env_lb = _env_bills(lobby_bills, leg_bills)
        if not env_lb.empty and 'passed' in env_lb.columns:
            employer_counts = (
                env_lb.groupby(['bill_number', 'general_court'])['entity_name']
                .nunique()
                .reset_index(name='employer_count')
            )
            bill_info = leg_bills[['bill_number', 'general_court', 'passed']].drop_duplicates()
            tc = employer_counts.merge(bill_info, on=['bill_number', 'general_court'], how='left')

            def _tier(n):
                if n >= 10:
                    return '10+ employers'
                elif n >= 3:
                    return '3–9 employers'
                else:
                    return '1–2 employers'

            tc['tier'] = tc['employer_count'].apply(_tier)
            tier_order = ['1–2 employers', '3–9 employers', '10+ employers']
            summary = (
                tc.groupby('tier')['passed']
                .agg(['mean', 'count'])
                .reindex(tier_order)
                .reset_index()
            )

            c = chartjs.Chart(
                'Environmental Bill Pass Rate by Lobbying Intensity',
                'Bar', width=500, height=360,
            )
            c.set_labels(tier_order)
            c.add_dataset(
                (summary['mean'].fillna(0) * 100).tolist(),
                'Pass rate (%)',
                backgroundColor=f"'{GREEN}'",
            )
            c.set_params(js_inline=False, ylabel='Pass rate (%)', xlabel='Number of employer lobbiers')
            c.jekyll_write(f'{CHART_DIR}/{prefix}lobbying_bill_pass_by_spend_tier.html')
            print(f'Wrote {prefix}lobbying_bill_pass_by_spend_tier.html')


def _write_facts(employers: pd.DataFrame, spend_trend: pd.DataFrame, most_recent_year: int):
    facts = {}
    if not employers.empty:
        facts['lobbying_most_recent_year'] = most_recent_year
        facts['lobbying_n_employers'] = int(
            employers[employers['year'] == most_recent_year].shape[0]
        )
    if not spend_trend.empty:
        latest_spend = spend_trend[spend_trend['year'] == most_recent_year]['compensation']
        if not latest_spend.empty:
            facts['lobbying_total_spend_latest'] = int(latest_spend.iloc[0])

    with open(FACTS_YML, 'w') as f:
        for k, v in facts.items():
            f.write(f'{k}: {v}\n')


if __name__ == '__main__':
    engine = create_engine('sqlite:///AMEND.db')
    generate_charts(engine, prefix='')
    generate_post_charts(engine, prefix='')
