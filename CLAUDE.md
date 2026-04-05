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

`.github/workflows/update-charts.yml` — triggers after a successful data update run.  Runs the six chart-generation scripts (excludes PySTAN and NECIR_CSO_map which require the full local env).

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

PySTAN models are excluded from CI.  Run locally with the full conda env.  The six CI-safe chart scripts are listed in `.github/workflows/update-charts.yml`.
