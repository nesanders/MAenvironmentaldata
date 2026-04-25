"""Generate dashboard-specific chart variants that update weekly with the latest data.

All charts are written with the 'dash_' filename prefix to avoid overwriting the
static chart files embedded in historical blog posts.
"""

from datetime import date
from sqlalchemy import create_engine

import MADEP_staff
import MADEP_enforcements_viz
import ECOS_budgets_viz
import EPA_303d_viz
import MS4_compliance_viz
from EEA_DP_CSO_map import CSOAnalysisEEADP

PREFIX = 'dash_'
engine = create_engine('sqlite:///../get_data/AMEND.db')

# --- Staffing charts (3 of 12) ---
MADEP_staff.generate_charts(engine, prefix=PREFIX)

# --- Enforcement charts (3 of 12) ---
MADEP_enforcements_viz.generate_charts(engine, prefix=PREFIX)

# --- Budget comparison chart (1 of 12) ---
ECOS_budgets_viz.generate_charts(engine, prefix=PREFIX)

# --- CSO discharge + EJ charts (5 of 12) ---
# Use end_date=date.today() so charts always show all available data to date.
# output_slug='MAEEADP_dashboard' writes dash_MAEEADP_dashboard_*.html files.
# make_regression=False to skip Stan (excluded from requirements-ci.txt)
# make_maps=False to skip Plotly map generation (too heavy for weekly CI)
csoa = CSOAnalysisEEADP(
    cso_data_start=date(2022, 6, 1),
    cso_data_end=date.today(),
    output_slug=f'{PREFIX}MAEEADP_dashboard',
    make_maps=False,
    make_charts=True,
    make_regression=False,
)
csoa.run_analysis()
csoa.extra_plots()

# --- Dashboard-specific CSO charts ---
# Generate charts specifically for the dashboard (not part of regular blog post pipeline)
csoa.plot_monthly_volume_and_rainfall()
csoa.plot_monthly_modeled_vs_metered_fraction()
csoa.plot_monthly_volume_by_watershed()

# Use annual operator timeseries for dashboard instead of static bar chart
csoa.plot_annual_volume_by_operator(outpath='../docs/_includes/charts/dash_MAEEADP_dashboard_volume_per_operator.html', top_n=10)

# --- 303(d) impaired waters charts (4 charts) ---
EPA_303d_viz.generate_charts(engine, prefix=PREFIX)

# --- MS4 stormwater compliance charts (3 charts) ---
MS4_compliance_viz.generate_charts(engine, prefix=PREFIX)
