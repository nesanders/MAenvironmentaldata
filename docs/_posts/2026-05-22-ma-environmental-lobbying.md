---
layout: post
title: "Who lobbies the Massachusetts Legislature on environmental policy?"
ancillary: 0
---

*The [lobbying disclosure data used in this analysis]({{ site.url }}{{ site.baseurl }}/data/MA_lobbying.html) comes from the [Massachusetts Secretary of the Commonwealth's Lobbyist Public Search portal](https://www.sec.state.ma.us/LobbyistPublicSearch/), and is joined here against the [DEP staffing]({{ site.url }}{{ site.baseurl }}/data/MADEP_staff.html), [agency budget]({{ site.url }}{{ site.baseurl }}/data/ECOS_budget_history.html), and [sewage discharge]({{ site.url }}{{ site.baseurl }}/data/EEADP_all.html) datasets already archived in the [{{ site.data.site_config.site_abbrev }} database]({{ site.url }}{{ site.baseurl }}/data/index.html).*

*[The code needed to reproduce this analysis using {{ site.data.site_config.site_abbrev }} data can be viewed and downloaded here](https://github.com/nesanders/MAenvironmentaldata/blob/master/analysis/MA_lobbying_viz.py).*

Every employer that hires a lobbyist in Massachusetts is required to file public disclosures with the Secretary of the Commonwealth: who they retained, how much they paid, and which bills they tried to influence. The Secretary publishes these filings on the [Lobbyist Public Search portal](https://www.sec.state.ma.us/LobbyistPublicSearch/) going back to 2005. In {{ site.data.facts_lobbying.lobbying_most_recent_year }} alone, registered lobbyists and lobbying entities disclosed roughly **${{ site.data.facts_lobbying.lobbying_total_spend_latest | divided_by: 1000000 }} million** in client compensation; across the full {{ site.data.facts_lobbying.lobbying_first_year }}–{{ site.data.facts_lobbying.lobbying_most_recent_year }} period the total approaches **\${{ site.data.facts_lobbying.lobbying_total_spend_cumulative | divided_by: 1000000 }} million**.

In this post we ask a narrower question: how much of that activity concerns environmental policy? We first have to decide which bills are environmentally relevant in the first place, and then we can look at who lobbies them, how the landscape has changed over nearly two decades, and whether lobbying intensity moves together with the regulatory capacity — staffing and budget — of the agency that environmental law actually empowers, the [Department of Environmental Protection (DEP)]({{ site.url }}{{ site.baseurl }}/data/MADEP_staff.html).

The underlying dataset, including the full scraping and scoring methodology, is documented on the [MA lobbying data page]({{ site.url }}{{ site.baseurl }}/data/MA_lobbying.html).

---

## What counts as an "environmental" bill?

The subject tags that filers attach to their disclosures are unreliable for this purpose: a utility lobbying a wastewater bill may file it under "Utilities & Energy," while a developer opposing wetlands reform may file the same bill under "Land Use." Rather than trust those tags, we classify each lobbied bill directly from its text.

We do this with a large language model. A `gemini-2.5-flash` model reads each bill's title and full text (retrieved from the [MA Legislature OpenAPI](https://malegislature.gov/api/swagger)), writes a plain-English summary, assigns it to a fixed taxonomy of policy categories and tags, and judges whether the bill is environmentally relevant. We treat this LLM judgment as the classification of record: in spot-checks it identified clearly environmental bills — the bottle bill, net metering, renewable portfolio standards — that a purely embedding-based similarity score missed. Of the **{{ site.data.facts_lobbying.lobbying_n_bills_total }}** distinct bills lobbied across the period, **{{ site.data.facts_lobbying.lobbying_n_env_bills }}** (about {{ site.data.facts_lobbying.lobbying_env_pct }}%) are flagged environmental.

We also retain a secondary, embedding-based score for each bill — its differential cosine similarity to reference sets of known environmental and non-environmental bills — so that an analyst who prefers a continuous measure, or a different threshold, can use it. The full methodology, including the clustering pipeline, is documented on the [data page]({{ site.url }}{{ site.baseurl }}/data/MA_lobbying.html#environmental-relevance--taxonomy).

### The policy landscape

The chart below projects every lobbied bill into two dimensions using [t-SNE](https://en.wikipedia.org/wiki/T-distributed_stochastic_neighbor_embedding) on the bill embeddings. The environmental bills are drawn as large outlined dots coloured by topic cluster; the remaining bills are tiny grey background points that provide context. Hover over any point for the bill title.

{% include charts/lobbying_bill_tsne.html %}

We should be cautious in reading too much into the cluster geometry. Topic clusters reflect the dominant subject across all bills in the cluster, and no cluster is purely environmental — environmentally-relevant bills are scattered across several clusters, with the heaviest concentrations in the clean-energy and waste/recycling topic groups. MA legislative text is also unusually dense (bills share a great deal of boilerplate amendment language), so the two-dimensional projection compresses real structure; it is best read as a rough map rather than a precise one.

---

## Environmental lobbying through the legislative sessions

The number of environmental bills attracting lobbyist attention, and the number of distinct employers engaging on them, have both risen substantially over the period for which per-client data is available.

{% include charts/lobbying_gc_trend.html %}

In the {{ site.data.facts_lobbying_post.post_first_session_gc }} General Court ({{ site.data.facts_lobbying_post.post_first_session_years }}), **{{ site.data.facts_lobbying_post.post_first_session_env_bills }}** environmental bills were lobbied by **{{ site.data.facts_lobbying_post.post_first_session_employers }}** distinct employers. By the {{ site.data.facts_lobbying_post.post_recent_session_gc }} ({{ site.data.facts_lobbying_post.post_recent_session_years }}) — the most recent completed session — those figures had grown to **{{ site.data.facts_lobbying_post.post_recent_session_env_bills }}** bills and **{{ site.data.facts_lobbying_post.post_recent_session_employers }}** employers, roughly {{ site.data.facts_lobbying_post.post_env_bills_growth_x }}× and {{ site.data.facts_lobbying_post.post_employers_growth_x }}× their earlier levels. The trend tracks the arrival of major clean-energy and climate legislation on Beacon Hill over the 2010s and early 2020s, and the broader mainstreaming of climate policy as a subject of organized lobbying.

*Note: the employer count measures unique lobbying clients per session, not individual lobbyists. A trade association that lobbies fifty bills counts once. Compensation is reported per registrant per six-month period rather than per bill, so all spend figures below that are attributed to individual bills rest on a proportional allocation, described in the caveats.*

### What kinds of environmental legislation attract lobbying?

The stacked bar below breaks the same sessions down by LLM-assigned policy category. A bill may span more than one category, and is counted once in each it is assigned.

{% include charts/lobbying_env_categories_by_gc.html %}

"Environmental Protection" is the largest category throughout. The share tagged "Energy" has grown noticeably over the more recent sessions, consistent with the increasing volume of clean-energy legislation, and a steady third share concerns "Public and Natural Resources" — land, water, and fishing-rights bills.

---

## Who lobbies environmental bills, and how focused are they?

Not every employer that touches an environmental bill is primarily an environmental actor. Some file hundreds of bills a year across every policy domain, of which a single environmental bill is a small fraction; others are single-issue advocates for whom nearly every bill is environmental.

{% include charts/lobbying_employer_env_scatter.html %}

The scatter above plots each employer with at least ten total lobbied bills by their total lobbying spend (horizontal axis) and the fraction of their bills that are environmental (vertical axis); the size of each point scales with the number of environmental bills lobbied. Three groups stand out. In the upper right are high-spending, highly-focused clients — renewable-energy developers, the large electric and gas distribution utilities, and the major environmental advocacy organizations — the dominant repeat players in environmental policy. In the lower right are high-spending but low-focus clients, chiefly the broad business trade associations that lobby comprehensively and devote only a small share of their effort to environmental bills. In the upper left are lower-spending, highly-focused clients: newer clean-energy entrants and niche advocacy groups with a specific environmental mandate.

### Top environmental lobbying spenders

The chart below ranks employers by cumulative environmental lobbying spend, where an employer's environmental budget is estimated as their total compensation scaled by the fraction of their bills that are environmental.

{% include charts/lobbying_top_env_employers.html %}

The leaders are a mix of regulated entities — distribution utilities and energy developers with a direct financial stake in energy legislation — and public-interest advocates. That both appear near the top is itself the central feature of environmental lobbying: it is a contested arena, not a one-sided one.

---

## What gets lobbied, and how is it categorized?

The LLM assigns structured tags to each bill from a fixed taxonomy. Across the environmental bills, the most common tags concern pollution control and environmental regulatory procedure — reflecting the large volume of bills that touch DEP's regulatory authority — followed by renewable energy and energy efficiency, the clean-energy cluster.

{% include charts/lobbying_top_env_tags.html %}

---

## Who opposes whom?

Lobbying on environmental bills does not all run in the same direction. The position field in the disclosures records whether each client registered "Support," "Oppose," or "Neutral" on a given bill. By taking each environmental bill on which one client registered support and another registered opposition, we can count how often any two clients land on opposite sides. The chart below shows the fifteen employer pairs most frequently in direct opposition.

{% include charts/lobbying_opposition_pairs.html %}

The most frequent opposing pair is **{{ site.data.facts_lobbying_post.post_top_opposition_a }}** and **{{ site.data.facts_lobbying_post.post_top_opposition_b }}**, on opposite sides of **{{ site.data.facts_lobbying_post.post_top_opposition_bills }}** distinct environmental bills — an industry trade group and a public-interest advocacy organization recurring across the toxics, packaging, and consumer-protection bills where chemical and product regulation is at stake. More generally, the recurring pattern in these pairings is the large distribution utilities and statewide business associations on one side and clean-energy and environmental advocacy coalitions on the other.

It is worth stressing what this chart does and does not show. "Opposing an environmental bill" is not the same as opposing environmental protection: a utility may oppose a clean-energy bill it considers technically flawed or cost-shifting, and an environmental group may oppose a bill it considers too weak. The pairs reflect patterns of organized engagement, not a pro- or anti-environment score.

### Unique clients by position

{% include charts/lobbying_env_positions.html %}

---

## Lobbying spend and DEP capacity over time

The comparison this combined dataset most naturally enables is between lobbying activity on environmental bills and the regulatory capacity of DEP — both its budget and its staffing — over the same years. We make no causal claim here; the question is simply whether the two move together.

### Lobbying spend vs. DEP administrative budget

{% include charts/lobbying_spend_vs_budget.html %}

The DEP administrative budget is inflation-adjusted to recent dollars and is drawn from the MA Comptroller's [CTHRU]({{ site.url }}{{ site.baseurl }}/data/ECOS_budget_history.html) system back to FY2005, with earlier years from MassBudget's historical archive.

### Lobbying spend vs. DEP staffing

{% include charts/lobbying_spend_vs_staff.html %}

[DEP headcount]({{ site.url }}{{ site.baseurl }}/data/MADEP_staff.html) is the annual count of unique employees with non-zero payroll in the MA Comptroller's payroll dataset. The vertical axis is a raw count of employees; the lobbying-spend axis is in millions of dollars. The two series do not track each other in any simple way — lobbying activity has risen fairly steadily, while DEP staffing has been comparatively flat — which is itself consistent with our earlier finding that [DEP enforcement activity has not kept pace]({% post_url 2017-04-02-dep-enforcements %}) with the regulatory demands placed on the agency.

---

## Environmental lobbying spend by topic

The chart below shows total annual lobbying spend allocated to environmental bills, stacked by topic cluster. As above, spend is allocated proportionally: a client that lobbied bills in two clusters has its annual compensation split between them.

{% include charts/lobbying_env_cluster_share.html %}

The clean-energy and waste/recycling clusters account for a growing share of allocated environmental spend over time, mirroring the shift in the categories chart above.

---

## Does lobbying intensity predict bill passage?

For each environmental bill we can count the number of distinct employers who lobbied it. Bills that attract many lobbyers tend to be higher-stakes — but it is not obvious whether heavily-lobbied legislation is more or less likely to become law.

{% include charts/lobbying_bill_pass_by_spend_tier.html %}

{% include charts/lobbying_pass_by_position.html %}

The relationship is weak and should be read cautiously. A higher pass rate among heavily-lobbied bills, where it appears, is as consistent with the mundane explanation — important, broadly-supported bills draw attention from every side — as with any story about the effectiveness of industry influence. Passage in the Massachusetts Legislature is determined by many factors the disclosure data does not capture.

---

## CSO operators and lobbying

One of the environmental datasets already on this site is the record of [Combined Sewer Overflow (CSO) discharges]({{ site.url }}{{ site.baseurl }}/data/EEADP_all.html) — untreated and partially-treated sewage released into Massachusetts waterways, the subject of [earlier]({% post_url 2018-04-25-necir-cso-ej %}) [AMEND analyses]({% post_url 2023-10-20-eea-dp-cso-ej %}). The portal identifies {{ site.data.facts_lobbying_post.post_cso_n_operators }} permitted operators. When CSO-related bills come before the Legislature, do these operators lobby, and how aggressively?

In practice, most municipal CSO operators do not lobby in their own name. They lobby through the [Massachusetts Municipal Association (MMA)](https://www.mma.org/), which represents nearly all 351 cities and towns on Beacon Hill. The chart below shows direct lobbying spend by known CSO permittees alongside the MMA as a proxy for the municipal sector. The MMA totals reflect *all* of its lobbying activity, not only CSO-related bills, so they are best read as a ceiling on potential municipal engagement on CSO policy rather than a measure of CSO-specific intensity.

{% include charts/lobbying_cso_operators.html %}

The operators that do appear directly tend to be the larger regional authorities that retain their own lobbying capacity, rather than individual cities and towns.

---

## Caveats and limitations

- **Spend allocation is approximate.** The disclosures report a single compensation figure per registrant per six-month period, not per-bill spend. Where we attribute spend to individual bills we allocate it proportionally across the bills the registrant disclosed lobbying. A client who spent most of their effort on one priority bill but listed ten others will have spend over-distributed to the secondary bills. The aggregate spend totals are not affected by this — only the per-bill and per-cluster allocations are.
- **Environmental classification is a model judgment, not ground truth.** The `is_environmental` flag reflects a Gemini 2.5 Flash assessment of each bill, not a domain-expert label. The model can over-classify bills that use environmental language incidentally, and under-classify bills that affect the environment indirectly. We expose both the LLM flag and the embedding similarity score so that analysts can apply their own threshold.
- **The earliest years are coarser.** The 2005–2008 disclosure format reports a single salary total per registrant with no per-client breakdown, and frequently omits bill titles; the per-client analyses in this post therefore begin with the 2009–2010 session. The MA Legislature API likewise does not serve bills before 2009, so environmental classification for the earliest years relies on disclosure titles alone, which are often blank in the legacy format. Some lobbied bills appear with no resolvable title from either source; these remain in the dataset as real lobbying activity but cannot be summarized or classified.
- **CSO-operator matching is fuzzy.** Substring matching captures operators that lobby under their own name; the MMA is included as an explicit proxy for the municipal sector, but its totals cover all of its work. Operators that retain commercial lobbying firms cannot be traced back to their underlying client from the disclosure data alone.

---

## Reproducibility

All charts on this page are generated by [`analysis/MA_lobbying_viz.py`](https://github.com/nesanders/MAenvironmentaldata/blob/master/analysis/MA_lobbying_viz.py), which reads the assembled SQLite database (`AMEND.db`) and the bill embeddings parquet. The scraping pipeline, the embedding and LLM scoring in [`get_data/score_lobbying_bills.py`](https://github.com/nesanders/MAenvironmentaldata/blob/master/get_data/score_lobbying_bills.py) and [`get_data/summarize_lobbying_bills.py`](https://github.com/nesanders/MAenvironmentaldata/blob/master/get_data/summarize_lobbying_bills.py), and the clustering in [`get_data/cluster_lobbying_bills.py`](https://github.com/nesanders/MAenvironmentaldata/blob/master/get_data/cluster_lobbying_bills.py) are all documented in [`get_data/README_lobbying.md`](https://github.com/nesanders/MAenvironmentaldata/blob/master/get_data/README_lobbying.md).

The complete bill embeddings (768-dimensional vectors and full text) are persisted to `gs://openamend-data/MA_bill_embeddings.parquet` and are not committed to the repository; a lightweight scored CSV without embeddings is committed at [`docs/data/MA_lobbying_bills_scored.csv`]({{ site.url }}{{ site.baseurl }}/data/MA_lobbying_bills_scored.csv).
