# CLAUDE.md — Working in the AMEND Repository

## Python environment

All Python scripts run in the `amend_python` conda environment:

```bash
conda activate amend_python
```

Scripts that are part of the CI pipeline use `requirements-ci.txt`. The only excluded dep is PySTAN (`stan`). Everything else needed by `dashboard_charts.py` and its transitive imports must be listed there. The full conda env is needed to run the analysis/visualization scripts locally.

**When adding a new import to any script in the `dashboard_charts.py` call chain**, check whether the package is in `requirements-ci.txt` and add it with a pinned version if not. The full import chain is: `dashboard_charts.py` → `MADEP_staff`, `MADEP_enforcements_viz`, `ECOS_budgets_viz`, `EPA_303d_viz`, `EEA_DP_CSO_map` → `NECIR_CSO_map` → `cso_maps`. To find the pinned version: `conda run -n amend_python python -c "import pkg_resources; print(pkg_resources.get_distribution('PKGNAME').version)"`.

## Repository layout

```
get_data/        Data-fetch and database-assembly scripts (run these first)
docs/data/       CSV output files and Jekyll data-source pages
docs/_includes/  Generated chart HTML (Chart.js for charts, Plotly/Folium for maps)
docs/assets/     Maps, figures, PDFs
analysis/        Visualization and statistical analysis scripts
```

**Data-source description pages** (the human-facing "what is this dataset" write-ups,
`layout: data_listing`) live in `docs/data/*.md` — one per dataset, e.g.
`docs/data/MA_lobbying.md`, `docs/data/EEADP_all.md`, `docs/data/MADEP_staff.md`.
Update the relevant `docs/data/<dataset>.md` whenever a dataset's schema, coverage,
or methodology changes so the published description stays accurate.

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
- **MA lobbying portal (Incapsula WAF)**: The SoS portal (`sec.state.ma.us/LobbyistPublicSearch/`) is protected by Incapsula WAF. A Chrome User-Agent gets a 302 redirect to a JS challenge page. An **iPad User-Agent** bypasses it entirely with plain `requests` — no Selenium needed. The working UA is `Mozilla/5.0 (iPad; CPU OS 12_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148`.
- **MA lobbying portal (search form)**: ASP.NET with ViewState. POST to `Default.aspx` with `drpType=L` (Lobbyist or Lobbying Entity — do NOT use `Z` which returns Client pages with different structure), `drpPageSize=20000`, `ddlYear=<year>`. POST timeout must be 120s (response is ~2MB for ~1700 results). Data goes back to 2005 (22 years).
- **MA lobbying incremental fetch**: Disclosures are filed semi-annually (H1 due ~Jul 15 of the year; H2 due ~Jan 15 of the following year), and amendments cluster within ~60 days of those deadlines. The incremental state lives in `MA_lobbying_summary_links.csv` (gitignored, synced to/from GCS by the script itself): each visited summary page is stamped with `last_checked`, pages with no disclosures get a marker row with null `disc_url`. Pages are re-checked only inside a filing window (`deadline − 14d` to `deadline + 60d`) plus one closing sweep after it; a year is skipped wholesale before Jul 1 (H1 period not yet closed). Steady-state weekly runs take ~1–2 min; runs during the Jul and Jan filing windows scan all ~1,700 pages (~40 min). State uploads to GCS happen every 200 pages (data files first, links index last) so a timed-out CI run still makes durable progress.
- **MA lobbying full historical fetch**: `REQUEST_DELAY` is 0.3s; actual page time is ~1.3s (server latency dominates). A full single-year scan (~1,700 registrants) takes ~40 min when most pages are skipped-after-visit, ~hours when every disclosure must also be fetched. The full 22-year history was completed in May 2026; it only ever needs re-running if the GCS state files are lost.
- **Running lobbying scripts**: Do NOT use `conda run` with stdout redirect (`> file`) — `conda run` buffers all output through a pipe and the log file stays empty until the process exits. Run Python directly: `/home/nes/miniconda/envs/amend_python/bin/python -u get_MA_lobbying.py` (the `-u` flag ensures unbuffered output).
- **MA lobbying Gemini SDK**: Uses `google-genai` (new SDK, `google.genai`), NOT the old `google-generativeai` package. API: `client = genai.Client(api_key=...)`, then `client.models.embed_content(model='gemini-embedding-2', contents=text, config=types.EmbedContentConfig(output_dimensionality=768))`.
- **MA lobbying Gemini API cost — do not underestimate**: Actual observed cost for `summarize_lobbying_bills.py` is **$0.627/1k bills** (verified June 2026). Output tokens ($2.50/1M) dominate at ~60% of total cost even though output is only ~151 tokens/bill. Prior estimates were off by 6× because they applied the input price ($0.30/1M) to output tokens. Rule of thumb: a one-time backfill of 7k bills ≈ $4.50; 26k bills ≈ $16. Weekly incremental runs (20–50 new bills) ≈ $0.02. Embedding via `gemini-embedding-2` is negligible ($0.20/1M tokens ≈ $0.00015/bill). Always verify estimate against GCP billing console before running a large batch — the API pricing page may show non-GA or pre-discount rates.
- **MA lobbying General Court formula bug (unfixed)**: `get_MA_lobbying.py` uses `FIRST_GC_START_YEAR = 2005` but the 183rd General Court started in 2003, not 2005. The correct constant is `2003`. As a result, every bill's `general_court` assignment is one session too low (year 2024 → GC192 instead of GC193, etc.), and `get_MA_legislature_bills.py` fetches bill text from the wrong legislative session. Fixing this constant and re-running the full pipeline would bring the title match rate from ~2% to ~65%. The remaining ~35% of mismatches are string-normalisation differences or genuinely wrong bill numbers in the SoS portal. See `get_data/NOTES_bill_embeddings.md` for full analysis.

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
| ECOS per-capita spending | ECOS budget survey | Static | Fetched manually; data covers FY2009–2023 (last updated from FY2016–2019 and FY2020–2023 reports, April 2026). Next report expected ~2028. Run `get_ECOS_data.py` when new report is published. |
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
- If ECOS releases new data: download the PDF to `get_data/ECOS/`, run `get_ECOS_data.py` (from `get_data/`), then `assemble_db.py`, then `dashboard_charts.py`. ECOS publishes roughly every 3–5 years; current data covers FY2009–2023.
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
