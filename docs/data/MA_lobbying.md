---
title: MA Lobbying Disclosures
author: NES
layout: data_listing
ancillary: 0
---

## Explore the data

The **[MA Lobbying Explorer](https://nsanders.me/ma_lobbying_explorer/)** is an interactive browser for this dataset. Search and filter bills, employers, and lobbying firms; click any entry to see its full disclosure history and links back to the Secretary of State portal and MA Legislature website.

- [Browse bills](https://nsanders.me/ma_lobbying_explorer/bills.html) — search by bill ID, title, or environmental relevance
- [Browse employers](https://nsanders.me/ma_lobbying_explorer/employers.html) — search by employer/client name; see all bills and spend history
- [Browse lobbyists](https://nsanders.me/ma_lobbying_explorer/lobbyists.html) — search by lobbying firm name; see all clients and bills

---

## Data source

The [MA Secretary of State](https://www.sec.state.ma.us/LobbyistPublicSearch/) publishes semi-annual lobbying disclosure filings for all registered lobbyists and lobbying entities in Massachusetts. Filers report which clients hired them, how much each client paid, and which specific bills they lobbied on behalf of each client (with chamber, bill number, title, and position — Support, Oppose, or Neutral).

Data is available from 2005 (184th General Court) through the present, spanning 22 years across 11 legislative sessions. Each two-year legislative session is identified by a General Court number (GC 184 = 2005–2006, GC 194 = 2025–2026, etc.).

The data from this source has been archived on this site, last updated on **{{ site.data.ts_update_MA_lobbying.updated | date: "%-d %B %Y %I:%M %P" }}**.
Filings are refreshed automatically on a weekly basis; the script exits early when no new semi-annual filings have been posted.

## Environmental relevance scoring

To identify which bills are environmentally relevant, each bill's full text (fetched from the [MA Legislature OpenAPI](https://malegislature.gov/api/swagger)) is preprocessed by stripping repeated legislative scaffolding (e.g. "Chapter X of the General Laws, as appearing in the 2020 Official Edition, is hereby amended by inserting after…") that appears identically across thousands of bills regardless of topic. The bill title is then prepended to the cleaned body, and the combined text is truncated to 3,000 characters before embedding. Bills for which no full text is available fall back to the title alone. The cleaned text is embedded using Google's **Gemini Embedding model** (`gemini-embedding-2`, 768-dimensional vectors).

Environmental relevance is scored using **differential cosine similarity**: for each bill, the maximum cosine similarity to a set of 42 known environmental bills is computed, and the maximum cosine similarity to a set of 42 known non-environmental bills is subtracted. Bills with a differential score above **0.05** are flagged as `is_environmental` (~1.3% of all uniquely lobbied bills). The non-environmental reference set spans eight policy domains — labor, criminal justice, healthcare, education, housing, municipal licensing, digital/media, and LGBTQ/social — to prevent cross-domain false positives.

**Data coverage note:** Bills from the two oldest legislative sessions (GC 183–184, 2005–2008) have no full text in the Legislature API and are often missing titles in the lobbying portal as well. These ~1,500 bills embed as zero vectors and are excluded from topic clustering (assigned `cluster_id = -1`). They are retained in the lobbying activity data but do not appear in the t-SNE visualization.

Embeddings are stored in a Parquet file on Google Cloud Storage (`gs://openamend-data/MA_bill_embeddings.parquet`) alongside bill full text. The lightweight scored CSV (scores and cluster IDs only, no embeddings) is committed to this repository.

## Topic clustering

All lobbied bills with valid embeddings (~24,400 bills) are clustered into **25 topic groups** using the **k-means clustering** algorithm on the L2-normalised Gemini embeddings (cosine-space clustering). Each cluster is labelled using **Gemini 2.5 Flash**, which receives the 20 most central bill titles in the cluster and returns a 3–5 word topic label. Clustering is a one-time operation re-run manually when the historical data changes significantly.

| Cluster | Label | Bills | Env. bills |
|---------|-------|------:|----------:|{% for row in site.data.MA_bill_cluster_labels %}
| {{ row.cluster_id }} | {{ row.label }} | {{ row.n_bills }} | {{ row.n_env_bills }} |{% endfor %}

### Bill embedding space (t-SNE)

The plot below shows environmental bills projected into the policy landscape using [t-SNE](https://en.wikipedia.org/wiki/T-distributed_stochastic_neighbor_embedding). **Coloured, outlined dots** are the 329 environmentally-relevant bills, coloured by topic cluster; **grey dots** are a stratified background sample (~120 per cluster, ~3,000 total) providing geographic context. Hover over any point for the bill title.

Note: MA legislative bill embeddings are semantically dense — even after boilerplate stripping, mean inter-cluster cosine distance is only ~0.006 vs. mean intra-cluster spread of ~0.53. Visualising all 25,000+ bills produces a featureless blob because the underlying high-dimensional structure does not project cleanly to two dimensions. The subsample approach makes the environmentally-relevant bills legible without misrepresenting the cluster separation.

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
| --- | --- | --- | --- | --- |{% for row in site.data.MA_lobbying_employers_sample limit:10 %}
| [{{ row.entity_name }}](https://nsanders.me/ma_lobbying_explorer/lobbyists.html?name={{ row.entity_name | slugify }}) | [{{ row.client_name }}](https://nsanders.me/ma_lobbying_explorer/employers.html?name={{ row.client_name | slugify }}) | {{ row.year }} | {{ row.reg_type }} | {{ row.compensation }} |{% endfor %}
{: .sortable}

### Lobbying Bills

One row per (entity, client, bill, session). Records which bills each entity lobbied on behalf of each client, with the lobbying position.

| Entity Name | Client Name | Year | Chamber | Bill | Bill Title | Position |
| --- | --- | --- | --- | --- | --- | --- |{% for row in site.data.MA_lobbying_bills_sample limit:10 %}
| [{{ row.entity_name }}](https://nsanders.me/ma_lobbying_explorer/lobbyists.html?name={{ row.entity_name | slugify }}) | [{{ row.client_name }}](https://nsanders.me/ma_lobbying_explorer/employers.html?name={{ row.client_name | slugify }}) | {{ row.year }} | {{ row.chamber }} | [{{ row.bill_id }}](https://nsanders.me/ma_lobbying_explorer/bills.html?id={{ row.bill_id }}&gc={{ row.general_court }}) | {{ row.bill_title | truncate: 60 }} | {{ row.position }} |{% endfor %}
{: .sortable}

### Legislature Bills

Bill metadata fetched from the [MA Legislature OpenAPI](https://malegislature.gov/api/swagger). Includes sponsor, final status, and derived `passed` boolean. Environmental relevance scores and cluster IDs are stored separately in `MA_lobbying_bills_scored.csv` (see above).

| Bill | General Court | Title | Sponsor | Status | Passed |
| --- | --- | --- | --- | --- | --- |{% for row in site.data.MA_legislature_bills_sample limit:10 %}
| [{{ row.bill_id }}](https://nsanders.me/ma_lobbying_explorer/bills.html?id={{ row.bill_id }}&gc={{ row.general_court }}) | {{ row.general_court }} | {{ row.title | truncate: 60 }} | {{ row.sponsor_name }} | {{ row.status | truncate: 40 }} | {{ row.passed }} |{% endfor %}
{: .sortable}
