# Archive of Mass ENvironmental Data Site

The Archive of Mass ENvironmental Data (AMEND) is a project to assemble and analyze data related to environmental regulation, focused on water policy in Massachusetts.

The website for the project can be [viewed here](https://openamend.org).

This git repository contains code for data acquisition (see `get_data/`), analysis (see `analysis/`), and the [`jekyll`](https://jekyllrb.com/) site (see `docs/`).

## Automated updates

Data is refreshed automatically every Monday at 6am UTC via two GitHub Actions workflows:

- **[Update Data](.github/workflows/update-data.yml):** Fetches all active data sources, validates row counts and schema, assembles the SQLite database, and commits updated CSVs. If any step fails, a GitHub Issue is opened automatically.
- **[Update Charts](.github/workflows/update-charts.yml):** Runs after a successful data update to regenerate Chart.js visualizations. The PySTAN-based CSO regression analysis (`NECIR_CSO_map.py`) is excluded from CI and must be run locally.

Both workflows can also be triggered manually from the GitHub Actions tab.

### Failure notifications

If a workflow fails, a GitHub Issue is opened with a link to the failed run. Make sure you are watching the repository with **Issues** notifications enabled to receive email alerts.

## Updating data manually

To run a full update locally:

```bash
bash update_all.sh
```

This script will not update ECOS budget records or the SSA wage table, which require manual data entry.

## Infrastructure

Large files (SQLite database, full drinking water CSV, permit PDFs) are stored on Google Cloud Storage at `gs://openamend-data` in the `openamend` GCP project. A budget alert is configured at $1/month.

The service account `amend-github-actions@openamend.iam.gserviceaccount.com` is used by CI to write to that bucket. Its credentials are stored as the `GCP_SA_KEY` GitHub Actions secret.

The SODA API credentials for the MA Comptroller payroll data are stored as `SODA_APP_TOKEN` and `SODA_SECRET_TOKEN` GitHub Actions secrets, and also locally in `get_data/SECRET_SODA_token` (not committed).

## Hosting the site

The site is hosted via [GitHub Pages](https://help.github.com/articles/using-jekyll-as-a-static-site-generator-with-github-pages/) from the `docs/` directory.

To run locally:

```bash
conda env create -f amend_jekyll_env.yml
conda activate amend_jekyll
cd docs
bundle exec jekyll serve
```

## Python dependencies

### CI (lightweight)

For running data fetches and most chart scripts (no PySTAN/geopandas):

```bash
pip install -r requirements-ci.txt
```

### Full local environment

For all scripts including PySTAN CSO regression analysis:

```bash
conda env create -f amend_python_env.yml
conda activate amend_python
```

## Other tools used

* [chart.js](http://www.chartjs.org/) — interactive charts
* [Leaflet](http://leafletjs.com) — interactive map display
* [MapShaper](http://mapshaper.org/) — convert MassGIS shapefiles to GeoJSON
* [sql.js](https://github.com/kripken/sql.js/blob/master/README.md) — browser-based SQLite querying
* [Tabula](http://tabula.technology/) — extract tables from PDFs
