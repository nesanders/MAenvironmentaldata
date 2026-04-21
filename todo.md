# Datasets

### UMass Water Resources Research Center Acid Rain Monitoring Project

[link](https://wrrc.umass.edu/research/acid-rain-monitoring-project)

### MS4 annual reports and extracted data

### MA political donations

### MA environmental lobbying data

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
