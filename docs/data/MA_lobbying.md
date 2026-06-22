---
title: MA Lobbying Disclosures
author: NES
layout: data_listing
ancillary: 0
---

## Data source

The [MA Secretary of State](https://www.sec.state.ma.us/LobbyistPublicSearch/) publishes semi-annual lobbying disclosure filings for all registered lobbyists and lobbying entities in Massachusetts. Filers report which clients hired them, how much each client paid, and which specific bills they lobbied on behalf of each client (with chamber, bill number, title, and position — Support, Oppose, or Neutral).

Data is available from 2005 (184th General Court) through the present, spanning 22 years across 11 legislative sessions. Each two-year legislative session is identified by a General Court number (GC 184 = 2005–2006, GC 194 = 2025–2026, etc.).

The data from this source has been archived on this site, last updated on **{{ site.data.ts_update_MA_lobbying.updated | date: "%-d %B %Y %I:%M %P" }}**.
Filings are refreshed automatically on a weekly basis; the script exits early when no new semi-annual filings have been posted.

## Compensation (lobbying spend)

Total lobbying spend is the **sum of the `compensation` column across all rows** of the employers table (both registrant types — lobbying entities and individual lobbyists). The figures do **not** need de-duplication: under the Secretary of the Commonwealth's filing rules each client payment is reported exactly once — by the lobbying entity *or* by the individual lobbyist, never both:

> "Compensation paid by the client should be reported either as an amount received by the lobbyist entity, or as an amount received by the individual lobbyist. The same payment should not be reported in both sections."
> — [Entity Disclosure Reporting User Guide](https://www.sec.state.ma.us/lobbyistweb/readme/OnlineHelp/2010/08_DiscEntityDec2020.pdf), Form 2, p.8 (see also the [Lobbyist Division](https://www.sec.state.ma.us/divisions/lobbyist/lobbyist.htm) and the [lobbying statute, M.G.L. c.3 §§39–50](https://www.sec.state.ma.us/lobbyistweb/ReadMe/MALobbyingLaw.pdf)).

On this basis, total reported compensation reached **${{ site.data.facts_lobbying.lobbying_total_spend_latest | divided_by: 1000000 }}M in {{ site.data.facts_lobbying.lobbying_most_recent_year }}**, roughly **${{ site.data.facts_lobbying.lobbying_total_spend_cumulative | divided_by: 1000000 }}M cumulatively** over {{ site.data.facts_lobbying.lobbying_first_year }}–{{ site.data.facts_lobbying.lobbying_most_recent_year }}. Note: filings from 2005–2008 use an older format that reports only an entity-level salary total (no per-client breakdown), so those years are best presented at the entity level. Two separate money streams are tracked in their own tables and are **not** part of spend: **salaries** paid by an entity to its lobbyists, and **campaign contributions** made by lobbyists.

**Bills vs. executive/regulatory activity:** the bills table records lobbying on legislative bills *and* on executive/regulatory matters. For the latter the source's "Bill Number or Agency Name" field holds an agency name (e.g. "Office of the Governor") and the chamber is `Executive`. To count *legislative bills*, use distinct `bill_id` (chamber-prefixed) or filter to House/Senate Bill/Docket chambers — not raw activity rows.

## Environmental relevance & taxonomy

Each bill is classified by an LLM (**Gemini 2.5 Flash**), which reads the bill title and text and returns a plain-English summary, a policy **category** and **tags** (from a fixed 21-category / 183-tag taxonomy), and an **environmental relevance** judgment. This LLM flag (`is_environmental`) is authoritative — in spot-checks it achieved ~100% recall and ~97% specificity, far better than a purely embedding-based classifier, which missed many clearly environmental bills (e.g. the bottle bill, net metering). **{{ site.data.facts_lobbying.lobbying_n_env_bills }} of {{ site.data.facts_lobbying.lobbying_n_bills_total }}** uniquely lobbied bills (~{{ site.data.facts_lobbying.lobbying_env_pct }}%) are flagged environmental.

As a secondary numeric feature, each bill also carries an embedding-based `env_relevance_score`: its full text (from the [MA Legislature OpenAPI](https://malegislature.gov/api/swagger)) is stripped of repeated legislative scaffolding, prepended with the title, truncated to 3,000 characters, and embedded with Google's **Gemini Embedding model** (`gemini-embedding-2`, 768-dim). The score is the differential cosine similarity to reference sets of known environmental vs. non-environmental bills. It is retained for ranking/analysis but is no longer the classification of record.

**Data coverage note:** Bills from the two oldest legislative sessions (GC 183–184, 2005–2008) have no full text in the Legislature API and are often missing titles in the lobbying portal as well. These ~1,500 bills embed as zero vectors and are excluded from topic clustering (assigned `cluster_id = -1`). They are retained in the lobbying activity data but do not appear in the t-SNE visualization.

Embeddings are stored in a Parquet file on Google Cloud Storage (`gs://openamend-data/MA_bill_embeddings.parquet`) alongside bill full text. The lightweight scored CSV (scores and cluster IDs only, no embeddings) is committed to this repository.

## Topic clustering

All lobbied bills with valid embeddings ({{ site.data.facts_lobbying.lobbying_n_clustered }} bills) are clustered into **25 topic groups** using the **k-means clustering** algorithm on the L2-normalised Gemini embeddings (cosine-space clustering). Each cluster is labelled using **Gemini 2.5 Flash**, which receives the 20 most central bill titles in the cluster and returns a 3–5 word topic label. Clustering is a one-time operation re-run manually when the historical data changes significantly.

| Cluster | Label | Bills | Env. bills |
|---------|-------|------:|----------:|{% for row in site.data.MA_bill_cluster_labels %}
| {{ row.cluster_id }} | {{ row.label }} | {{ row.n_bills }} | {{ row.n_env_bills }} |{% endfor %}

### Bill embedding space (t-SNE)

The plot below shows environmental bills projected into the policy landscape using [t-SNE](https://en.wikipedia.org/wiki/T-distributed_stochastic_neighbor_embedding). **Coloured, outlined dots** are the environmentally-relevant bills ({{ site.data.facts_lobbying.lobbying_n_env_bills }}), coloured by topic cluster; **grey dots** are a stratified background sample (~120 per cluster, ~3,000 total) providing geographic context. Hover over any point for the bill title.

Note: MA legislative bill embeddings are semantically dense — even after boilerplate stripping, mean inter-cluster cosine distance is only ~0.006 vs. mean intra-cluster spread of ~0.53. Visualising all {{ site.data.facts_lobbying.lobbying_n_bills_total }} bills produces a featureless blob because the underlying high-dimensional structure does not project cleanly to two dimensions. The subsample approach makes the environmentally-relevant bills legible without misrepresenting the cluster separation.

{% include charts/lobbying_bill_tsne.html %}

## Download archive

Full CSVs are stored in Google Cloud Storage (too large for the repository).
These links will be active once the initial full-history scrape is complete and uploaded:

* Lobbying employers (entity–client–year, with compensation) — `gs://openamend-data/MA_lobbying_employers.csv`
* Lobbying bills (entity–client–bill–year) — `gs://openamend-data/MA_lobbying_bills.csv`
* Lobbying bills scored (env relevance + cluster) — `gs://openamend-data/MA_lobbying_bills_scored.csv`
* Lobbyist↔entity mapping + salaries — `gs://openamend-data/MA_lobbying_lobbyists.csv`
* Campaign contributions (lobbyist → recipient) — `gs://openamend-data/MA_lobbying_campaign_contributions.csv`
* Itemized expenses (operating / meals-travel-entertainment / additional) — `gs://openamend-data/MA_lobbying_expenses.csv`
* Per-client annual amount + purpose text — `gs://openamend-data/MA_lobbying_client_purposes.csv`
* Legislature bill metadata — `gs://openamend-data/MA_legislature_bills.csv`
* [Bill embeddings (768-dim Parquet)](https://storage.googleapis.com/openamend-data/MA_bill_embeddings.parquet)

## Data tables

### Lobbying Employers

One row per (entity, client, year). Records how much each client paid each lobbying entity in a given year.

| Entity Name | Client Name | Year | Reg Type | Compensation |
| --- | --- | --- | --- | --- |{% for row in site.data.MA_lobbying_employers_sample limit:10 %}
| {{ row.entity_name }} | {{ row.client_name }} | {{ row.year }} | {{ row.reg_type }} | {{ row.compensation }} |{% endfor %}
{: .sortable}

### Lobbying Bills

One row per (entity, client, bill, session). Records which bills each entity lobbied on behalf of each client, with the lobbying position.

| Entity Name | Client Name | Year | Chamber | Bill | Bill Title | Position |
| --- | --- | --- | --- | --- | --- | --- |{% for row in site.data.MA_lobbying_bills_sample limit:10 %}
| {{ row.entity_name }} | {{ row.client_name }} | {{ row.year }} | {{ row.chamber }} | {{ row.bill_id }} | {{ row.bill_title | truncate: 60 }} | {{ row.position }} |{% endfor %}
{: .sortable}

### Legislature Bills

Bill metadata fetched from the [MA Legislature OpenAPI](https://malegislature.gov/api/swagger). Includes sponsor, final status, and derived `passed` boolean. Environmental relevance scores and cluster IDs are stored separately in `MA_lobbying_bills_scored.csv` (see above).

| Bill | General Court | Title | Sponsor | Status | Passed |
| --- | --- | --- | --- | --- | --- |{% for row in site.data.MA_legislature_bills_sample limit:10 %}
| {{ row.bill_id }} | {{ row.general_court }} | {{ row.title | truncate: 60 }} | {{ row.sponsor_name }} | {{ row.status | truncate: 40 }} | {{ row.passed }} |{% endfor %}
{: .sortable}

### Lobbyist–Entity Mapping

One row per (lobbyist, employing entity, year), with the salary the entity paid that lobbyist. The salary is an internal entity-to-lobbyist payment and is **separate** from client compensation above.

| Lobbyist | Entity | Year | Salary |
| --- | --- | --- | --- |{% for row in site.data.MA_lobbying_lobbyists_sample limit:10 %}
| {{ row.lobbyist_name }} | {{ row.entity_name }} | {{ row.year }} | {{ row.salary }} |{% endfor %}
{: .sortable}

### Campaign Contributions

Political contributions made by lobbyists, disclosed in their lobbying reports. One row per contribution.

| Lobbyist | Recipient | Office Sought | Date | Amount | Reporting Entity | Year |
| --- | --- | --- | --- | --- | --- | --- |{% for row in site.data.MA_lobbying_campaign_contributions_sample limit:10 %}
| {{ row.lobbyist_name }} | {{ row.recipient_name }} | {{ row.office_sought }} | {{ row.date }} | {{ row.amount }} | {{ row.entity_name }} | {{ row.year }} |{% endfor %}
{: .sortable}

### Expenses

Itemized lobbying expenses by type (`operating`, `meals_entertainment_travel`, `additional`). One row per expense; blank $0 template rows are excluded.

| Entity | Year | Type | Date | Payee | Description | Amount |
| --- | --- | --- | --- | --- | --- | --- |{% for row in site.data.MA_lobbying_expenses_sample limit:10 %}
| {{ row.entity_name }} | {{ row.year }} | {{ row.expense_type }} | {{ row.date }} | {{ row.payee }} | {{ row.description | truncate: 40 }} | {{ row.amount }} |{% endfor %}
{: .sortable}

### Client Purposes

Per-client annual summary: the annual amount a client paid and a free-text description of the lobbying purpose. One row per (entity, client, year).

| Entity | Client | Year | Amount | Purpose |
| --- | --- | --- | --- | --- |{% for row in site.data.MA_lobbying_client_purposes_sample limit:10 %}
| {{ row.entity_name }} | {{ row.client_name }} | {{ row.year }} | {{ row.amount }} | {{ row.purpose | truncate: 70 }} |{% endfor %}
{: .sortable}
