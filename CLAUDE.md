# CLAUDE.md — Working in the AMEND Repository

## Python environment

All Python scripts run in the `amend_python` conda environment:

```bash
conda activate amend_python
```

Scripts that are part of the CI pipeline use `requirements-ci.txt` (no PySTAN, geopandas, scipy, or joblib).  The full conda env is needed to run the analysis/visualization scripts locally.

## Repository layout

```
get_data/        Data-fetch and database-assembly scripts (run these first)
docs/data/       CSV output files and Jekyll data-source pages
docs/_includes/  Generated chart HTML (Plotly/Bokeh, produced by analysis scripts)
docs/assets/     Maps, figures, PDFs
analysis/        Visualization and statistical analysis scripts
```

## Data pipeline (in order)

All fetch scripts are run from `get_data/`:

1. `get_EPARegion1_NPDES_permits.py` — EPA NPDES permit listings + PDF sync to GCS
2. `get_DEP_staff_SODA.py` — MA Comptroller payroll via SODA API (requires `SECRET_SODA_token`)
3. `get_EEA_data_portal.py` — EEA portal tables (permit, facility, inspection, enforcement, drinkingWater)
4. `get_eea_dp_cso.py` — EEA CSO discharge incidents (separate API endpoint)
5. `validate_data.py` — schema + row-count checks; writes `docs/data/data_stats.yml`
6. `assemble_db.py` — builds `AMEND.db` SQLite and uploads to `gs://openamend-data/amend.db`

Scripts that are **not** part of automated runs:
- `get_MassBudget_environmental.py` — blocked (source returns 403 as of early 2026)
- `get_DEP_staff.py`, `get_Census_*.py`, `transform_*.py` — run manually as needed

## SODA credentials

The `get_DEP_staff_SODA.py` script reads credentials from `get_data/SECRET_SODA_token` (two lines: app token, secret token).  In CI this file is written from GitHub secrets `SODA_APP_TOKEN` and `SODA_SECRET_TOKEN`.  Do not commit this file.

## GCS infrastructure

- Project: `openamend` (GCP)
- Bucket: `gs://openamend-data` — public read, stores the SQLite DB and large CSVs
- Service account key stored in GitHub secret `GCP_SA_KEY`

To update CORS on the bucket:
```bash
bash set_cors_gsutil.sh
```

## CI / GitHub Actions

`.github/workflows/update-data.yml` — runs every Monday at 06:00 UTC, or on manual dispatch.  Steps: fetch → validate → assemble DB → commit CSVs → push.  Opens a GitHub issue labeled `data-update-failure` if any step fails.

`.github/workflows/update-charts.yml` — triggers after a successful data update run.  Runs `analysis/dashboard_charts.py`, which generates 12 dashboard charts with `dash_` prefix. Uses `end_date=date.today()` for rolling CSO data window. See **Live Dashboard** section below for details.

## Known issues and workarounds

- **MassBudget (403)**: `massbudget.org` blocks the CSV endpoint with Cloudflare.  Existing CSVs from June 2023 remain in the repo.  To restore, contact MassBudget for API access or a direct data export.
- **EPA NPDES page changes**: EPA changed JSON format and column names around 2025; both handled with `isinstance` checks and fallback column detection.
- **EEA CSOAPI**: Requires `Referer` and `Origin` headers matching the portal URL; plain requests return HTTP 500.  Pagination is 1-indexed.
- **SSAWages lag**: The SSA average wage index CSV is updated manually.  `assemble_db.py` auto-extends it with zero-growth placeholder rows for any year gap.

## Local Jekyll preview

Run from the `docs/` directory in the `amend_jekyll` conda env.  Use `--host localhost` (not `0.0.0.0`) so that `site.url` resolves to `http://localhost:4000` and sidebar links work correctly in the browser:

```bash
conda activate amend_jekyll
cd docs
bundle exec jekyll serve --host localhost --port 4000 --baseurl ""
```

## Analysis scripts

PySTAN models are excluded from CI.  Run locally with the full conda env.

## Live Dashboard

The live dashboard at `/dashboard.html` auto-updates weekly via `update-charts.yml`. All dashboard chart files use a `dash_` filename prefix to prevent overwriting historical blog post charts.

### How it works

**`analysis/dashboard_charts.py`** — Master script that generates all 12 dashboard charts:
- Wraps calls to `MADEP_staff.generate_charts()`, `MADEP_enforcements_viz.generate_charts()`, and `ECOS_budgets_viz.generate_charts()` with `prefix='dash_'`
- Instantiates `CSOAnalysisEEADP` with `end_date=date.today()` for rolling CSO data window, `make_regression=False` (Stan excluded from CI), `make_maps=False` (too heavy for weekly CI)
- Calls dashboard-specific plot methods: `plot_monthly_volume_and_rainfall()`, `plot_monthly_modeled_vs_metered_fraction()`, `plot_monthly_volume_by_watershed()`, `plot_annual_volume_by_operator()`

**Three refactored analysis scripts** — Each now has a `generate_charts(engine, prefix='')` function:
- `MADEP_staff.py` — Generates 6 staffing charts
- `MADEP_enforcements_viz.py` — Generates 4 enforcement charts (uses hybrid data: `MAEEADP_Enforcement` for counts/fines 1996–2026, `MADEP_enforcement` for topic breakdown through 2017)
- `ECOS_budgets_viz.py` — Generates 3 budget comparison charts

**`docs/dashboard.md`** — Jekyll post at `/dashboard.html` that includes the 12 `dash_*.html` chart files. See file for data sources and methodology notes.

### Key implementation details

**Numpy serialization:** When passing pandas Series or numpy arrays to `chartjs.chart.add_dataset()`, always convert to a list of Python floats (not numpy types). Use:
```python
vals_list = [float(v) if pd.notna(v) else np.nan for v in vals.values]
mychart.add_dataset(vals_list, label, ...)
```
Numpy types like `np.float64(0.123)` serialize to strings in JSON, causing "np is not defined" browser errors.

**Date handling:** Use `pd.to_datetime()` when comparing Python `date` objects with pandas datetime64 values. Avoids `TypeError: ufunc 'isnan' not supported` errors.

**File protection mechanism:** Blog post charts (e.g., `MADEP_staffing_overall.html`) are never regenerated by CI — only dashboard charts with `dash_` prefix are. The `if __name__ == '__main__':` block in each refactored script calls `generate_charts(engine, prefix='')` (empty prefix), preserving original filenames for local testing. CI always uses `prefix='dash_'`.

### Data currency

| Chart | Data source | Auto-updates? | Notes |
|-------|------------|---------------|-------|
| Staffing levels | MA Comptroller SODA API | Yes | Updated Monday via data pipeline |
| Staffing vs funding | SODA + MassBudget | Partial | Staffing updates; budget data static (source blocked since 2026) |
| Seniority | SODA payroll | Yes | Data only available through 2016 from VisibleGovernment; Comptroller data doesn't include seniority calculations |
| Enforcement overall | EEA Data Portal | Yes | 1996–2026; filtered to years with budget data (2001–2024) |
| Enforcement vs funding | EEA DP + MassBudget | Partial | Enforcement updates; budget data static |
| Enforcement by topic | MADEP enforcement DB | Partial | Topic breakdown only available through 2017; dashboard notes this visibly |
| ECOS per-capita spending | ECOS budget survey | Static | Fetched manually; update frequency depends on ECOS data release schedule |
| CSO annual volume + rainfall | EEA DP CSO + NOAA ACIS | Yes | Uses `end_date=date.today()` for rolling window |
| CSO monthly counts + rainfall | EEA DP CSO + NOAA ACIS | Yes | Same as above; rainfall overlaid as line |
| CSO by operator (annual trends) | EEA DP CSO | Yes | Top 10 operators shown; updated Monday |
| CSO modeled vs metered | EEA DP CSO | Yes | Monthly CSO-Untreated (detailed), SSO aggregated annually |
| CSO by watershed | EEA DP CSO + geography lookup | Yes | Top 8 waterbodies; uses Waterbody fallback if Watershed not available |

Dashboard includes italicized notes where data is static (budget, ECOS, seniority cutoff).

### Maintenance tasks

**When data sources change:**
- If MassBudget is restored, update `MADEP_staff.py` and `MADEP_enforcements_viz.py` to fetch fresh budget data; regenerate dashboard
- If ECOS releases new data, manually fetch and run `ECOS_budgets_viz.generate_charts()` to update dashboard
- If EEA DP schema changes, test locally first, then update CI script

**When adding new dashboard charts:**
1. Add chart generation method to the appropriate analysis script (or `EEA_DP_CSO_map.py`)
2. Update `dashboard_charts.py` to call the new method with output slug `f'{PREFIX}MAEEADP_dashboard_...'`
3. Add chart include line to `docs/dashboard.md` with methodology notes
4. Test locally: `python dashboard_charts.py && cd docs && bundle exec jekyll serve --host localhost --port 4000 --baseurl ""`
