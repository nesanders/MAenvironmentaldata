# Datasets

### UMass Water Resources Research Center Acid Rain Monitoring Project

[link](https://wrrc.umass.edu/research/acid-rain-monitoring-project)

### US EPA Clean Water Act 303(d) impaired waters assessment reports

[link](https://www.epa.gov/tmdl/region-1-impaired-waters-and-303d-lists-state)

### MS4 annual reports and extracted data

### MA political donations


# Analyses

### Distribution of permit age by watershed and municipality 

### Effects of variation in budget and enforcement on 303(d) assessment outcomes


# Features

### Interactive plotting features to allow users to visualize interactive SQL queries

### "Ask AI" tab alongside the SQL query feature
Allow users to ask natural-language questions about the data, with the AI translating
them into SQL queries and/or summarizing results.  Should integrate with the existing
SQL demo interface.

### Restore MassBudget environmental budget data
Source: `massbudget.org` — blocked as of early 2026 (Cloudflare on `spreadsheet.php`).
Contact MassBudget directly for API access or a direct CSV export.
Script: `get_data/get_MassBudget_environmental.py`.

### Update Jekyll and Ruby gem versions
Audit and update `docs/Gemfile` and `docs/Gemfile.lock` to current stable versions of
Jekyll and all dependencies (there are known Dependabot alerts on the default branch).

### Optimize geospatial performance in analysis scripts
The EJ/EJSCREEN correlation analyses and CSO map scripts are slow due to shapefile
loading and per-feature spatial joins.  Consider pre-simplifying geometries, caching
dissolved boundaries, or switching to vectorized `geopandas.sjoin`.

### Replace fixed-in-time chart regeneration with live dashboards
The `update-charts.yml` workflow (now disabled) regenerated charts weekly for analyses
that rarely change: SSA wages, MassBudget, ECOS budgets. These are historical artifacts
that don't benefit from weekly regeneration. Instead:

- Keep blog posts as static historical artifacts (2018 NECIR, 2023/2026 CSO analyses)
- Create new "Dashboards" section on the site with interactive, weekly-updated charts:
  - CSO discharge trends (data refreshed Monday via data pipeline)
  - DEP enforcement and payroll trends (data refreshed Monday)
  - Real-time permit and facility summaries
- Use lightweight Plotly templates or Streamlit for dashboard interactivity
- Only regenerate when underlying data actually changes via `update-data` workflow
- Reduces CI noise and git history churn from unchanged chart files
