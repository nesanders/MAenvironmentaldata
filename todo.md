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

### Make an animated demo of the Ask AMEND AI feature

Create a short screen-capture animation (GIF or video) showing a user asking a natural-language
question in the Ask AMEND AI interface, the SQL being generated, and an interactive chart or
table appearing as the result. Embed on the About page or README to help new visitors understand
what the feature does before trying it themselves.

### Add unit tests

### Develop tests for AI Analysis semantic context (`get_data/generate_semantic_context.py`)

- Verify every DB table has an entry in `TABLE_DESCRIPTIONS`
- Verify key categorical columns (waterBody, municipality, Town) are flagged as ALL_CAPS in generated output
- Verify column notes for known quirks are present (e.g. `volumnOfEvent` typo note, `Year` as FLOAT in MAEEADP_CSO)
- Verify join relationship hints are present in output
- Verify sample rows are non-empty for all non-skipped tables
- Regression test: run a set of representative natural-language questions through the LLM (mocked or live) and assert the generated SQL is syntactically valid and references correct table/column names
- Consider a round-trip integration test: generate SQL from question → execute against AMEND.db → assert non-empty result set