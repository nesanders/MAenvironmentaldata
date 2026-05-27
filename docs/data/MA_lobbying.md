---
title: MA Lobbying Disclosures
author: NES
layout: data_listing
ancillary: 0
---

## Data source

The [MA Secretary of State](https://www.sec.state.ma.us/LobbyistPublicSearch/) publishes semi-annual lobbying disclosure filings for all registered lobbyists and lobbying entities in Massachusetts. Filers report which clients hired them, how much each client paid, and which specific bills they lobbied on behalf of each client (with chamber, bill number, title, and position — Support, Oppose, or Neutral).

Data is available from 2005 (183rd General Court) through the present, spanning 22 years across 11 legislative sessions. Each two-year legislative session is identified by a General Court number (GC 183 = 2005–2006, GC 194 = 2025–2026, etc.).

The data from this source has been archived on this site, last updated on **{{ site.data.ts_update_MA_lobbying.updated | date: "%-d %B %Y %I:%M %P" }}**.
Filings are refreshed automatically on a weekly basis; the script exits early when no new semi-annual filings have been posted.

## Environmental relevance scoring

To identify which bills are environmentally relevant, each bill's full text (fetched from the [MA Legislature OpenAPI](https://malegislature.gov/api/swagger) and truncated to 2,000 characters) is embedded using Google's **Gemini Embedding model** (`gemini-embedding-2`, 768-dimensional vectors). Bills for which full text is unavailable fall back to their title.

Environmental relevance is scored using **differential cosine similarity**: for each bill, the maximum cosine similarity to a set of 20 known environmental bills is computed, and the maximum cosine similarity to a set of 20 known non-environmental bills is subtracted. Bills with a differential score above **0.05** are flagged as `is_environmental` (~22% of all lobbied bills in 2024).

This approach avoids the "compressed range" problem of seed-phrase scoring, where all bills cluster in a narrow similarity band and thresholds become arbitrary. By anchoring to real bills rather than short phrases, the model distinguishes genuinely environmental legislation from superficially similar health, infrastructure, or governance bills.

Embeddings are stored in a Parquet file on Google Cloud Storage (`gs://openamend-data/MA_bill_embeddings.parquet`) alongside bill full text. The lightweight scored CSV (scores and cluster IDs only, no embeddings) is committed to this repository.

## Topic clustering

All lobbied bills are clustered into **15 topic groups** using **k-means** on the L2-normalised Gemini embeddings (cosine-space clustering). Each cluster is labelled using **Gemini 2.5 Flash**, which receives the 20 most central bill titles in the cluster and returns a 3–5 word topic label. Clustering is a one-time operation re-run manually when the historical data changes significantly.

| Cluster | Label | Bills | Env. bills |
|---------|-------|------:|----------:|{% for row in site.data.MA_bill_cluster_labels %}
| {{ row.cluster_id }} | {{ row.label }} | {{ row.n_bills }} | {{ row.n_env_bills }} |{% endfor %}

The two most environment-heavy clusters are **Health, Climate, and Community** (cluster 11; 155/172 env) and **Legislative Modernization and Reform** (cluster 13; 166/248 env). The former captures direct environmental/climate legislation; the latter is a catch-all for cross-cutting reform bills that frequently include environmental provisions.

### Bill embedding space (t-SNE)

The plot below shows all lobbied bills projected into two dimensions using [t-SNE](https://en.wikipedia.org/wiki/T-distributed_stochastic_neighbor_embedding) (perplexity 40, 1,000 iterations). Each point is a bill; colour indicates topic cluster; larger points with white rings are bills flagged as environmentally relevant. Hover over any point for the bill title.

{% include charts/lobbying_bill_tsne.html %}

## Download archive

Full CSVs are stored in Google Cloud Storage (too large for the repository).
These links will be active once the initial full-history scrape is complete and uploaded:

* Lobbying employers (entity–client–year) — `gs://openamend-data/MA_lobbying_employers.csv`
* Lobbying bills (entity–client–bill–year) — `gs://openamend-data/MA_lobbying_bills.csv`
* Lobbying bills scored (env relevance + cluster) — `gs://openamend-data/MA_lobbying_bills_scored.csv`
* Legislature bill metadata — `gs://openamend-data/MA_legislature_bills.csv`
* [Bill embeddings (768-dim Parquet)](https://storage.googleapis.com/openamend-data/MA_bill_embeddings.parquet)

## Data tables

### Lobbying Employers

One row per (entity, client, year). Records how much each client paid each lobbying entity in a given year.

| Entity Name | Client Name | Year | Reg Type | Compensation |
| --- | --- | --- | --- | --- |{% for row in site.data.MA_lobbying_employers_sample %}
| {{ row.entity_name }} | {{ row.client_name }} | {{ row.year }} | {{ row.reg_type }} | {{ row.compensation }} |{% endfor %}
{: .sortable}

### Lobbying Bills

One row per (entity, client, bill, session). Records which bills each entity lobbied on behalf of each client, with the lobbying position.

| Entity Name | Client Name | Year | Chamber | Bill Number | Bill Title | Position |
| --- | --- | --- | --- | --- | --- | --- |{% for row in site.data.MA_lobbying_bills_sample %}
| {{ row.entity_name }} | {{ row.client_name }} | {{ row.year }} | {{ row.chamber }} | {{ row.bill_number }} | {{ row.bill_title }} | {{ row.position }} |{% endfor %}
{: .sortable}

### Legislature Bills

Bill metadata fetched from the [MA Legislature OpenAPI](https://malegislature.gov/api/swagger). Includes sponsor, final status, and derived `passed` boolean. Environmental relevance scores and cluster IDs are stored separately in `MA_lobbying_bills_scored.csv` (see above).

| Bill Number | General Court | Title | Sponsor | Status | Passed |
| --- | --- | --- | --- | --- | --- |{% for row in site.data.MA_legislature_bills_sample %}
| {{ row.bill_number }} | {{ row.general_court }} | {{ row.title }} | {{ row.sponsor_name }} | {{ row.status }} | {{ row.passed }} |{% endfor %}
{: .sortable}
