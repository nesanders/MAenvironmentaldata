"""Generate charts for the MA environmental lobbying analysis.

Dashboard charts (called with prefix='dash_' by dashboard_charts.py):
  {prefix}lobbying_spend_trend      — Annual lobbying spend on environmental bills, stacked by sector
  {prefix}lobbying_top_employers    — Top 15 employer spenders in most recent complete year
  {prefix}lobbying_bill_intensity   — Unique bills lobbied per year + pass rate
  {prefix}lobbying_vs_enforcement   — Dual-axis: lobbying spend vs. enforcement action count

Analysis-post charts (no prefix, generate_post_charts):
  lobbying_spend_vs_budget          — Lobbying spend overlaid on DEP budget (dual-axis)
  lobbying_bill_pass_by_spend_tier  — Bill pass rate by lobbying intensity tier
  lobbying_spend_vs_staff           — Env lobbying spend vs. DEP FTE headcount (dual-axis)
  lobbying_env_cluster_share        — Env-bill lobbying spend by topic cluster, stacked over years
  lobbying_top_env_employers        — Top 20 employers ranked by total env-bill lobbying spend
  lobbying_env_positions            — Unique clients by Support/Oppose/Neutral position on env bills
  lobbying_env_opponents            — Top 20 clients by unique env bills opposed (all years)
  lobbying_pass_by_position         — Env bill pass rate by dominant lobbying position
  lobbying_env_score_vs_clients     — Scatter: env score vs. lobbying intensity, env + top-500 non-env
  lobbying_cso_operators            — Lobbying spend by known CSO operators (permittees), by year

Data files written:
  docs/data/facts_lobbying.yml      — Key facts for Jekyll post templates
"""

import sys
import os
from pathlib import Path
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


def _load_data(engine):
    """Load lobbying/legislature tables from DB. Returns empty DataFrames if not yet populated."""
    def _safe_read(query):
        try:
            return pd.read_sql_query(query, engine)
        except Exception:
            return pd.DataFrame()

    employers = _safe_read('SELECT * FROM MA_Lobbying_Employers')
    lobby_bills = _safe_read('SELECT * FROM MA_Lobbying_Bills')
    # MA_Lobbying_Bills_Scored: is_environmental, env_relevance_score, cluster_id
    # MA_Legislature_Bills: passed status
    scored = _safe_read('SELECT * FROM MA_Lobbying_Bills_Scored')
    leg_bills_raw = _safe_read(
        'SELECT bill_number, general_court, passed FROM MA_Legislature_Bills'
    )
    if not scored.empty and not leg_bills_raw.empty:
        leg_bills = scored.merge(leg_bills_raw, on=['bill_number', 'general_court'], how='left')
    elif not scored.empty:
        leg_bills = scored
    else:
        leg_bills = pd.DataFrame()
    return employers, lobby_bills, leg_bills


def _env_bills(lobby_bills: pd.DataFrame, leg_bills: pd.DataFrame) -> pd.DataFrame:
    """Return lobby_bills rows joined to environmentally relevant bills."""
    if leg_bills.empty or lobby_bills.empty or 'is_environmental' not in leg_bills.columns:
        return pd.DataFrame()
    env = leg_bills[leg_bills['is_environmental'] == 1][
        ['bill_number', 'general_court', 'passed']
    ].copy()
    return lobby_bills.merge(env, on=['bill_number', 'general_court'], how='inner')


def _annual_env_spend(employers: pd.DataFrame, lobby_bills: pd.DataFrame,
                      leg_bills: pd.DataFrame) -> pd.DataFrame:
    """Annual lobbying spend allocated to environmental bills (proportional).

    For each (entity, client, year) row in MA_Lobbying_Employers, computes
    env_spend = compensation × (n_env_bills / n_all_bills) where both bill
    counts are for that (entity, client, year) triple. Sums across all pairs
    per year.

    Proportional allocation avoids inflating spend for clients who lobbied a
    single env bill alongside hundreds of unrelated bills.

    Falls back to total env-client spend (non-proportional) if lobby_bills
    has no year-level bill counts — but this should not occur in normal use.

    Excludes the legacy 'Total salaries received' aggregate rows.
    """
    if employers.empty or lobby_bills.empty:
        return pd.DataFrame()
    env_lb = _env_bills(lobby_bills, leg_bills)
    if env_lb.empty:
        # No env scoring yet — fall back to total spend for clients with any bills
        env_pairs = lobby_bills[['client_name', 'year']].drop_duplicates()
        emp = employers[employers['client_name'] != 'Total salaries received']
        merged = emp.merge(env_pairs, on=['client_name', 'year'], how='inner')
        return (
            merged.groupby('year')['compensation']
            .sum()
            .reset_index()
            .sort_values('year')
        )

    pair_keys = ['entity_name', 'client_name', 'year']
    # Count env bills per (firm, client, year)
    env_counts = (
        env_lb.groupby(pair_keys)['bill_number'].nunique()
        .reset_index(name='n_env')
    )
    # Count all bills per (firm, client, year)
    all_counts = (
        lobby_bills.groupby(pair_keys)['bill_number'].nunique()
        .reset_index(name='n_all')
    )
    fracs = env_counts.merge(all_counts, on=pair_keys, how='left')
    fracs['env_frac'] = fracs['n_env'] / fracs['n_all'].replace(0, np.nan)

    emp = employers[employers['client_name'] != 'Total salaries received']
    merged = emp.merge(fracs, on=pair_keys, how='inner')
    merged['env_spend'] = merged['compensation'] * merged['env_frac'].fillna(0)
    return (
        merged.groupby('year')['env_spend']
        .sum()
        .reset_index()
        .rename(columns={'env_spend': 'compensation'})
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
    employers, lobby_bills, leg_bills = _load_data(engine)

    if employers.empty:
        print('MA lobbying data not yet available — skipping lobbying charts.')
        return

    employers['year'] = pd.to_numeric(employers['year'], errors='coerce').astype('Int64')
    if not lobby_bills.empty:
        lobby_bills['year'] = pd.to_numeric(lobby_bills['year'], errors='coerce').astype('Int64')

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

    # Aggregate by client (paying entity), not by lobbying firm
    emp_year = employers[
        (employers['year'] == most_recent_year)
        & (employers['client_name'] != 'Total salaries received')
    ]
    top_employers = (
        emp_year.groupby('client_name')['compensation'].sum()
        .nlargest(15)
        .sort_values()  # ascending for horizontal bar
        .reset_index()
    )

    if not top_employers.empty:
        c = chartjs.Chart(
            f'Top 15 MA Lobbying Clients — {most_recent_year}',
            'HorizontalBar', width=700, height=440,
        )
        c.set_labels(top_employers['client_name'].tolist())
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
    _chart_spend_by_cluster(engine, employers, lobby_bills, prefix)

    _write_facts(employers, spend_trend, most_recent_year)


def _chart_spend_by_cluster(engine, employers: pd.DataFrame, lobby_bills: pd.DataFrame, prefix: str):
    """Stacked bar: annual employer spend broken down by bill topic cluster."""
    try:
        scored = pd.read_sql_query(
            'SELECT bill_number, general_court, cluster_id FROM MA_Lobbying_Bills_Scored '
            'WHERE cluster_id IS NOT NULL AND cluster_id != -1',
            engine,
        )
        cluster_labels = pd.read_sql_query(
            'SELECT cluster_id, label FROM MA_Bill_Cluster_Labels', engine,
        )
    except Exception:
        print('  Cluster data not yet in DB — skipping cluster spend chart.')
        return

    if scored.empty:
        print('  Cluster IDs not yet assigned — skipping cluster spend chart.')
        return

    # Join cluster_id onto lobby_bills via bill_number + general_court
    lb = lobby_bills.merge(
        scored[['bill_number', 'general_court', 'cluster_id']],
        on=['bill_number', 'general_court'], how='left'
    )
    lb = lb.dropna(subset=['cluster_id'])
    lb['cluster_id'] = lb['cluster_id'].astype(int)

    # Join client compensation: match (entity_name, client_name, year)
    emp = employers[employers['client_name'] != 'Total salaries received']
    lb_emp = lb.merge(emp[['entity_name', 'client_name', 'year', 'compensation']],
                      on=['entity_name', 'client_name', 'year'], how='left')

    # Annual spend per cluster (divide compensation equally across clusters
    # lobbied by each (firm, client) pair in that year to avoid double-counting)
    clusters_per_pair_year = (
        lb_emp.groupby(['entity_name', 'client_name', 'year'])['cluster_id']
        .nunique()
        .reset_index(name='n_clusters')
    )
    lb_emp = lb_emp.merge(clusters_per_pair_year,
                          on=['entity_name', 'client_name', 'year'])
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
    employers, lobby_bills, leg_bills = _load_data(engine)

    if employers.empty:
        print('MA lobbying data not yet available — skipping post charts.')
        return

    employers['year'] = pd.to_numeric(employers['year'], errors='coerce').astype('Int64')

    # ── Post chart 1: Lobbying spend vs. DEP budget ───────────────────────────
    try:
        budget = pd.read_sql_query(
            'SELECT Year, DEPAdministration_inf FROM MassBudget_summary', engine
        )
        budget['Year'] = pd.to_numeric(budget['Year'], errors='coerce').astype('Int64')
    except Exception as e:
        print(f'  Budget query failed: {e}')
        budget = pd.DataFrame()

    spend_trend = _annual_env_spend(employers, lobby_bills, leg_bills)

    if not spend_trend.empty and not budget.empty:
        merged = spend_trend.merge(budget, left_on='year', right_on='Year', how='inner')
        merged = merged.sort_values('year')
        years_sb = merged['year'].astype(int).tolist()
        spend_m = (merged['compensation'] / 1e6).tolist()
        budget_m = (merged['DEPAdministration_inf'].astype(float) / 1e6).tolist()

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
                env_lb.groupby(['bill_number', 'general_court'])['client_name']
                .nunique()
                .reset_index(name='employer_count')
            )
            bill_info = leg_bills[['bill_number', 'general_court', 'passed']].drop_duplicates()
            tc = employer_counts.merge(bill_info, on=['bill_number', 'general_court'], how='left')

            def _tier(n):
                if n >= 10:
                    return '10+ clients'
                elif n >= 3:
                    return '3–9 clients'
                else:
                    return '1–2 clients'

            tc['tier'] = tc['employer_count'].apply(_tier)
            tier_order = ['1–2 clients', '3–9 clients', '10+ clients']
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

    # ── Post chart 3: Lobbying spend vs. DEP FTE headcount ────────────────────
    try:
        staff = pd.read_sql_query(
            "SELECT year, COUNT(*) AS n_fte FROM MADEP_staff_Comptroller "
            "WHERE pay_total_actual > 0 GROUP BY year", engine
        )
        staff['year'] = pd.to_numeric(staff['year'], errors='coerce').astype('Int64')
    except Exception:
        staff = pd.DataFrame()

    if not spend_trend.empty and not staff.empty:
        merged = spend_trend.merge(staff, on='year', how='inner').sort_values('year')
        if not merged.empty:
            years_s = merged['year'].astype(int).tolist()
            spend_m = (merged['compensation'] / 1e6).tolist()
            fte = merged['n_fte'].astype(int).tolist()

            c = chartjs.Chart(
                'Environmental Lobbying Spend vs. DEP Staff Headcount',
                'Bar', width=700, height=400,
            )
            c.set_labels([str(y) for y in years_s])
            c.add_dataset(spend_m, 'Industry lobbying spend ($M)',
                          backgroundColor=f"'{ORANGE}'", yAxisID="'y'")
            c.add_dataset(fte, 'DEP staff (FTE)',
                          backgroundColor=f"'{BLUE}'", type="'line'", yAxisID="'y1'")
            c.set_params(
                js_inline=False,
                ylabel='Lobbying spend ($M)',
                xlabel='Year',
                y2nd=1,
                y2nd_title='DEP staff (FTE)',
            )
            c.jekyll_write(f'{CHART_DIR}/{prefix}lobbying_spend_vs_staff.html')
            print(f'Wrote {prefix}lobbying_spend_vs_staff.html')

    # ── Post chart 4: Env-bill lobbying spend by topic cluster, stacked ───────
    # Joins employers→lobby_bills→scored→cluster_labels.
    if (not employers.empty and not lobby_bills.empty
            and 'cluster_id' in leg_bills.columns):
        try:
            cluster_labels = pd.read_sql_query(
                'SELECT cluster_id, label FROM MA_Bill_Cluster_Labels', engine
            )
        except Exception:
            cluster_labels = pd.DataFrame()

        if not cluster_labels.empty and 'cluster_id' in cluster_labels.columns:
            cluster_labels['cluster_id'] = pd.to_numeric(
                cluster_labels['cluster_id'], errors='coerce'
            ).astype('Int64')

        env_lb = _env_bills(lobby_bills, leg_bills)
        if not env_lb.empty and not cluster_labels.empty:
            # Attach cluster_id to each env lobby_bills row
            scored_cluster = leg_bills[['bill_number', 'general_court', 'cluster_id']]
            env_lb_c = env_lb.merge(
                scored_cluster, on=['bill_number', 'general_court'], how='left'
            )
            # Allocate (firm, client) compensation equally across env bills they
            # lobbied that year, then sum by (year, cluster_id).
            pair_year_bills = (
                env_lb_c.groupby(['entity_name', 'client_name', 'year'])
                .size().reset_index(name='n_env_bills')
            )
            emp = employers[employers['client_name'] != 'Total salaries received']
            emp_join = emp.merge(
                pair_year_bills, on=['entity_name', 'client_name', 'year'], how='inner'
            )
            emp_join['per_bill'] = emp_join['compensation'] / emp_join['n_env_bills']
            cluster_spend = env_lb_c.merge(
                emp_join[['entity_name', 'client_name', 'year', 'per_bill']],
                on=['entity_name', 'client_name', 'year'], how='left'
            ).dropna(subset=['cluster_id', 'per_bill'])
            cluster_spend['cluster_id'] = cluster_spend['cluster_id'].astype(int)
            agg = (
                cluster_spend.groupby(['year', 'cluster_id'])['per_bill']
                .sum().reset_index()
            )
            agg = agg.merge(cluster_labels, on='cluster_id', how='left')
            pivot = agg.pivot_table(
                index='year', columns='label', values='per_bill', aggfunc='sum'
            ).fillna(0).sort_index()
            # Keep top 8 clusters by total spend, group rest into "Other"
            totals = pivot.sum(axis=0).sort_values(ascending=False)
            top = totals.head(8).index.tolist()
            other_cols = [c for c in pivot.columns if c not in top]
            if other_cols:
                pivot['Other'] = pivot[other_cols].sum(axis=1)
                pivot = pivot[top + ['Other']]
            else:
                pivot = pivot[top]

            years = pivot.index.astype(int).tolist()
            c = chartjs.Chart(
                'Environmental Lobbying Spend by Topic Cluster',
                'Bar', width=750, height=420,
            )
            c.set_labels([str(y) for y in years])
            for i, col in enumerate(pivot.columns):
                color = SECTOR_COLORS[i % len(SECTOR_COLORS)]
                c.add_dataset(
                    (pivot[col] / 1e6).tolist(), col,
                    backgroundColor=f"'{color}'", stack="'a'",
                )
            c.set_params(
                js_inline=False,
                ylabel='Allocated spend ($M)',
                xlabel='Year',
                stacked=1,
            )
            c.jekyll_write(f'{CHART_DIR}/{prefix}lobbying_env_cluster_share.html')
            print(f'Wrote {prefix}lobbying_env_cluster_share.html')

    # ── Post chart 5: Top clients by cumulative environmental lobbying spend ──
    if not employers.empty and not lobby_bills.empty:
        env_lb = _env_bills(lobby_bills, leg_bills)
        if not env_lb.empty:
            # Per (firm, client, year): env share = env bills / total bills lobbied
            pair_keys = ['entity_name', 'client_name', 'year']
            bill_counts = (
                lobby_bills.groupby(pair_keys).size()
                .reset_index(name='n_all')
            )
            env_counts = (
                env_lb.groupby(pair_keys).size()
                .reset_index(name='n_env')
            )
            shares = bill_counts.merge(env_counts, on=pair_keys, how='left')
            shares['n_env'] = shares['n_env'].fillna(0)
            shares['env_share'] = shares['n_env'] / shares['n_all'].replace(0, np.nan)
            emp = employers[employers['client_name'] != 'Total salaries received']
            pair_year = emp.merge(shares, on=pair_keys, how='inner')
            pair_year['env_spend'] = pair_year['compensation'] * pair_year['env_share']
            top_clients = (
                pair_year.groupby('client_name')['env_spend']
                .sum().sort_values(ascending=False).head(20)
            )
            if not top_clients.empty:
                # Reverse so largest is at top in horizontal bar (ascending order)
                top_clients = top_clients.sort_values()
                c = chartjs.Chart(
                    'Top 20 Clients by Cumulative Environmental Lobbying Spend',
                    'HorizontalBar', width=750, height=520,
                )
                c.set_labels(top_clients.index.tolist())
                c.add_dataset(
                    (top_clients.values / 1e6).tolist(),
                    'Total env-bill spend ($M, all years)',
                    backgroundColor=f"'{GREEN}'",
                )
                c.set_params(
                    js_inline=False,
                    ylabel='',
                    xlabel='Cumulative env-bill spend ($M)',
                )
                c.jekyll_write(f'{CHART_DIR}/{prefix}lobbying_top_env_employers.html')
                print(f'Wrote {prefix}lobbying_top_env_employers.html')

    # ── Post chart 6: Support/Oppose/Neutral trend on env bills ──────────────
    _chart_env_position_trend(lobby_bills, leg_bills, prefix)

    # ── Post chart 7: Top opponents of env bills ──────────────────────────────
    _chart_top_env_opponents(lobby_bills, leg_bills, prefix)

    # ── Post chart 8: Env bill pass rate by dominant lobbying position ────────
    _chart_pass_rate_by_position(lobby_bills, leg_bills, prefix)

    # ── Post chart 9: Env score vs. lobbying intensity scatter ───────────────
    _chart_env_score_vs_clients(engine, prefix)

    # ── Post charts 11–15: LLM-based new analysis charts ─────────────────────
    parquet_df = _load_parquet_llm()
    _chart_env_categories_by_gc(parquet_df, prefix)
    _chart_gc_trend(parquet_df, lobby_bills, prefix)
    _chart_employer_env_scatter(parquet_df, lobby_bills, employers, prefix)
    _chart_opposition_pairs(parquet_df, lobby_bills, prefix)
    _chart_top_env_tags(parquet_df, prefix)

    # ── Post chart 10: Lobbying spend by known CSO operators + proxies ────────
    # Cross-references MA_Lobbying_Employers.client_name with MAEEADP_CSO.permiteeName.
    # Includes the Massachusetts Municipal Association as a proxy: it is the
    # primary lobbyist for municipal CSO operators (most cities/towns lobby
    # through MMA rather than directly).
    try:
        cso_permittees = pd.read_sql_query(
            'SELECT DISTINCT permiteeName FROM MAEEADP_CSO WHERE permiteeName IS NOT NULL',
            engine,
        )
    except Exception:
        cso_permittees = pd.DataFrame()

    PROXY_LOBBYISTS = {
        'MASSACHUSETTS MUNICIPAL ASSOCIATION': 'Massachusetts Municipal Association (CSO proxy)',
    }

    if not employers.empty and not cso_permittees.empty:
        import re
        def _norm(s):
            # Collapse 'AND'/'&' to space, drop punctuation, collapse whitespace
            t = re.sub(r'[&]', ' ', str(s).upper())
            t = re.sub(r'\bAND\b', ' ', t)
            t = ''.join(ch if ch.isalnum() or ch == ' ' else ' ' for ch in t)
            t = re.sub(r'\s+', ' ', t).strip()
            return t

        operator_norms = {_norm(p): p for p in cso_permittees['permiteeName'].dropna()}
        operator_norms = {k: v for k, v in operator_norms.items() if len(k) > 4}

        def _match_operator(name):
            n = _norm(name)
            for proxy_norm, label in PROXY_LOBBYISTS.items():
                if proxy_norm in n:
                    return label
            for op_norm, op in operator_norms.items():
                if op_norm in n or n in op_norm:
                    return op
            return None

        emp = employers[employers['client_name'] != 'Total salaries received'].copy()
        emp['cso_operator'] = emp['client_name'].apply(_match_operator)
        cso_emp = emp.dropna(subset=['cso_operator'])
        if not cso_emp.empty:
            yearly = (
                cso_emp.groupby(['year', 'cso_operator'])['compensation']
                .sum().reset_index()
            )
            # Keep top 8 operators by total spend
            top_ops = (
                yearly.groupby('cso_operator')['compensation']
                .sum().sort_values(ascending=False).head(8).index.tolist()
            )
            yearly = yearly[yearly['cso_operator'].isin(top_ops)]
            pivot = yearly.pivot_table(
                index='year', columns='cso_operator', values='compensation', aggfunc='sum'
            ).fillna(0).sort_index()

            years = pivot.index.astype(int).tolist()
            c = chartjs.Chart(
                'Total Lobbying Spend by Known CSO Operators',
                'Bar', width=750, height=420,
            )
            c.set_labels([str(y) for y in years])
            for i, col in enumerate(pivot.columns):
                color = SECTOR_COLORS[i % len(SECTOR_COLORS)]
                c.add_dataset(
                    (pivot[col] / 1e6).tolist(), col,
                    backgroundColor=f"'{color}'", stack="'a'",
                )
            c.set_params(
                js_inline=False,
                ylabel='Annual lobbying spend ($M)',
                xlabel='Year',
                stacked=1,
            )
            c.jekyll_write(f'{CHART_DIR}/{prefix}lobbying_cso_operators.html')
            print(f'Wrote {prefix}lobbying_cso_operators.html')


def _chart_env_position_trend(lobby_bills: pd.DataFrame, leg_bills: pd.DataFrame,
                               prefix: str):
    """Stacked-area: unique clients taking Support/Oppose/Neutral positions on env bills by year.

    Note: "opposing an environmental bill" does not always mean opposing environmental
    protection — some env advocates oppose bills they consider inadequate or harmful.
    The chart shows industry engagement with env-relevant legislation, not ideology.
    """
    if lobby_bills.empty or leg_bills.empty or 'is_environmental' not in leg_bills.columns:
        return

    env_ids = leg_bills[leg_bills['is_environmental'] == 1][
        ['bill_number', 'general_court']
    ].copy()
    env_lb = lobby_bills.merge(env_ids, on=['bill_number', 'general_court'], how='inner')
    if env_lb.empty:
        return

    pos_yr = (
        env_lb[env_lb['position'].isin(['Support', 'Oppose', 'Neutral'])]
        .groupby(['year', 'position'])['client_name']
        .nunique()
        .reset_index(name='n_clients')
    )
    pivot = pos_yr.pivot_table(
        index='year', columns='position', values='n_clients', fill_value=0
    ).sort_index()
    for col in ['Support', 'Oppose', 'Neutral']:
        if col not in pivot.columns:
            pivot[col] = 0

    # Drop sparse early years (fewer than 5 total clients across positions)
    pivot = pivot[pivot[['Support', 'Oppose', 'Neutral']].sum(axis=1) >= 5]
    if pivot.empty:
        return

    years = pivot.index.astype(int).tolist()
    c = chartjs.Chart(
        'Unique Clients by Position on Environmental Bills',
        'Bar', width=700, height=380,
    )
    c.set_labels([str(y) for y in years])
    c.add_dataset(pivot['Support'].tolist(), 'Support',
                  backgroundColor=f"'{GREEN}'", stack="'pos'")
    c.add_dataset(pivot['Neutral'].tolist(), 'Neutral',
                  backgroundColor=f"'{GREY}'", stack="'pos'")
    c.add_dataset(pivot['Oppose'].tolist(), 'Oppose',
                  backgroundColor=f"'{RED}'", stack="'pos'")
    c.set_params(
        js_inline=False,
        ylabel='Unique lobbying clients',
        xlabel='Year',
        stacked=True,
    )
    c.jekyll_write(f'{CHART_DIR}/{prefix}lobbying_env_positions.html')
    print(f'Wrote {prefix}lobbying_env_positions.html')


def _chart_top_env_opponents(lobby_bills: pd.DataFrame, leg_bills: pd.DataFrame,
                              prefix: str):
    """Horizontal bar: clients ranked by unique env bills opposed (all years).

    "Opposing" an env-relevant bill can reflect either industry opposition to
    new regulation, or an env group opposing a bill it considers harmful.
    Top opponents are labelled accordingly where known.
    """
    if lobby_bills.empty or leg_bills.empty or 'is_environmental' not in leg_bills.columns:
        return

    env_ids = leg_bills[leg_bills['is_environmental'] == 1][
        ['bill_number', 'general_court']
    ].copy()
    env_lb = lobby_bills.merge(env_ids, on=['bill_number', 'general_court'], how='inner')
    if env_lb.empty:
        return

    oppose = (
        env_lb[env_lb['position'] == 'Oppose']
        .groupby('client_name')[['bill_number', 'general_court']]
        .apply(lambda g: g.drop_duplicates().shape[0])
        .reset_index(name='n_bills_opposed')
        .sort_values('n_bills_opposed', ascending=False)
        .head(20)
        .sort_values('n_bills_opposed')  # ascending for horizontal bar
    )
    if oppose.empty:
        return

    c = chartjs.Chart(
        'Top 20 Clients Opposing Environmental Bills (all years)',
        'HorizontalBar', width=750, height=520,
    )
    c.set_labels(oppose['client_name'].tolist())
    c.add_dataset(
        oppose['n_bills_opposed'].tolist(),
        'Unique env bills opposed',
        backgroundColor=f"'{RED}'",
    )
    c.set_params(
        js_inline=False,
        ylabel='',
        xlabel='Unique environmental bills opposed',
    )
    c.jekyll_write(f'{CHART_DIR}/{prefix}lobbying_env_opponents.html')
    print(f'Wrote {prefix}lobbying_env_opponents.html')


def _chart_pass_rate_by_position(lobby_bills: pd.DataFrame, leg_bills: pd.DataFrame,
                                  prefix: str):
    """Grouped bar: env bill pass rate by dominant lobbying position.

    Classifies each env bill as 'Mostly supported', 'Mostly opposed', or
    'Contested/Neutral' based on which position has the most unique clients.
    Shows pass rate and bill count per category.
    """
    if lobby_bills.empty or leg_bills.empty or 'is_environmental' not in leg_bills.columns:
        return
    if 'passed' not in leg_bills.columns:
        return

    env_scored = leg_bills[leg_bills['is_environmental'] == 1][
        ['bill_number', 'general_court', 'passed']
    ].drop_duplicates()
    if env_scored.empty:
        return

    env_lb = lobby_bills.merge(
        env_scored[['bill_number', 'general_court']],
        on=['bill_number', 'general_court'], how='inner'
    )
    pos_counts = (
        env_lb[env_lb['position'].isin(['Support', 'Oppose'])]
        .groupby(['bill_number', 'general_court', 'position'])['client_name']
        .nunique()
        .unstack(fill_value=0)
        .reset_index()
    )
    for col in ['Support', 'Oppose']:
        if col not in pos_counts.columns:
            pos_counts[col] = 0

    def _category(row):
        if row['Support'] > row['Oppose']:
            return 'Mostly supported'
        if row['Oppose'] > row['Support']:
            return 'Mostly opposed'
        return 'Contested / Neutral'

    pos_counts['category'] = pos_counts.apply(_category, axis=1)
    tc = pos_counts.merge(env_scored, on=['bill_number', 'general_court'], how='left')

    cat_order = ['Mostly supported', 'Mostly opposed', 'Contested / Neutral']
    summary = (
        tc.groupby('category')['passed']
        .agg(pass_rate='mean', n_bills='count')
        .reindex(cat_order)
        .fillna(0)
        .reset_index()
    )

    c = chartjs.Chart(
        'Environmental Bill Pass Rate by Lobbying Position',
        'Bar', width=520, height=360,
    )
    c.set_labels(cat_order)
    c.add_dataset(
        (summary['pass_rate'] * 100).round(1).tolist(),
        'Pass rate (%)',
        backgroundColor=[f"'{GREEN}'", f"'{RED}'", f"'{GREY}'"],
    )
    c.set_params(
        js_inline=False,
        ylabel='Pass rate (%)',
        xlabel='Dominant lobbying position',
    )
    c.jekyll_write(f'{CHART_DIR}/{prefix}lobbying_pass_by_position.html')
    print(f'Wrote {prefix}lobbying_pass_by_position.html')


def _chart_env_score_vs_clients(engine, prefix: str, top_n_nonenv: int = 500):
    """Scatter: environmental relevance score (x) vs. unique lobbying clients (y, log scale).

    Three groups:
      Environmental       — all env-relevant bills (green, outlined)
      Appropriations      — annual budget / line-item bills (purple); separated because
                            they attract hundreds of clients for budget reasons unrelated
                            to the bill's policy topic — they dominate the y-axis and
                            are a distinct lobbying mechanism
      Non-env policy      — top-N most-lobbied non-appropriations, non-env bills (grey)

    Y-axis is log-scaled: most bills have 1–10 clients, appropriations have 300+,
    so linear scale compresses the interesting region.
    Marginal histograms show the density distribution of each group along both axes.
    Threshold line (x = 0.05) only on main scatter and top (x) marginal.
    """
    import plotly.express as px

    try:
        scored = pd.read_sql_query(
            'SELECT bill_number, general_court, bill_id, bill_title, '
            '       env_relevance_score, is_environmental '
            'FROM MA_Lobbying_Bills_Scored',
            engine,
        )
        counts = pd.read_sql_query(
            'SELECT bill_number, general_court, '
            '       COUNT(DISTINCT client_name) AS n_clients '
            'FROM MA_Lobbying_Bills '
            'GROUP BY bill_number, general_court',
            engine,
        )
    except Exception as e:
        print(f'  env_score_vs_clients: DB query failed ({e}) — skipping')
        return

    df = scored.merge(counts, on=['bill_number', 'general_court'], how='left')
    df['n_clients'] = df['n_clients'].fillna(0).astype(int)
    df['bill_title'] = df['bill_title'].fillna('').astype(str)

    # Classify appropriations by title pattern — these are the annual budget bills
    # and their line-item amendments, which attract 100–350 clients purely because
    # they're the vehicle for all state spending decisions.
    _approp_re = (
        r'(?i)making appropriations|appropriation.*fiscal year'
        r'|line item \d|amendment.*\d{4}-\d{4}'
    )
    df['is_approp'] = df['bill_title'].str.contains(_approp_re, regex=True, na=False)

    env       = df[df['is_environmental'] == 1].copy()
    approp    = df[(df['is_environmental'] == 0) & df['is_approp']].copy()
    policy_nonenv = (
        df[(df['is_environmental'] == 0) & ~df['is_approp']]
        .nlargest(top_n_nonenv, 'n_clients')
        .copy()
    )

    def _group(row):
        if row['is_environmental'] == 1:
            return 'Environmental'
        if row['is_approp']:
            return 'Appropriations bill'
        return f'Non-env policy (top {top_n_nonenv})'

    plot_df = pd.concat([env, approp, policy_nonenv], ignore_index=True)
    plot_df['group'] = plot_df.apply(_group, axis=1)
    # log1p for y so bills with 0 clients don't vanish; displayed as n_clients
    plot_df['n_clients_log'] = np.log1p(plot_df['n_clients'])
    # Short title for hover name (shown bold at top)
    plot_df['title_short'] = plot_df['bill_title'].str.slice(0, 90)

    color_map = {
        'Environmental':                  '#2ca02c',
        'Appropriations bill':             '#9467bd',
        f'Non-env policy (top {top_n_nonenv})': '#aaaaaa',
    }

    fig = px.scatter(
        plot_df,
        x='env_relevance_score',
        y='n_clients',
        color='group',
        color_discrete_map=color_map,
        hover_name='title_short',
        hover_data={
            'title_short': False,
            'bill_title': False,
            'is_environmental': False,
            'is_approp': False,
            'group': False,
            'n_clients_log': False,
            'env_relevance_score': ':.3f',
            'n_clients': True,
            'bill_id': True,
            'general_court': True,
        },
        marginal_x='histogram',
        marginal_y='histogram',
        labels={
            'env_relevance_score': 'Environmental relevance score',
            'n_clients':           'Unique lobbying clients',
            'bill_id':             'Bill ID',
            'general_court':       'General Court',
            'group':               '',
        },
        title=(
            'Environmental Relevance vs. Lobbying Intensity<br>'
            f'<sup>All env bills · top {top_n_nonenv} non-env policy bills · '
            'appropriations bills shown separately · hover for title</sup>'
        ),
        opacity=0.72,
        width=820,
        height=620,
    )

    # Env dots: slightly larger, outlined
    fig.update_traces(
        selector=dict(type='scatter', name='Environmental'),
        marker=dict(size=8, line=dict(color='black', width=0.8)),
    )
    fig.update_traces(
        selector=dict(type='scatter', name='Appropriations bill'),
        marker=dict(size=5),
    )
    fig.update_traces(
        selector=dict(type='scatter', name=f'Non-env policy (top {top_n_nonenv})'),
        marker=dict(size=5),
    )

    # Threshold line on main scatter and top x-marginal.
    # Plain add_vline without row/col — plotly draws it at x=0.05 on each subplot's
    # own x-axis. The right marginal histogram's x-axis is in units of bill count
    # (0–300+), so x=0.05 lands at the invisible left edge there. No row/col
    # specification avoids the axis-matching infinite-loop bug in plotly express
    # marginal figures.
    fig.add_vline(
        x=0.05, line_dash='dot', line_color='#2ca02c', line_width=1.2,
        annotation_text='env threshold (0.05)',
        annotation_position='top right',
        annotation_font_size=10,
    )

    # Log scale on main scatter y-axis.
    # Must NOT use log_y=True in px.scatter — it transforms a shared axis in a
    # way that breaks marginal histogram rendering.
    # In px.scatter with marginal_x + marginal_y, yaxis is the main scatter y-axis
    # and yaxis2 (right marginal) has matches='y', so both get log together which
    # is correct: the marginal histogram's n_clients axis stays in sync.
    fig.update_layout(yaxis=dict(
        type='log',
        tickmode='array',
        tickvals=[1, 2, 5, 10, 20, 50, 100, 200, 350],
        ticktext=['1', '2', '5', '10', '20', '50', '100', '200', '350'],
    ))

    fig.update_layout(
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0),
        plot_bgcolor='#f8f8f8',
        paper_bgcolor='white',
    )

    out = Path(CHART_DIR) / f'{prefix}lobbying_env_score_vs_clients.html'
    html = fig.to_html(full_html=False, include_plotlyjs='cdn', config={'responsive': True})
    out.write_text('{% raw  %}\n' + html + '\n{% endraw %}\n', encoding='utf-8')
    print(f'Wrote {prefix}lobbying_env_score_vs_clients.html')


def _write_facts(employers: pd.DataFrame, spend_trend: pd.DataFrame, most_recent_year: int):
    facts = {}
    if not employers.empty:
        emp_year = employers[
            (employers['year'] == most_recent_year)
            & (employers['client_name'] != 'Total salaries received')
        ]
        facts['lobbying_most_recent_year'] = most_recent_year
        facts['lobbying_n_employers'] = int(emp_year['client_name'].nunique())
        facts['lobbying_n_firms'] = int(emp_year['entity_name'].nunique())
    if not spend_trend.empty:
        latest_spend = spend_trend[spend_trend['year'] == most_recent_year]['compensation']
        if not latest_spend.empty:
            facts['lobbying_total_spend_latest'] = int(latest_spend.iloc[0])

    with open(FACTS_YML, 'w') as f:
        for k, v in facts.items():
            f.write(f'{k}: {v}\n')


def _load_parquet_llm() -> pd.DataFrame:
    """Load bill parquet from local path (LLM columns: categories, tags, is_env_llm)."""
    local = Path(CHART_DIR).parent / 'data' / 'MA_bill_embeddings.parquet'
    if local.exists():
        return pd.read_parquet(local)
    # Fallback to GCS
    try:
        import gcsfs
        fs = gcsfs.GCSFileSystem()
        with fs.open('gs://openamend-data/MA_bill_embeddings.parquet', 'rb') as f:
            return pd.read_parquet(f)
    except Exception as e:
        print(f'  Parquet load failed: {e}')
        return pd.DataFrame()


def _make_env_lobby_bills(parquet_df: pd.DataFrame, lobby_bills: pd.DataFrame) -> pd.DataFrame:
    """Merge parquet LLM env flag (is_env_llm) onto lobby_bills rows."""
    if parquet_df.empty or lobby_bills.empty:
        return pd.DataFrame()
    env_ids = parquet_df[parquet_df['is_env_llm'] == True][
        ['bill_number', 'general_court']
    ].copy()
    env_ids['bill_number'] = pd.to_numeric(env_ids['bill_number'], errors='coerce').astype('Int64')
    env_ids['general_court'] = pd.to_numeric(env_ids['general_court'], errors='coerce').astype('Int64')
    lb = lobby_bills.copy()
    lb['bill_number'] = pd.to_numeric(lb['bill_number'], errors='coerce').astype('Int64')
    lb['general_court'] = pd.to_numeric(lb['general_court'], errors='coerce').astype('Int64')
    return lb.merge(env_ids, on=['bill_number', 'general_court'], how='inner')


def _chart_env_categories_by_gc(parquet_df: pd.DataFrame, prefix: str):
    """Stacked bar: env bill count by LLM category, by general court.

    Uses is_env_llm from parquet to select environmental bills.
    Each bill may belong to multiple categories (JSON list); one count
    per (bill, category) — bills counted once per unique category they appear in.
    X-axis = General Court (session), stacked by top-5 categories + 'Other'.
    """
    import json as _json

    if parquet_df.empty or 'is_env_llm' not in parquet_df.columns:
        return

    env = parquet_df[parquet_df['is_env_llm'] == True].copy()
    if env.empty:
        return

    # Explode categories
    rows = []
    for _, row in env.iterrows():
        gc = row.get('general_court')
        cats_raw = row.get('categories')
        if pd.isna(gc) or cats_raw is None:
            continue
        try:
            cats = _json.loads(cats_raw) if isinstance(cats_raw, str) else cats_raw
        except Exception:
            cats = []
        if not isinstance(cats, list) or not cats:
            cats = ['Unknown']
        gc_int = int(gc)
        # Deduplicate categories per bill
        for cat in set(cats):
            rows.append({'general_court': gc_int, 'category': cat})

    if not rows:
        return

    cat_df = pd.DataFrame(rows)

    # Top 5 categories by total count
    top_cats = (
        cat_df['category'].value_counts()
        .head(5)
        .index.tolist()
    )

    cat_df['cat_label'] = cat_df['category'].apply(
        lambda c: c if c in top_cats else 'Other'
    )

    pivot = (
        cat_df.groupby(['general_court', 'cat_label'])
        .size()
        .unstack(fill_value=0)
        .sort_index()
    )

    # Column order: top cats in size order, then Other
    ordered = [c for c in top_cats if c in pivot.columns]
    if 'Other' in pivot.columns:
        ordered.append('Other')
    pivot = pivot[ordered]

    gcs = pivot.index.tolist()
    cat_colors = [BLUE, ORANGE, GREEN, RED, PURPLE, TEAL, GREY]

    c = chartjs.Chart(
        'Environmental Bills by Topic Category and Legislative Session',
        'Bar', width=720, height=400,
    )
    c.set_labels([f'GC{gc}' for gc in gcs])
    for i, col in enumerate(pivot.columns):
        c.add_dataset(
            pivot[col].tolist(), col,
            backgroundColor=f"'{cat_colors[i % len(cat_colors)]}'",
            stack="'cat'",
        )
    c.set_params(
        js_inline=False,
        ylabel='Unique environmental bills',
        xlabel='General Court (legislative session)',
        stacked=True,
    )
    c.jekyll_write(f'{CHART_DIR}/{prefix}lobbying_env_categories_by_gc.html')
    print(f'Wrote {prefix}lobbying_env_categories_by_gc.html')


def _chart_gc_trend(parquet_df: pd.DataFrame, lobby_bills: pd.DataFrame, prefix: str):
    """Dual-line: unique env bills and unique clients per General Court.

    Uses LLM env flag from parquet for env bill identification.
    """
    env_lb = _make_env_lobby_bills(parquet_df, lobby_bills)
    if env_lb.empty:
        return

    gc_bills = (
        env_lb.groupby('general_court')['bill_number']
        .nunique()
        .reset_index(name='n_env_bills')
        .sort_values('general_court')
    )
    gc_clients = (
        env_lb.groupby('general_court')['client_name']
        .nunique()
        .reset_index(name='n_env_clients')
    )
    gc_trend = gc_bills.merge(gc_clients, on='general_court')
    gc_trend = gc_trend[gc_trend['general_court'] > 180].sort_values('general_court')

    if gc_trend.empty:
        return

    gcs = gc_trend['general_court'].astype(int).tolist()
    n_bills = gc_trend['n_env_bills'].tolist()
    n_clients = gc_trend['n_env_clients'].tolist()

    c = chartjs.Chart(
        'Environmental Lobbying Engagement by Legislative Session',
        'Bar', width=720, height=380,
    )
    c.set_labels([f'GC{g}' for g in gcs])
    c.add_dataset(n_bills, 'Unique env bills lobbied',
                  backgroundColor=f"'{TEAL}'", yAxisID="'y'")
    c.add_dataset(n_clients, 'Unique employer clients',
                  backgroundColor=f"'{ORANGE}'", type="'line'", yAxisID="'y1'")
    c.set_params(
        js_inline=False,
        ylabel='Unique environmental bills',
        xlabel='General Court (legislative session)',
        y2nd=1,
        y2nd_title='Unique employer clients',
    )
    c.jekyll_write(f'{CHART_DIR}/{prefix}lobbying_gc_trend.html')
    print(f'Wrote {prefix}lobbying_gc_trend.html')


def _chart_employer_env_scatter(parquet_df: pd.DataFrame, lobby_bills: pd.DataFrame,
                                  employers: pd.DataFrame, prefix: str,
                                  min_bills: int = 10):
    """Plotly scatter: total lobbying spend (x) vs env bill share (y) per client.

    Each point is one lobbying client (employer). Clients with fewer than
    `min_bills` total bills are excluded to remove noise from one-off filers.
    Point size scales with total env bills. Hover shows client name, totals,
    and average env fraction.
    """
    import plotly.express as px

    env_lb = _make_env_lobby_bills(parquet_df, lobby_bills)
    if env_lb.empty or employers.empty:
        return

    pair_keys = ['entity_name', 'client_name', 'year']
    lb = lobby_bills.copy()
    lb['bill_number'] = pd.to_numeric(lb['bill_number'], errors='coerce').astype('Int64')
    lb['year'] = pd.to_numeric(lb['year'], errors='coerce').astype('Int64')
    env_lb2 = env_lb.copy()
    env_lb2['year'] = pd.to_numeric(env_lb2['year'], errors='coerce').astype('Int64')

    all_counts = lb.groupby(pair_keys)['bill_number'].nunique().reset_index(name='n_all')
    env_counts = env_lb2.groupby(pair_keys)['bill_number'].nunique().reset_index(name='n_env')
    fracs = all_counts.merge(env_counts, on=pair_keys, how='left')
    fracs['n_env'] = fracs['n_env'].fillna(0)
    fracs['env_frac'] = fracs['n_env'] / fracs['n_all'].replace(0, np.nan)

    emp = employers[employers['client_name'] != 'Total salaries received'].copy()
    emp['year'] = pd.to_numeric(emp['year'], errors='coerce').astype('Int64')
    emp['compensation'] = pd.to_numeric(emp['compensation'], errors='coerce').fillna(0)

    merged = emp.merge(fracs, on=pair_keys, how='inner')
    merged['env_spend'] = merged['compensation'] * merged['env_frac'].fillna(0)

    client_stats = merged.groupby('client_name').agg(
        total_spend=('compensation', 'sum'),
        total_env_spend=('env_spend', 'sum'),
        total_bills=('n_all', 'sum'),
        total_env_bills=('n_env', 'sum'),
    ).reset_index()
    client_stats['avg_env_frac'] = (
        client_stats['total_env_bills'] / client_stats['total_bills'].replace(0, np.nan)
    )
    client_stats = client_stats[client_stats['total_bills'] >= min_bills].copy()

    if client_stats.empty:
        return

    # Classify by env fraction
    def _sector(row):
        f = row['avg_env_frac']
        if f >= 0.8:
            return 'Primarily env (≥80%)'
        elif f >= 0.4:
            return 'Mixed env (40–80%)'
        elif f >= 0.1:
            return 'Occasional env (10–40%)'
        else:
            return 'Rarely env (<10%)'

    client_stats['sector'] = client_stats.apply(_sector, axis=1)
    sector_order = [
        'Primarily env (≥80%)',
        'Mixed env (40–80%)',
        'Occasional env (10–40%)',
        'Rarely env (<10%)',
    ]
    color_map = {
        'Primarily env (≥80%)':    '#2ca02c',
        'Mixed env (40–80%)':      '#1f77b4',
        'Occasional env (10–40%)': '#ff7f0e',
        'Rarely env (<10%)':       '#aaaaaa',
    }

    client_stats['spend_k'] = (client_stats['total_spend'] / 1e3).round(1)
    client_stats['env_pct'] = (client_stats['avg_env_frac'] * 100).round(1)
    client_stats['env_bills_int'] = client_stats['total_env_bills'].astype(int)
    # Bubble size: sqrt of total env bills (capped)
    client_stats['bubble_size'] = np.sqrt(client_stats['total_env_bills'].clip(1, 200)) * 1.5

    fig = px.scatter(
        client_stats,
        x='spend_k',
        y='env_pct',
        color='sector',
        color_discrete_map=color_map,
        category_orders={'sector': sector_order},
        size='bubble_size',
        size_max=22,
        hover_name='client_name',
        hover_data={
            'client_name': False,
            'bubble_size': False,
            'sector': False,
            'spend_k': ':.0f',
            'env_pct': ':.1f',
            'env_bills_int': True,
            'total_bills': True,
        },
        labels={
            'spend_k':       'Total lobbying spend ($K, all years)',
            'env_pct':       'Share of bills that are environmental (%)',
            'env_bills_int': 'Env bills lobbied',
            'total_bills':   'Total bills lobbied',
            'sector':        '',
        },
        title=(
            'Lobbying Clients: Total Spend vs. Environmental Focus<br>'
            f'<sup>{len(client_stats):,} clients with ≥{min_bills} bills · '
            'bubble size ∝ √(env bills) · hover for details</sup>'
        ),
        opacity=0.75,
        width=820,
        height=560,
    )
    fig.update_layout(
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0),
        plot_bgcolor='#f8f8f8',
        paper_bgcolor='white',
        xaxis=dict(title='Total lobbying spend ($K, all years)'),
        yaxis=dict(title='Share of bills that are environmental (%)', range=[-2, 102]),
    )
    out = Path(CHART_DIR) / f'{prefix}lobbying_employer_env_scatter.html'
    html = fig.to_html(full_html=False, include_plotlyjs='cdn', config={'responsive': True})
    out.write_text('{% raw  %}\n' + html + '\n{% endraw %}\n', encoding='utf-8')
    print(f'Wrote {prefix}lobbying_employer_env_scatter.html')


def _chart_opposition_pairs(parquet_df: pd.DataFrame, lobby_bills: pd.DataFrame, prefix: str,
                              top_n: int = 15):
    """Horizontal bar: employer pairs most frequently on opposite sides of env bills.

    Self-joins lobby_bills on (bill_number, general_court) to find (supporter, opposer)
    pairs for environmentally-relevant bills, then counts unique bills per pair.
    """
    env_lb = _make_env_lobby_bills(parquet_df, lobby_bills)
    if env_lb.empty or 'position' not in env_lb.columns:
        return

    supporters = (
        env_lb[env_lb['position'] == 'Support']
        [['bill_number', 'general_court', 'client_name']]
        .drop_duplicates()
        .rename(columns={'client_name': 'supporter'})
    )
    opponents = (
        env_lb[env_lb['position'] == 'Oppose']
        [['bill_number', 'general_court', 'client_name']]
        .drop_duplicates()
        .rename(columns={'client_name': 'opposer'})
    )

    pairs = supporters.merge(opponents, on=['bill_number', 'general_court'])
    pairs = pairs[pairs['supporter'] != pairs['opposer']].copy()

    if pairs.empty:
        return

    # Canonical ordering: smaller string first
    pairs['a'] = pairs[['supporter', 'opposer']].min(axis=1)
    pairs['b'] = pairs[['supporter', 'opposer']].max(axis=1)

    pair_counts = (
        pairs.groupby(['a', 'b'])['bill_number']
        .nunique()
        .reset_index(name='n_bills')
        .nlargest(top_n, 'n_bills')
        .sort_values('n_bills')   # ascending for horizontal bar
    )

    if pair_counts.empty:
        return

    # Short labels: truncate to 35 chars each
    def _short(s, n=35):
        return s if len(s) <= n else s[:n - 1] + '…'

    labels = [
        f'{_short(r["a"])} vs {_short(r["b"])}'
        for _, r in pair_counts.iterrows()
    ]

    c = chartjs.Chart(
        f'Top {top_n} Most-Opposed Employer Pairs on Environmental Bills',
        'HorizontalBar', width=780, height=520,
    )
    c.set_labels(labels)
    c.add_dataset(
        pair_counts['n_bills'].tolist(),
        'Unique env bills where they opposed each other',
        backgroundColor=f"'{RED}'",
    )
    c.set_params(
        js_inline=False,
        ylabel='',
        xlabel='Unique environmental bills (as opposing parties)',
    )
    c.jekyll_write(f'{CHART_DIR}/{prefix}lobbying_opposition_pairs.html')
    print(f'Wrote {prefix}lobbying_opposition_pairs.html')


def _chart_top_env_tags(parquet_df: pd.DataFrame, prefix: str, top_n: int = 15):
    """Horizontal bar: most common LLM-assigned tags for environmental bills."""
    import json as _json
    from collections import Counter

    if parquet_df.empty or 'is_env_llm' not in parquet_df.columns:
        return

    env = parquet_df[parquet_df['is_env_llm'] == True]
    all_tags: list = []
    for t in env['tags'].dropna():
        try:
            tags = _json.loads(t) if isinstance(t, str) else t
            if isinstance(tags, list):
                all_tags.extend(tags)
        except Exception:
            pass

    if not all_tags:
        return

    tag_counts = Counter(all_tags)
    top_tags = tag_counts.most_common(top_n)
    # Reverse for ascending horizontal bar
    top_tags = list(reversed(top_tags))

    labels = [t[0] for t in top_tags]
    counts = [t[1] for t in top_tags]

    c = chartjs.Chart(
        f'Top {top_n} Tags on Environmental Bills (LLM-assigned)',
        'HorizontalBar', width=720, height=480,
    )
    c.set_labels(labels)
    c.add_dataset(counts, 'Bills with tag', backgroundColor=f"'{TEAL}'")
    c.set_params(
        js_inline=False,
        ylabel='',
        xlabel='Number of environmental bills',
    )
    c.jekyll_write(f'{CHART_DIR}/{prefix}lobbying_top_env_tags.html')
    print(f'Wrote {prefix}lobbying_top_env_tags.html')


if __name__ == '__main__':
    _db = Path(__file__).parent.parent / 'get_data' / 'AMEND.db'
    engine = create_engine(f'sqlite:///{_db}')
    generate_charts(engine, prefix='')
    generate_post_charts(engine, prefix='')
