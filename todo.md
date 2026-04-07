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

### Optimize geospatial performance in analysis scripts
The EJ/EJSCREEN correlation analyses and CSO map scripts are slow due to shapefile
loading and per-feature spatial joins.  Consider pre-simplifying geometries, caching
dissolved boundaries, or switching to vectorized `geopandas.sjoin`.

# Infrastructure

### Add unit tests