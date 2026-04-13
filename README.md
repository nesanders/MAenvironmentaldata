# Archive of Mass ENvironmental Data Site

The Archive of Mass ENvironmental Data (AMEND) is a project to assemble and analyze data related to environmental regulation, focused on water policy in Massachusetts.

The website for the project is [openamend.org](https://openamend.org).

This git repository contains code for data acquisition (see `get_data/`), analysis (see `analysis/`), and the [`jekyll`](https://jekyllrb.com/) site (see `docs/`).

## Automated updates

Data is refreshed automatically every Monday at 6am UTC via two GitHub Actions workflows:

- **[Update Data](.github/workflows/update-data.yml):** Fetches all active data sources, validates row counts and schema, assembles the SQLite database, commits updated CSVs, and regenerates the AI Analysis semantic context. If any step fails, a GitHub Issue is opened automatically.
- **[Update Charts](.github/workflows/update-charts.yml):** Runs after a successful data update to regenerate Chart.js visualizations. The PySTAN-based CSO regression analysis (`NECIR_CSO_map.py`) is excluded from CI and must be run locally.

### Failure notifications

If a workflow fails, a GitHub Issue is opened with a link to the failed run.

## Updating data manually

To run a full update locally:

```bash
bash update_all.sh
```

This script will not update ECOS budget records or the SSA wage table, which require manual data entry.

## Infrastructure

Large files (SQLite database, full drinking water CSV, permit PDFs) are stored on Google Cloud Storage.

## Hosting the site

The site is hosted via [GitHub Pages](https://help.github.com/articles/using-jekyll-as-a-static-site-generator-with-github-pages/) from the `docs/` directory.

To run locally (use `--host localhost` so sidebar links resolve correctly in the browser):

```bash
conda env create -f amend_jekyll_env.yml
conda activate amend_jekyll
cd docs
bundle exec jekyll serve --host localhost --port 4000 --baseurl ""
```

For faster rebuilds while editing, add the `--incremental` flag to rebuild only the files that have changed:

```bash
bundle exec jekyll serve --host localhost --port 4000 --baseurl "" --incremental
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

## Ask AMEND AI

The [AI Analysis page](https://openamend.org/ai_analysis.html) lets users ask natural-language questions about the AMEND database. An AI model generates SQL, executes it client-side via sql.js, and renders interactive charts with Plotly — no data leaves your browser.

<video src="docs/assets/ask-amend-demo.webm" width="100%" controls autoplay muted loop>
  <a href="docs/assets/ask-amend-demo.webm">Watch the demo</a>
</video>

## AI Analysis

The [AI Analysis page](https://openamend.org/ai_analysis.html) lets users ask natural-language questions about the database. The LLM generates SQL, executes it client-side via sql.js, and renders results with Plotly.

### Semantic context

The LLM is given a rich schema description — `docs/assets/db_semantic_context.txt` — instead of bare `CREATE TABLE` statements. This file includes:
- Table descriptions and row counts
- 5 sample rows per table (showing actual value formats, e.g. ALL-CAPS town names)
- Per-column notes (typos, date formats, join keys)
- Cross-table join relationships

**The semantic context must be regenerated whenever data sources change** (new tables, renamed columns, schema changes). It is regenerated automatically by `assemble_db.py` on each weekly data update. To regenerate manually:

```bash
cd get_data
conda run -n amend_python python generate_semantic_context.py
```

When adding or changing a data source:
1. Update `TABLE_DESCRIPTIONS` and `COLUMN_NOTES` in `get_data/generate_semantic_context.py`
2. Run `generate_semantic_context.py` to regenerate `docs/assets/db_semantic_context.txt`
3. Commit both files

### Recording a demo

To create an automated screen-capture demo of the Ask AMEND AI feature:

```bash
# First time: create the Playwright environment
conda env create -f environment-playwright.yml

# Record a demo with Groq (free API key)
GROQ_API_KEY=sk_... conda run -n amend_playwright python record_ai_demo.py

# Or with OpenAI
OPENAI_API_KEY=sk_... conda run -n amend_playwright python record_ai_demo.py

# Or with Google Gemini
GOOGLE_API_KEY=... conda run -n amend_playwright python record_ai_demo.py

# Specify starter question (0-8)
GROQ_API_KEY=sk_... conda run -n amend_playwright python record_ai_demo.py --question 2

# Custom output path
GROQ_API_KEY=sk_... conda run -n amend_playwright python record_ai_demo.py --output my-demo.webm
```

**Prerequisites:**
- Jekyll server running: `cd docs && bundle exec jekyll serve --host localhost --port 4000 --baseurl ""`
- API key from Groq (free), OpenAI, or Google Gemini

The script records a ~30–45 second demo showing a user asking a natural-language question, the generated SQL, and an interactive chart rendering. The API key is only held in memory during the session and is not persisted to disk. Output is saved as WebM video.

### API key security

The Ask AI page stores API keys in **browser localStorage** (plain text, client-side). This is not cryptographically secured but keeps keys off your servers. On shared machines, any JavaScript on the page or browser extensions could access the key.

**Recommendations:**
- Use **restricted/temporary API keys** if your provider supports them (rate limits, expiration, scope limitations)
- On shared machines, clear localStorage after use: open browser console (`F12`), run `localStorage.clear()`, then refresh
- Or use private/incognito browsing to isolate keys from your regular browsing history

All major providers (Groq, OpenAI, Google Gemini) allow creating limited-scope API keys.

## Other tools used

* [chart.js](http://www.chartjs.org/) — interactive charts
* [Plotly](https://plotly.com/javascript/) — interactive choropleth maps (all analysis maps)
* [MapShaper](http://mapshaper.org/) — convert MassGIS shapefiles to GeoJSON
* [sql.js](https://github.com/kripken/sql.js/blob/master/README.md) — browser-based SQLite querying
* [Tabula](http://tabula.technology/) — extract tables from PDFs
