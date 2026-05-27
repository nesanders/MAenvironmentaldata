---
layout: post
title: "(DRAFT) Who lobbies the Massachusetts Legislature on environmental policy?"
ancillary: 0
---

*This post is in DRAFT status. Numbers and narrative claims will be filled in once the full historical lobbying dataset (2005–present) finishes scraping. Charts currently render against the partial dataset and will update automatically.*

Every employer that hires a lobbyist in Massachusetts is required to file public disclosures with the Secretary of State: who they retained, how much they paid, and which bills they tried to influence. The Secretary of State publishes these filings on the [Lobbyist Public Search portal](https://www.sec.state.ma.us/LobbyistPublicSearch/) going back to 2005. Across {{ site.data.facts_lobbying.lobbying_most_recent_year }}, **{{ site.data.facts_lobbying.lobbying_n_employers }} employers** disclosed lobbying activity totalling roughly **${{ site.data.facts_lobbying.lobbying_total_spend_latest | divided_by: 1000000 }}M**.

But what fraction of that money is spent on environmental policy? Which bills are environmentally relevant in the first place? And does lobbying intensity correlate with regulatory capacity — DEP staffing, enforcement actions, agency budget?

This post is the first systematic analysis of the MA environmental lobbying landscape. The underlying dataset is documented on the [MA lobbying data page]({{ site.baseurl }}/data/MA_lobbying.html); the [analysis code](https://github.com/nesanders/MAenvironmentaldata/blob/master/analysis/MA_lobbying_viz.py) and [scraping pipeline](https://github.com/nesanders/MAenvironmentaldata/blob/master/get_data/README_lobbying.md) are on GitHub.

---

## What counts as an "environmental" bill?

Filer-reported subject tags (e.g. "Energy & Environment") are unreliable: a utility lobbying a wastewater bill may tag it "Utilities & Energy"; a developer opposing wetlands reform may tag it "Land Use." Rather than trust the tags, we **embed the full text of each bill** using Google's `gemini-embedding-2` model and score it by **differential cosine similarity** against two reference sets of 20 real MA bills each — one set known to be environmental (PFAS, stormwater, clean energy, etc.), one set known not to be (health, labor, education). A bill is flagged `is_environmental = True` when its similarity to env examples exceeds its similarity to non-env examples by at least 0.05.

Methodology details and the cluster labelling pipeline are documented on the [data page]({{ site.baseurl }}/data/MA_lobbying.html#environmental-relevance-scoring).

To visualise the result, every lobbied bill is projected into 2-D via t-SNE and coloured by its k-means topic cluster. Environmental bills are shown as large outlined dots; non-environmental bills are smaller and muted. Hover for the title.

{% include charts/lobbying_bill_tsne.html %}

*Caveat:* topic clusters reflect the dominant topic across all bills in the cluster. No cluster is purely environmental — environmentally-relevant bills are scattered across multiple topic clusters, including a heavy concentration in the "Health, Climate, and Community" cluster.

---

## How much does environmental lobbying cost?

The next chart shows total annual lobbying spend by employers who lobbied at least one environmentally-relevant bill, broken down by topic cluster. Stacked bar height represents allocated spend ($M); allocation distributes each employer's annual total proportionally across the bills they lobbied that year, so a single employer who lobbied 10 bills in different clusters contributes 1/10 of its total to each.

{% include charts/lobbying_env_cluster_share.html %}

*[Once full historical data lands: which cluster dominates? Are clean-energy bills lobbied at the same intensity as health-environment bills? How has the mix shifted from 2005 to 2024?]*

---

## Who are the biggest environmental lobbying spenders?

The cumulative spend below is calculated as `(employer total compensation that year) × (share of that employer's bills flagged environmental)`. This share-weighted measure means an employer that lobbied 100 bills, 5 of which were environmental, contributes 5% of their annual spend to the env total.

{% include charts/lobbying_top_env_employers.html %}

*[Once full historical data lands: are these primarily utilities, industry trade groups, environmental NGOs, or municipalities? What share of the top 20 are regulated entities vs. public-interest advocates?]*

---

## Lobbying spend vs. DEP capacity over time

The strongest cross-dataset comparison this dataset enables is between **industry lobbying spend on environmental bills** and the **regulatory capacity of the Department of Environmental Protection (DEP)** — both its budget and its staffing levels — over time.

### Lobbying spend vs. DEP administrative budget

{% include charts/lobbying_spend_vs_budget.html %}

The DEP administrative budget is inflation-adjusted (2024 dollars) and sourced from the MA Comptroller's CTHRU system back to FY2005, with earlier years from MassBudget's historical archive. See the [DEP budget data page]({{ site.baseurl }}/data/EEA_budget.html) for methodology.

### Lobbying spend vs. DEP staffing

{% include charts/lobbying_spend_vs_staff.html %}

DEP headcount is the annual count of unique employees with non-zero payroll in the MA Comptroller's payroll dataset (CTHRU-based). The y-axis is a raw FTE count; the lobbying spend axis is in millions of dollars.

*[Once full historical data lands: do these series correlate? Does lobbying ramp up in years when DEP staffing is cut? Or is there a lag — does lobbying intensity precede or follow regulatory rollbacks?]*

---

## Does lobbying intensity predict bill passage?

For each environmental bill, we count the number of distinct employers who lobbied it. Bills with more lobbyers tend to be higher-stakes — but is heavily-lobbied legislation more or less likely to pass?

{% include charts/lobbying_bill_pass_by_spend_tier.html %}

*[Once full historical data lands: interpret the tier comparison. A higher pass rate among heavily-lobbied bills could indicate either successful industry influence or simply that important/well-supported bills attract more attention from all sides.]*

---

## CSO operators and lobbying

The Combined Sewer Overflow (CSO) dataset identifies {{ site.data.facts_EEA_CSO.n_operators }} permitted operators discharging untreated sewage into MA waterways. Some are municipalities (cities and towns); some are regional authorities (MWRA, Springfield Water and Sewer Commission). When CSO-related bills come before the Legislature, do these operators lobby — and how aggressively?

In practice, **most municipal CSO operators do not lobby directly** — they lobby through the [Massachusetts Municipal Association (MMA)](https://www.mma.org/), which represents nearly all 351 MA cities and towns on Beacon Hill. The chart below shows direct lobbying spend by known CSO permittees alongside MMA as a proxy for the municipal sector. MMA totals reflect *all* of its lobbying activity (not only CSO-related bills), so it is best read as a ceiling on potential municipal-sector engagement on CSO policy rather than a measure of CSO-specific lobbying intensity.

{% include charts/lobbying_cso_operators.html %}

*[Once full historical data lands: which operators show consistent lobbying activity year over year? Do spend trends correlate with CSO enforcement events at the operator's facilities?]*

---

## Caveats and limitations

- **Spend allocation is approximate.** The SoS portal reports a single per-employer-per-period compensation figure, not per-bill spend. We allocate proportionally across the bills the employer disclosed lobbying. An employer who spends most of their effort on one priority bill but mentions ten others will have spend over-distributed to the secondary bills.
- **Environmental scoring is a similarity score, not a label.** A bill flagged `is_environmental = True` is more textually similar to known env bills than to known non-env bills — it is not a domain-expert classification. We expose `env_relevance_score` so downstream analysts can choose their own threshold; the current default (0.05 differential) is calibrated for high recall and accepts some false positives.
- **Legacy filings (pre-~2013) are coarser.** The pre-2013 portal format reports total compensation across all clients in one figure (no per-client breakdown) and sometimes omits bill titles. Bills with empty titles are present in the dataset but have zero embeddings (and thus `is_environmental = False`).
- **CSO operator matching is fuzzy.** Direct substring matching captures operators that lobby in their own name (e.g. MWRA, large independent water districts). MMA is included as an explicit proxy for the municipal sector, but its totals reflect *all* of its lobbying — not only CSO-related work. Operators that retain commercial lobbying firms cannot be attributed back to their underlying client from the SoS disclosure data alone.
- **The Legislature API does not serve pre-2009 bills.** For lobbying activity 2005–2008, bill titles come only from the SoS portal (often blank in the legacy format), so environmental scoring quality is reduced for those years.

---

## Reproducibility

All charts on this page are generated by [`analysis/MA_lobbying_viz.py`](https://github.com/nesanders/MAenvironmentaldata/blob/master/analysis/MA_lobbying_viz.py), which reads exclusively from the assembled SQLite database (`AMEND.db`). The scoring pipeline is in [`get_data/score_lobbying_bills.py`](https://github.com/nesanders/MAenvironmentaldata/blob/master/get_data/score_lobbying_bills.py); the clustering pipeline is in [`get_data/cluster_lobbying_bills.py`](https://github.com/nesanders/MAenvironmentaldata/blob/master/get_data/cluster_lobbying_bills.py). See [`get_data/README_lobbying.md`](https://github.com/nesanders/MAenvironmentaldata/blob/master/get_data/README_lobbying.md) for the full pipeline.

The complete bill embeddings (768-dimensional vectors plus full text) are persisted to `gs://openamend-data/MA_bill_embeddings.parquet` (~100 MB; not committed to the repo). A lightweight scored CSV without embeddings is committed at [`docs/data/MA_lobbying_bills_scored.csv`]({{ site.baseurl }}/data/MA_lobbying_bills_scored.csv).
