# CLAUDE.md — Working in the AMEND Repository

## Python environment

All Python scripts run in the `amend_python` conda environment:

```bash
conda activate amend_python
```

Scripts that are part of the CI pipeline use `requirements-ci.txt` (no PySTAN, geopandas, or joblib; scipy is imported inline only where needed and is not listed).  The full conda env is needed to run the analysis/visualization scripts locally.

## Repository layout

```
get_data/        Data-fetch and database-assembly scripts (run these first)
docs/data/       CSV output files and Jekyll data-source pages
docs/_includes/  Generated chart HTML (Chart.js for charts, Plotly/Folium for maps)
docs/assets/     Maps, figures, PDFs
analysis/        Visualization and statistical analysis scripts
```

## Data pipeline (in order)

All fetch scripts are run from `get_data/`:

1. `get_EPARegion1_NPDES_permits.py` — EPA NPDES permit listings + PDF sync to GCS
2. `get_budget_CTHRU.py` — MA Comptroller CTHRU Socrata API (FY2005–present) + cached MassBudget (FY2001–2004); no auth required
3. `get_DEP_staff_SODA.py` — MA Comptroller payroll via SODA API (requires `SECRET_SODA_token`)
4. `get_EEA_data_portal.py` — EEA portal tables (permit, facility, inspection, enforcement, drinkingWater)
5. `get_eea_dp_cso.py` — EEA CSO discharge incidents (separate API endpoint)
5.5. `get_ATTAINS_303d.py` — EPA 303(d) impaired waters from MassGIS shapefiles (biennial data; exits early if all cycles already cached)
6. `validate_data.py` — schema + row-count checks; writes `docs/data/data_stats.yml`
7. `assemble_db.py` — builds `AMEND.db` SQLite, uploads to `gs://openamend-data/amend.db`, and regenerates `docs/assets/db_semantic_context.txt`

Scripts that are **not** part of automated runs:
- `get_SSAWages.py` — Attempts to fetch SSA Average Wage Index (currently blocked by ssa.gov 403). Cached CSV is used as fallback.
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

`.github/workflows/update-charts.yml` — triggers after a successful data update run.  Runs `analysis/dashboard_charts.py`, which generates all dashboard charts with `dash_` prefix. Uses `end_date=date.today()` for rolling CSO data window. See **Live Dashboard** section below for details.

## Known issues and workarounds

- **Budget data (CTHRU)**: MA Comptroller CTHRU Socrata API replaces MassBudget (which returned 403 Cloudflare blocks as of early 2026). CTHRU provides DEP, DCR, EEA, and Fish&Game admin budgets FY2005–present. FY2001–2004 are from cached MassBudget CSVs and do not auto-update.
- **SSAWages (403)**: The SSA website (`ssa.gov`) blocks automated access despite User-Agent headers. `get_SSAWages.py` script is created but not yet run in CI. Falls back to cached 2023-02-03 version. `assemble_db.py` auto-extends with zero-growth placeholder rows for any year gap.
- **EPA NPDES page changes**: EPA changed JSON format and column names around 2025; both handled with `isinstance` checks and fallback column detection.
- **EEA CSOAPI**: Requires `Referer` and `Origin` headers matching the portal URL; plain requests return HTTP 500.  Pagination is 1-indexed.
- **303(d) data (biennial)**: `get_ATTAINS_303d.py` fetches from MassGIS S3-hosted shapefiles (not the ATTAINS REST API, which times out on `/assessments`). Data updates only biennially (even years); the script exits early if all known cycles are already in the cached CSV. The 2020 cycle was never published by MassGIS. The 2024/2026 cycle is in draft as of April 2026 — the script will auto-detect it when MassGIS publishes the approved shapefile. `CSO_303d_Mapping` in `assemble_db.py` is a manually curated dict (35 verified matches of 56 CSO waterbodies); update it when a new cycle is added by reviewing new assessment unit names against CSO waterBody values.

## Running scripts

**Critical: All scripts use relative paths and MUST be run from their parent directory.** The session starts in the repo root (`/home/nes/Documents/MAenvironmentaldata`).

**Data fetch and assembly (from repo root, cd into get_data/):**
```bash
cd get_data
conda run -n amend_python python get_EPARegion1_NPDES_permits.py
conda run -n amend_python python get_budget_CTHRU.py
conda run -n amend_python python get_DEP_staff_SODA.py
conda run -n amend_python python get_EEA_data_portal.py
conda run -n amend_python python get_eea_dp_cso.py
conda run -n amend_python python validate_data.py
conda run -n amend_python python assemble_db.py
```

**Analysis and visualization (from repo root, cd into analysis/):**
```bash
cd ../analysis
conda run -n amend_python python MADEP_staff.py
conda run -n amend_python python MADEP_enforcements_viz.py
conda run -n amend_python python dashboard_charts.py
```

**Why this matters:**
- `get_data/*.py` scripts read from `../docs/data/` and write outputs there
- `analysis/*.py` scripts read from `../docs/data/` and `../get_data/` and write to `../_includes/charts/`
- Using wrong working directory causes "file not found" or "cannot save to non-existent directory" errors
- Always use `conda run -n amend_python` (not `conda activate`); this ensures clean environment isolation between runs

## Local Jekyll preview

Run from the `docs/` directory in the `amend_jekyll` conda env.  Use `--host localhost` (not `0.0.0.0`) so that `site.url` resolves to `http://localhost:4000` and sidebar links work correctly in the browser:

```bash
cd docs
conda run -n amend_jekyll bundle exec jekyll serve --host localhost --port 4000 --baseurl ""
```

## Analysis scripts

PySTAN models are excluded from CI.  Run locally with the full conda env.

## Live Dashboard

The live dashboard at `/dashboard.html` auto-updates weekly via `update-charts.yml`. All dashboard chart files use a `dash_` filename prefix to prevent overwriting historical blog post charts.

### How it works

**`analysis/dashboard_charts.py`** — Master script that generates all dashboard charts:
- Wraps calls to `MADEP_staff.generate_charts()`, `MADEP_enforcements_viz.generate_charts()`, and `ECOS_budgets_viz.generate_charts()` with `prefix='dash_'`
- Instantiates `CSOAnalysisEEADP` with `end_date=date.today()` for rolling CSO data window, `make_regression=False` (Stan excluded from CI), `make_maps=False` (too heavy for weekly CI)
- Calls dashboard-specific plot methods: `plot_monthly_volume_and_rainfall()`, `plot_monthly_modeled_vs_metered_fraction()`, `plot_monthly_volume_by_watershed()`, `plot_annual_volume_by_operator()`

**Four refactored analysis scripts** — Each now has a `generate_charts(engine, prefix='')` function:
- `MADEP_staff.py` — Generates 6 staffing charts
- `MADEP_enforcements_viz.py` — Generates 6 enforcement charts (overall, vs budget, by type, penalties overall, penalties stacked, topic breakdown); uses `MAEEADP_Enforcement` for counts/fines 1996–2026, `MADEP_enforcement` for topic breakdown through 2017; enforces routine notice filtering to restore enforcement-staffing correlation
- `ECOS_budgets_viz.py` — Generates 3 budget comparison charts
- `EPA_303d_viz.py` — Generates 4 dashboard charts (impaired trend, causes, CSO-to-impaired, TMDL progress) + writes `docs/data/facts_EPA303d.yml`; `generate_post_charts()` also generates 2 analysis-post charts (watershed bar chart, folium TMDL map) — requires folium, excluded from CI

**`docs/dashboard.md`** — Jekyll post at `/dashboard.html` that includes the `dash_*.html` chart files. See file for data sources and methodology notes.

### Key implementation details

**Numpy serialization:** `chartjs.py` automatically converts numpy scalars and NaN to JSON-safe values via `_NumpyEncoder`. You do not need to manually convert arrays before passing to `add_dataset()`.

**Chart.js version:** The current version is defined in `analysis/chartjs.py` as `JS_URL` (currently `chart.js@4.4.4`). To upgrade:
1. Update the version string in `JS_URL` in `chartjs.py`
2. Check the [Chart.js migration guide](https://www.chartjs.org/docs/latest/migration/) for breaking API changes
3. Update `make_chart_canvas()` in `chartjs.py` if the scale/plugin config API changed
4. Search for any hardcoded CDN URLs in `analysis/` scripts (e.g. `_CHARTJS_CDN` in `EPA_303d_viz.py`) and update those too
5. Re-run `dashboard_charts.py` and visually verify charts render correctly

**Date handling:** Use `pd.to_datetime()` when comparing Python `date` objects with pandas datetime64 values. Avoids `TypeError: ufunc 'isnan' not supported` errors.

**File protection mechanism:** Blog post charts (e.g., `MADEP_staffing_overall.html`) are never regenerated by CI — only dashboard charts with `dash_` prefix are. The `if __name__ == '__main__':` block in each refactored script calls `generate_charts(engine, prefix='')` (empty prefix), preserving original filenames for local testing. CI always uses `prefix='dash_'`.

### Data currency

| Chart | Data source | Auto-updates? | Notes |
|-------|------------|---------------|-------|
| Staffing levels | MA Comptroller SODA API | Yes | Updated Monday via data pipeline |
| Staffing vs funding | SODA + CTHRU Socrata | Yes | Both update Monday; FY2001–2004 from cached MassBudget (static) |
| Seniority | SODA payroll | Yes | Data only available through 2016 from VisibleGovernment; Comptroller data doesn't include seniority calculations |
| Enforcement overall | EEA Data Portal | Yes | 1996–2026 (substantive actions only, routine notices filtered) |
| Enforcement vs funding | EEA DP + CTHRU Socrata | Yes | Both update Monday |
| Enforcement by type | EEA Data Portal MAEEADP_Enforcement | Yes | Shows substantive enforcement action types through 2026; filtered from 54k+ routine notices |
| ECOS per-capita spending | ECOS budget survey | Static | Fetched manually; update frequency depends on ECOS data release schedule |
| CSO annual volume + rainfall | EEA DP CSO + NOAA ACIS | Yes | Uses `end_date=date.today()` for rolling window |
| CSO monthly counts + rainfall | EEA DP CSO + NOAA ACIS | Yes | Same as above; rainfall overlaid as line |
| CSO by operator (annual trends) | EEA DP CSO | Yes | Top 10 operators shown; updated Monday |
| CSO modeled vs metered | EEA DP CSO | Yes | Monthly CSO-Untreated (detailed), SSO aggregated annually |
| CSO by watershed | EEA DP CSO + geography lookup | Yes | Top 8 waterbodies; uses Waterbody fallback if Watershed not available |
| 303(d) impaired trend | MassGIS shapefiles (biennial) | Auto-detects new cycle | Script exits early if cycles unchanged; new data expected ~2027 for 2024/2026 cycle |
| 303(d) causes breakdown | MassGIS shapefiles (biennial) | Auto-detects new cycle | Top 15 causes in most recent approved cycle |
| 303(d) CSO to impaired | MassGIS + EEA DP CSO + CSO_303d_Mapping | Auto (CSO); biennial (303d) | CSO_303d_Mapping must be manually reviewed when a new 303d cycle is added |
| 303(d) TMDL progress | MassGIS shapefiles (biennial) | Auto-detects new cycle | hasTmdl derived from category column in each cycle's DBF |

Dashboard includes italicized notes where data is static (budget, ECOS, seniority cutoff).

### Maintenance tasks

**When data sources change:**
- If SSA website unblocks automated access, uncomment the `get_SSAWages.py` call in CI and it will auto-fetch real AWI data (currently using cached 2023-02-03 version)
- If ECOS releases new data, manually fetch and run `ECOS_budgets_viz.generate_charts()` to update dashboard
- If EEA DP schema changes, test locally first, then update CI script
- CTHRU budget data (DEP, DCR, EEA, Fish&Game) auto-updates Monday; FY2001–2004 from cached MassBudget do not update

**When adding new dashboard charts:**
1. Add chart generation method to the appropriate analysis script (or `EEA_DP_CSO_map.py`)
2. Update `dashboard_charts.py` to call the new method with output slug `f'{PREFIX}MAEEADP_dashboard_...'`
3. Add chart include line to `docs/dashboard.md` with methodology notes
4. Test locally: `python dashboard_charts.py && cd docs && bundle exec jekyll serve --host localhost --port 4000 --baseurl ""`

## AI Analysis

The AI Analysis page (`docs/ai_analysis.html`) lets users ask natural-language questions. The LLM generates SQL, executes it client-side via the existing sql.js Web Worker, and renders results with Plotly.

**Supported providers:** Groq (default, free), OpenAI, Google Gemini. Anthropic Claude is excluded — no browser CORS support.

### Semantic context

The LLM receives `docs/assets/db_semantic_context.txt` instead of bare `CREATE TABLE` statements. This file includes table descriptions, 5 sample rows per table (showing actual value formats like ALL-CAPS town names), per-column notes (typos, date formats, join keys), and cross-table join relationships.

**The semantic context must be regenerated whenever data sources change** (new tables, renamed columns, new data loaded). It is auto-regenerated by `assemble_db.py` after each DB build.

To regenerate manually:
```bash
cd get_data
conda run -n amend_python python generate_semantic_context.py
```

**When adding or changing a data source:**
1. Update `TABLE_DESCRIPTIONS` and `COLUMN_NOTES` in `get_data/generate_semantic_context.py`
2. Run `generate_semantic_context.py` to update `docs/assets/db_semantic_context.txt`
3. Commit both files along with any CSV/DB changes

**Key implementation files:**
- `get_data/generate_semantic_context.py` — generates semantic context from `AMEND.db`
- `docs/assets/db_semantic_context.txt` — the generated context (committed, auto-updated)
- `docs/ai_analysis.html` — page layout (disclaimer, settings, two-panel chat + artifact tray); also contains starter question buttons
- `docs/assets/ai_analysis.js` — all client-side logic (~950 lines vanilla JS)
- `docs/assets/ai_analysis.css` — styles

### Starter questions

Starter question buttons live in `docs/ai_analysis.html` as `.ai-starter-btn` elements inside `#ai-starters`. When updating them, follow these principles:
- **Prefer trend/historical questions** over point-in-time status questions; current-status questions are only appropriate for datasets with high recency (CSO, enforcement, permits — not 303d which only goes to 2022)
- **Prioritise cross-dataset joins** — the best questions exercise joins between 2–3 tables (e.g. CSO + precipitation, enforcement + budget, CSO + 303d mapping + impairments)
- **Cover a range of plot types** — aim for scatter, dual-axis line, bar, choropleth, and stacked bar across the full set
- **Be broadly representative** — one or two questions per major data asset (CSO, staffing/budget, enforcement, 303d, drinking water, ECOS, NPDES/permits, EJ)

### Semantic context pitfalls

Common LLM SQL errors and how the semantic context addresses them:
- **ALL-CAPS fields**: `waterBody`, `municipality`, `Town` are stored in ALL CAPS — document this with `UPPER()` examples
- **Misspelled column**: `volumnOfEvent` (not "volume") — document explicitly in `COLUMN_NOTES`
- **Year as FLOAT**: `MAEEADP_CSO.Year` is stored as FLOAT (e.g. 2023.0) — note `CAST(Year AS INTEGER)` if needed
- **Table alias confusion**: lookup/mapping tables (e.g. `CSO_303d_Mapping`, `CSO_WatershedMapping`) have very few columns — add explicit `IMPORTANT: this table has NO [other columns]` warnings in `TABLE_DESCRIPTIONS` and `COLUMN_NOTES` to prevent the LLM from applying filters (e.g. `reportingCycle`) to the wrong alias
- **Join pattern examples**: add concrete SQL examples to `JOIN_RELATIONSHIPS` for non-obvious multi-table joins; the LLM reliably follows patterns it has seen

### API key security

**Browser storage:** The Ask AI page stores API keys in **browser localStorage** (plain text, client-side). This is not cryptographically secured but keeps keys off your servers. On shared machines, any JavaScript on the page or other browser extensions could access the key. 

**Recommendations for users:**
- Use **restricted/temporary API keys** if your provider supports them (e.g., API keys with rate limits, expiration dates, or scope limitations)
- On shared machines, clear browser storage after use (`localStorage.clear()` in browser console), or use private/incognito browsing
- Providers like Groq, OpenAI, and Gemini all support creating limited-scope keys

**For the demo recording script:** The `record_ai_demo.py` script accepts API keys via environment variables only (`GROQ_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`). Keys are held in memory during recording and never persisted to disk.
