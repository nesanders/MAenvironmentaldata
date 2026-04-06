# Datasets

### UMass Water Resources Research Center Acid Rain Monitoring Project

[link](https://wrrc.umass.edu/research/acid-rain-monitoring-project)

### US EPA Clean Water Act 303(d) impaired waters assessment reports

[link](https://www.epa.gov/tmdl/region-1-impaired-waters-and-303d-lists-state)

### MS4 annual reports and extracted data

### MA political donations

### Update ECOS budget data across states

Look at the latest [ECOS](https://www.ecos.org/areas-of-focus/budget-and-agency-management/) reports to update environmntal agency budget data across states.


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

### Find replacement source for MassBudget environmental budget data
Source: `massbudget.org` — blocked as of early 2026 (Cloudflare on `spreadsheet.php`).
The dashboard currently shows budget data static at 2015 inflation-adjusted levels.
A live dashboard needs current budget figures to track agency spending trends.
Options:
- Contact MassBudget directly for API access or a direct data export
- Check MA Comptroller's system for state appropriations data
- Use alternative budget tracking sources (state executive budget documents, legislative appropriations)

This blocks the funding charts (#2, #5, #7 on the dashboard) from auto-updating. High priority.
