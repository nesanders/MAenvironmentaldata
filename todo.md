# Datasets

### UMass Water Resources Research Center Acid Rain Monitoring Project

[link](https://wrrc.umass.edu/research/acid-rain-monitoring-project)

### MS4 annual reports and extracted data

### MA political donations

### MA environmental lobbying data

MA Secretary of State lobbying disclosure portal at [https://www.sec.state.ma.us/LobbyistPublicSearch/](https://www.sec.state.ma.us/LobbyistPublicSearch/) publishes filings by lobbyist, employer (client), and bill. Data is annual going back to ~2007.

#### Data available
- **By lobbyist**: registration, employer clients, bills lobbied, compensation received
- **By employer/client**: annual lobbying expenditures, lobbyists retained, bills targeted
- **By bill**: which employers/lobbyists filed on each bill number (cross-ref to legislature)
- **By subject area**: MA SoS assigns subject tags to filings (Energy & Environment is one)

#### Database tables (normalized schema)
- `MA_Lobbying_Employers` — one row per employer-year: name, total expenditure, industry sector (manually curated)
- `MA_Lobbying_Lobbyists` — one row per lobbyist-year-employer: lobbyist name, compensation
- `MA_Lobbying_Bills` — fact table: one row per bill-year-employer: bill number, general court session, employer name, `env_relevance_score FLOAT`, `is_environmental BOOL`; foreign keys into `MA_Lobbying_Employers` and `MA_Legislature_Bills`
- `MA_Legislature_Bills` — one row per bill-session: bill number, general court, title, primary sponsor, committee, final status, `passed BOOL`; populated from MA Legislature OpenAPI independent of lobbying data

#### Scraping approach (`get_data/get_MA_lobbying.py`)
1. Pull **all** lobbying filings without pre-filtering by subject tag — filer-supplied subject tags are unreliable (a utility lobbying a wastewater bill may tag it "Utilities & Energy"; a developer opposing wetlands reform may tag it "Land Use"). Subject tags can be retained as a column for reference but should not gate inclusion.
2. Paginate the SoS portal search using `requests` + `BeautifulSoup`. Rate-limit to ~1 req/sec with `time.sleep`. Cache raw HTML under `get_data/MA_lobbying_cache/` so incremental re-runs skip already-fetched pages.
3. Write raw CSVs to `docs/data/`: `MA_lobbying_employers.csv`, `MA_lobbying_lobbyists.csv`, `MA_lobbying_bills.csv`.

#### Bill augmentation (`get_data/get_MA_legislature_bills.py`)
- Fetch only bills that appear in lobbying disclosures (to keep scope bounded) from the **MA Legislature OpenAPI** at [https://malegislature.gov/api/swagger](https://malegislature.gov/api/swagger). No auth required.
- Key endpoints: `GET /api/GeneralCourts` (session index), `GET /api/GeneralCourts/{generalCourtNumber}/Bills/{billNumber}` (bill metadata).
- Write `docs/data/MA_legislature_bills.csv`. Cache JSON responses under `get_data/MA_legislature_cache/`.

#### Environmental relevance scoring (`get_data/score_lobbying_bills.py`)
- For each unique bill in `MA_Legislature_Bills`, embed `title + description` using the **Google Embeddings API** (`gemini-embedding-2` — current production model as of 2026; supports up to 8,192 input tokens, 768–3,072 output dimensions) via `SECRET_GOOGLE_API_KEY` (already in repo).
- Compute cosine similarity against a curated set of seed phrases: "environmental regulation", "water quality", "wetlands protection", "air pollution control", "DEP enforcement", "stormwater management", "CSO discharge", "hazardous waste", "climate change", "clean energy", "pesticide regulation", "drinking water safety".
- Store `env_relevance_score` (0–1 float) on `MA_Legislature_Bills`; derive `is_environmental` at a calibrated threshold (e.g. 0.55 — tune against a hand-labeled validation set of ~50 bills). Storing the raw score lets analysts choose their own threshold.
- Only embed new/unseen bills on each incremental run — cost stays low.
- Add `GOOGLE_API_KEY` secret to CI for this step; a separate `score_lobbying_bills.py` call after `get_MA_legislature_bills.py`.

#### Pipeline integration
- Add to `assemble_db.py` and `generate_semantic_context.py` with explicit join relationship notes (lobbying bills → legislature bills via `bill_number + general_court`; lobbying bills → employers via `employer_name + year`).
- Add to `validate_data.py` row-count checks.
- CI sequence (in `update-data.yml`): `get_MA_lobbying.py` → `get_MA_legislature_bills.py` → `score_lobbying_bills.py`, inserted after `get_eea_dp_cso.py` (step 5.6–5.8).

#### Analyses and blog posts

**Lobbying spend vs. DEP budget and staffing** *(strongest cross-dataset narrative)*
- Overlay annual industry lobbying spend on environmental bills (`env_relevance_score` threshold) against DEP/EEA budget and FTE timelines from `ECOS_budgets_viz.py` and `MADEP_staff.py`. A dual-axis time series: rising lobbying spend vs. falling regulatory capacity, 2007–present.

**Environmental bill lobbying landscape**
- Which industries (energy, real estate, agriculture, municipalities) dominate lobbying on environmental bills? Time-trend from 2007–present.
- Cross-reference bill disposition (`passed` from legislature API) against lobbying spend — do more heavily-lobbied bills die more often? Requires aggregating employer spend per bill per session.

**Lobbying intensity vs. enforcement outcomes**
- Join `MA_Lobbying_Employers` against `MAEEADP_Enforcement` by regulated entity name (fuzzy match via rapidfuzz). Are the highest-spending lobbying clients also among the most frequently violated? Does lagged lobbying spend predict reduced enforcement counts?

**CSO operator lobbying**
- Cross-reference `MA_Lobbying_Bills` (filtered to high `env_relevance_score` CSO/wastewater bills) against EEA DP CSO operators. Are MWRA, city DPWs, or industrial dischargers lobbying on bills that would tighten or relax CSO controls?

#### Dashboard charts (weekly-updatable, add to `dashboard_charts.py`)
Lobbying data updates once per year (prior-year filings posted mid-year), so charts will show a new data point annually but are still appropriate for the weekly-run dashboard.

| Chart slug | Description |
|------------|-------------|
| `dash_lobbying_spend_trend` | Annual total lobbying spend on environmentally-relevant bills (`is_environmental=True`), 2007–present, stacked by industry sector |
| `dash_lobbying_top_employers` | Top 15 employer spenders (most recent complete year) — horizontal bar |
| `dash_lobbying_bill_intensity` | Unique bills lobbied per year + share that passed vs. died in committee |
| `dash_lobbying_vs_enforcement` | Dual-axis: industry lobbying spend (left) vs. EEA enforcement action count (right), 2007–present |

All four follow the existing `{% include %}` pattern in `docs/dashboard.md`.

#### Complementary data: MA Legislature OpenAPI
- Session (General Court) index: resolves bill numbers across sessions (190th, 191st, etc.)
- Sponsor data: cross-reference sponsor names against lobbying employer targets to identify which legislators are most frequently lobbied on environmental topics (analysis-post level, not dashboard)

#### Pending: re-fetch 2010–2016 bill data

The 2010+ disclosure pages use a 5-column format (`Activity or Bill No and Title | Position | DirectBiz | Client | Compensation`) rather than the 2009 4-column format (`Date | Bill+Title | Lobbyist | Client`). The scraper parser was reading the wrong column as the bill cell, so 2010–2016 fetches captured employer compensation but zero bills.

Fix is already applied in `get_MA_lobbying.py` (header-based format detection — looks for `'Activity'` in the first header cell to choose `bill_col=0, client_col=3` vs. the 2009 layout). The currently-running historical scrape (started 2026-05-21) has already cached those years' `disc_url`s as "fetched", so the fix won't take effect until those rows are re-queued.

Recovery steps (run from `get_data/` after the main scrape finishes through 2026):
1. Confirm main scrape complete: check `MA_lobbying_summary_links.csv` has rows through 2026
2. Delete year 2010–2016 rows: `python -c "import pandas as pd; df = pd.read_csv('../docs/data/MA_lobbying_summary_links.csv', index_col=0); df = df[~df['year'].astype(int).between(2010, 2016)]; df.to_csv('../docs/data/MA_lobbying_summary_links.csv')"`
3. Restart scraper: `/home/nes/miniconda/envs/amend_python/bin/python -u get_MA_lobbying.py` — will re-fetch only those years using the fixed parser
4. Run `get_MA_legislature_bills.py` to pick up any new general courts found
5. Run `score_lobbying_bills.py`, `cluster_lobbying_bills.py`, `assemble_db.py`, `generate_semantic_context.py`
6. Re-run `MA_lobbying_viz.py` and update the draft analysis post

#### Implementation sequence
1. Manual exploration: browse SoS portal to document exact URL patterns, pagination parameters, and field names before writing scraper
2. Write `get_MA_lobbying.py` with caching; run manually on one year to validate
3. Write `get_MA_legislature_bills.py` for bill augmentation (OpenAPI, no auth)
4. Write `score_lobbying_bills.py` for Google Embeddings API relevance scoring; hand-label ~50 bills to calibrate threshold
5. Extend `assemble_db.py`, `generate_semantic_context.py`, `validate_data.py`
6. Write `MA_lobbying_viz.py` with `generate_charts()` and `generate_post_charts()` following the MS4 pattern
7. Add dashboard chart calls to `dashboard_charts.py`
8. Add steps 1–3 to CI pipeline; add `GOOGLE_API_KEY` secret
9. Write analysis blog post: lobbying spend vs. enforcement/budget narrative

# Analyses

### Distribution of permit age by watershed and municipality 

### Bayesian hierarchical regression: enforcement/budget effects on 303(d) impairment

Fit a hierarchical logistic regression with AUs nested in watersheds. Outcome: binary
impairment status per AU per biennial cycle. AU-level predictors: water type, AU size,
lagged impairment status (autoregressive). Watershed-level predictors: enforcement action
density (EEADP_Enforcement aggregated by municipality→watershed per 2-year window), CSO
discharge volume, population density (Census ACS). State-level temporal predictor: DEP
staff FTE as budget proxy, lagged one cycle.

Expected findings: the autoregressive term will dominate (94% persistence → large
log-odds). Cause type and water type will be the strongest structural predictors — bacterial
impairments are ~3× more likely to resolve than non-bacterial; lakes almost never improve.
Enforcement/budget effects will likely be small and have wide posteriors, because the
binding constraint on delisting is physical tractability of the impairment cause (invasive
plants and legacy mercury are essentially irreversible on decadal timescales), not
regulatory pressure. The most credible result may be a well-quantified null.

Requires PySTAN and full conda env; not suitable for CI.

### 303(d) post-TMDL infrastructure lag: how long does remediation take after regulatory coverage?

The April 2025 EPA statewide pathogen TMDL formally covered ~679 bacterial Category 5 AUs.
Infrastructure investment (septic upgrades, sewer extension, CSO controls) will drive
eventual delisting — the question is timing. Use the 2024/2026 cycle (expected ~2027) as
the first post-TMDL data point, then track the bacterial cohort across subsequent cycles.
Compare against the pre-2025 delisting rate (2.8% per cycle) to estimate whether TMDL
coverage accelerates infrastructure deployment or whether the lag is long enough that
impairment rates barely budge for a decade. Cross-reference with CSO capital spending
records and permit compliance timelines where available.


# Features

### Optimize geospatial performance in analysis scripts
The EJ/EJSCREEN correlation analyses and CSO map scripts are slow due to shapefile
loading and per-feature spatial joins.  Consider pre-simplifying geometries, caching
dissolved boundaries, or switching to vectorized `geopandas.sjoin`.

# Infrastructure

### Add unit tests
