---
layout: post
title: "(DRAFT) Who lobbies the Massachusetts Legislature on environmental policy?"
ancillary: 0
---

*This post is in DRAFT status. Numbers and narrative claims will be filled in once the full historical lobbying dataset (2005–present) finishes scraping. Charts currently render against the partial dataset and will update automatically.*

Every employer that hires a lobbyist in Massachusetts is required to file public disclosures with the Secretary of State: who they retained, how much they paid, and which bills they tried to influence. The Secretary of State publishes these filings on the [Lobbyist Public Search portal](https://www.sec.state.ma.us/LobbyistPublicSearch/) going back to 2005. Across {{ site.data.facts_lobbying.lobbying_most_recent_year }}, **{{ site.data.facts_lobbying.lobbying_n_employers }} employers** disclosed lobbying activity totalling roughly **${{ site.data.facts_lobbying.lobbying_total_spend_latest | divided_by: 1000000 }}M**.

But what fraction of that money is spent on environmental policy? Which bills are environmentally relevant in the first place? And does lobbying intensity correlate with regulatory capacity — DEP staffing, enforcement actions, agency budget?

This post is the first systematic analysis of the MA environmental lobbying landscape. The underlying dataset is documented on the [MA lobbying data page]({{ site.baseurl }}/data/MA_lobbying.html); the [analysis code](https://github.com/nesanders/MAenvironmentaldata/blob/master/analysis/MA_lobbying_viz.py) and [scraping pipeline](https://github.com/nesanders/MAenvironmentaldata/blob/master/get_data/README_lobbying.md) are on GitHub. An interactive **[MA Lobbying Explorer](https://nsanders.me/ma_lobbying_explorer/)** lets you browse individual bills, employers, and lobbying firms with direct links to the Secretary of State filings.

---

## What counts as an "environmental" bill?

Filer-reported subject tags (e.g. "Energy & Environment") are unreliable: a utility lobbying a wastewater bill may tag it "Utilities & Energy"; a developer opposing wetlands reform may tag it "Land Use." Rather than trust the tags, we classify bills in two complementary ways:

1. **Embedding similarity score** — every bill's full text is embedded using Google's `gemini-embedding-2` model and scored by differential cosine similarity against reference sets of known environmental and non-environmental bills. A bill is flagged `is_environmental = True` when its similarity to env examples exceeds its similarity to non-env examples by at least 0.05.

2. **LLM classification** — a `gemini-2.5-flash` model summarizes each bill, assigns it to policy categories, and flags `is_env_llm = True` for bills it classifies as environmental. This approach captures more bills (3,521 vs ~700 at the embedding threshold) and provides structured tags (e.g. "Pollution control and abatement", "Renewable energy sources") that enable the category analysis below.

Methodology details and the cluster labelling pipeline are documented on the [data page]({{ site.baseurl }}/data/MA_lobbying.html#environmental-relevance-scoring).

### The policy landscape: env bills in context

The chart below projects every lobbied bill into 2-D using UMAP on bill embeddings. Environmental bills (LLM-identified) are shown as large outlined dots coloured by topic cluster; non-environmental bills are tiny grey background points that provide geographic context. Hover for bill titles.

{% include charts/lobbying_bill_tsne.html %}

*Caveat:* topic clusters reflect the dominant topic across all bills in the cluster. No cluster is purely environmental — environmentally-relevant bills are scattered across multiple topic clusters, with heavy concentrations in "Solid Waste Reduction and Recycling," "Massachusetts Clean Energy Transition," and "Local Clean Energy Transition."

---

## Environmental lobbying through the legislative sessions

The 9 legislative sessions in the dataset (the 186th through 194th General Courts, covering 2009–2026) show a dramatic upswing in both the number of environmental bills attracting lobbyist attention and the number of distinct employers engaging.

{% include charts/lobbying_gc_trend.html %}

The 186th General Court (2009–2010) saw just 134 unique environmental bills lobbied by 77 distinct employers. By the 192nd (2021–2022), those numbers had grown to 493 bills and 624 employers — roughly 4× more bills and 8× more employers. This expansion tracks the passage of major clean energy legislation (the 2021 Climate Act, the 2022 Climate Act II) and the broader mainstreaming of climate policy on Beacon Hill.

*Note: The employer count measures unique lobbying clients per session, not individuals. One trade association that lobbies 50 bills counts as one employer.*

### What types of environmental legislation attract lobbying?

The stacked bar below breaks the same sessions down by LLM-assigned policy category. Each bill may span multiple categories; a bill tagged both "Environmental Protection" and "Energy" is counted once per category.

{% include charts/lobbying_env_categories_by_gc.html %}

"Environmental Protection" dominates throughout, but the share of bills tagged "Energy" has grown substantially since GC190 (2017–2018), reflecting the increasing volume of clean energy legislation. "Public and Natural Resources" (land, water, fishing rights) contributes a steady third category.

---

## Who lobbies environmental bills — and how focused are they?

### The spectrum of environmental engagement

Not all lobbyists who touch environmental bills are primarily environmental advocates. Some file thousands of bills a year across every policy domain; a single environmental bill in their portfolio contributes only 0.04% of their activity. Others are single-issue advocates for whom every bill they file is environmental.

{% include charts/lobbying_employer_env_scatter.html %}

The scatter above plots each employer (with ≥10 total bills) by their total lobbying spend (x-axis) and the fraction of their bills that are environmental (y-axis). Bubble size scales with the number of environmental bills lobbied. A few observations:

- **High-spend, high-focus clients** (upper right) include renewable energy developers ([Orsted](https://nsanders.me/ma_lobbying_explorer/employers.html?name=orsted-wind-power-north-america-inc), [NextEra](https://nsanders.me/ma_lobbying_explorer/employers.html?name=nextera-energy-resources-llc), [Bloom Energy](https://nsanders.me/ma_lobbying_explorer/employers.html?name=bloom-energy)), transmission companies ([National Grid](https://nsanders.me/ma_lobbying_explorer/employers.html?name=national-grid), [Eversource](https://nsanders.me/ma_lobbying_explorer/employers.html?name=eversource)), and environmental advocates ([Conservation Law Foundation](https://nsanders.me/ma_lobbying_explorer/employers.html?name=conservation-law-foundation-inc), [Environmental League of Massachusetts](https://nsanders.me/ma_lobbying_explorer/employers.html?name=environmental-league-of-massachusetts)). These are the dominant players in environmental policy.
- **High-spend, low-focus clients** (lower right) include trade associations ([Associated Industries of Massachusetts](https://nsanders.me/ma_lobbying_explorer/employers.html?name=associated-industries-of-massachusetts-aim), [Massachusetts Chamber of Commerce](https://nsanders.me/ma_lobbying_explorer/employers.html?name=massachusetts-chamber-of-commerce)) that lobby comprehensively but spend a small fraction of their effort on environmental issues.
- **Low-spend, high-focus clients** (upper left) are often newer clean energy entrants and niche environmental advocacy groups — small shops with a specific environmental mandate.

### Top environmental lobbying spenders

Looking at cumulative allocated spend across all years: an employer's environmental lobbying budget is estimated as `total compensation × (env bills / all bills)`.

{% include charts/lobbying_top_env_employers.html %}

*[Once full historical data lands: are these primarily utilities, industry trade groups, environmental NGOs, or municipalities? What share of the top 20 are regulated entities vs. public-interest advocates?]*

---

## What gets lobbied — and how is it categorized?

### Top tags on environmental bills

The LLM assigns structured tags to each bill based on its content. Among the 3,521 environmental bills in the dataset, the most common tags are:

{% include charts/lobbying_top_env_tags.html %}

"Pollution control and abatement" (1,819 bills) and "Environmental regulatory procedures" (1,264 bills) together represent about half the corpus, reflecting the large volume of bills touching DEP's regulatory authority. "Renewable energy sources" (1,053) and "Energy efficiency and conservation" (979) together dominate a second major category — clean energy legislation.

---

## Who opposes whom?

Not all lobbying on environmental bills runs in the same direction. The position field in the SoS disclosures records whether each client disclosed "Support," "Oppose," or "Neutral." The chart below shows the 15 employer pairs most frequently found on opposite sides of the same environmental bill.

{% include charts/lobbying_opposition_pairs.html %}

The top opposition pairing — **[Associated Industries of Massachusetts (AIM)](https://nsanders.me/ma_lobbying_explorer/employers.html?name=associated-industries-of-massachusetts-aim) vs. [Environmental League of Massachusetts](https://nsanders.me/ma_lobbying_explorer/employers.html?name=environmental-league-of-massachusetts)** — appeared on opposite sides of 28 distinct environmental bills. AIM, as the major statewide business lobbying association, consistently opposes clean energy and environmental regulations it views as burdensome to industry. ELM is the state's largest environmental advocacy coalition. Their opposition is the defining fault line in MA environmental politics.

**[National Grid](https://nsanders.me/ma_lobbying_explorer/employers.html?name=national-grid)** appears repeatedly on the right side of these pairings — opposing clean energy advocates ([Northeast Clean Energy Council](https://nsanders.me/ma_lobbying_explorer/employers.html?name=northeast-clean-energy-council), [Vote Solar](https://nsanders.me/ma_lobbying_explorer/employers.html?name=vote-solar), [BCC Solar](https://nsanders.me/ma_lobbying_explorer/employers.html?name=bcc-solar)) and environmental groups. As a regulated distribution utility, National Grid has opposed some clean energy procurement requirements that would shift costs to ratepayers; it has also been a supporter of some climate legislation.

*Note: "opposing an environmental bill" does not always mean opposing environmental protection. A utility might oppose a clean energy bill it considers technically flawed; an environmental group might oppose a bill it considers inadequate. The chart reflects industry engagement patterns, not a simple pro/anti-environment score.*

### Unique clients by position on environmental bills

{% include charts/lobbying_env_positions.html %}

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

## Environmental bill lobbying spend by topic cluster

The next chart shows total annual lobbying spend allocated to environmental bills, stacked by topic cluster. Spend is allocated proportionally — if a client lobbied 10 bills in two different clusters, each cluster receives half the client's annual compensation.

{% include charts/lobbying_env_cluster_share.html %}

---

## Does lobbying intensity predict bill passage?

For each environmental bill, we count the number of distinct employers who lobbied it. Bills with more lobbyers tend to be higher-stakes — but is heavily-lobbied legislation more or less likely to pass?

{% include charts/lobbying_bill_pass_by_spend_tier.html %}

{% include charts/lobbying_pass_by_position.html %}

*[Once full historical data lands: interpret the tier and position comparisons. A higher pass rate among heavily-lobbied bills could indicate either successful industry influence or simply that important/well-supported bills attract more attention from all sides.]*

---

## CSO operators and lobbying

The Combined Sewer Overflow (CSO) dataset identifies {{ site.data.facts_EEA_CSO.n_operators }} permitted operators discharging untreated sewage into MA waterways. Some are municipalities (cities and towns); some are regional authorities (MWRA, Springfield Water and Sewer Commission). When CSO-related bills come before the Legislature, do these operators lobby — and how aggressively?

In practice, **most municipal CSO operators do not lobby directly** — they lobby through the [Massachusetts Municipal Association (MMA)](https://www.mma.org/) ([explorer](https://nsanders.me/ma_lobbying_explorer/employers.html?name=massachusetts-municipal-association)), which represents nearly all 351 MA cities and towns on Beacon Hill. The chart below shows direct lobbying spend by known CSO permittees alongside MMA as a proxy for the municipal sector. MMA totals reflect *all* of its lobbying activity (not only CSO-related bills), so it is best read as a ceiling on potential municipal-sector engagement on CSO policy rather than a measure of CSO-specific lobbying intensity.

{% include charts/lobbying_cso_operators.html %}

*[Once full historical data lands: which operators show consistent lobbying activity year over year? Do spend trends correlate with CSO enforcement events at the operator's facilities?]*

---

## Caveats and limitations

- **Spend allocation is approximate.** The SoS portal reports a single per-employer-per-period compensation figure, not per-bill spend. We allocate proportionally across the bills the employer disclosed lobbying. An employer who spends most of their effort on one priority bill but mentions ten others will have spend over-distributed to the secondary bills.
- **Environmental scoring (LLM) is a classification, not ground truth.** `is_env_llm = True` reflects a Gemini 2.5 Flash assessment of the bill summary — it is not a domain-expert label. The model may over-classify bills that use environmental language incidentally (e.g. a transportation bill that mentions air quality) and under-classify bills that affect the environment indirectly (e.g. a zoning reform). The dataset exposes both `env_relevance_score` (embedding similarity) and `is_env_llm` (LLM) so analysts can choose their own threshold or approach.
- **Legacy filings (pre-~2013) are coarser.** The pre-2013 portal format reports total compensation across all clients in one figure (no per-client breakdown) and sometimes omits bill titles. Bills with empty titles are present in the dataset but have zero embeddings (and thus `is_environmental = False`).
- **CSO operator matching is fuzzy.** Direct substring matching captures operators that lobby in their own name (e.g. MWRA, large independent water districts). MMA is included as an explicit proxy for the municipal sector, but its totals reflect *all* of its lobbying — not only CSO-related work. Operators that retain commercial lobbying firms cannot be attributed back to their underlying client from the SoS disclosure data alone.
- **The Legislature API does not serve pre-2009 bills.** For lobbying activity 2005–2008, bill titles come only from the SoS portal (often blank in the legacy format), so environmental scoring quality is reduced for those years.
- **General Court mapping has a known off-by-one bug.** The bill-fetching pipeline used `FIRST_GC_START_YEAR = 2005` (the correct value is 2003), which shifts every `general_court` assignment one session too low. The charts that use `general_court` from the parquet (which was fetched directly from the Legislature API) are unaffected. Charts that join lobbying disclosure years to legislature sessions via the year→GC formula may show session labels one off for pre-GC188 data.

---

## Reproducibility

All charts on this page are generated by [`analysis/MA_lobbying_viz.py`](https://github.com/nesanders/MAenvironmentaldata/blob/master/analysis/MA_lobbying_viz.py), which reads from the assembled SQLite database (`AMEND.db`) and the bill embeddings parquet. The embedding and LLM scoring pipeline is in [`get_data/score_lobbying_bills.py`](https://github.com/nesanders/MAenvironmentaldata/blob/master/get_data/score_lobbying_bills.py) and [`get_data/summarize_lobbying_bills.py`](https://github.com/nesanders/MAenvironmentaldata/blob/master/get_data/summarize_lobbying_bills.py); the clustering pipeline is in [`get_data/cluster_lobbying_bills.py`](https://github.com/nesanders/MAenvironmentaldata/blob/master/get_data/cluster_lobbying_bills.py). See [`get_data/README_lobbying.md`](https://github.com/nesanders/MAenvironmentaldata/blob/master/get_data/README_lobbying.md) for the full pipeline.

The complete bill embeddings (768-dimensional vectors plus full text) are persisted to `gs://openamend-data/MA_bill_embeddings.parquet` (~100 MB; not committed to the repo). A lightweight scored CSV without embeddings is committed at [`docs/data/MA_lobbying_bills_scored.csv`]({{ site.baseurl }}/data/MA_lobbying_bills_scored.csv).
