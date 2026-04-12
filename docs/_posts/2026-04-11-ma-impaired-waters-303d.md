---
layout: post
title: "(DRAFT) MA Impaired Waters: Trends, Causes, and the CSO Connection"
ancillary: 0
---

*This post is in DRAFT status. It has not yet been fully completed and reviewed.*

Massachusetts has been formally identifying waterbodies that fail water quality standards since at least 2002. Under [Section 303(d) of the Clean Water Act](https://www.epa.gov/tmdl/overview-impaired-waters-and-total-maximum-daily-loads), states must submit a biennial **Integrated List of Waters** to EPA identifying every waterbody that fails to meet its water quality standards — and for each one, develop a **Total Maximum Daily Load (TMDL)**, a legally binding cleanup plan specifying the maximum pollutant load a waterbody can receive and still meet standards.

This dataset is the primary outcome measure that AMEND has been missing. Previous analyses tracked DEP staffing, enforcement, and CSO discharges — the regulatory *inputs*. The 303(d) list tells us something different: **is the environment actually getting better?**

The data used here comes from [MassGIS](https://www.mass.gov/info-details/massgis-data-massdep-2022-integrated-list-of-waters-305b303d), which publishes each approved reporting cycle as GIS shapefiles with associated attribute tables. Available cycles: 2010, 2012, 2014, 2016, 2018, and 2022 (the 2020 cycle was never published by MassGIS). In total, this analysis covers {{ site.data.facts_EPA303d.n_cycles }} reporting cycles over twelve years.

*[The code needed to reproduce this analysis using {{ site.data.site_config.site_abbrev }} data can be viewed and downloaded here](https://github.com/nesanders/MAenvironmentaldata/blob/master/analysis/EPA_303d_viz.py)*

---

## Background: What Are 303(d) Impaired Waters?

A **303(d) listing** means a waterbody has failed to meet its designated use standards even after technology-based pollution controls are applied. Designated uses define the intended purpose of a waterbody — for example: swimming (recreation), aquatic life, fish consumption, or drinking water supply.

Each waterbody is assessed at the level of an **Assessment Unit (AU)**: a discrete, named segment of a waterbody with its own unique identifier. A single river may have multiple AUs assessed independently.

The assessment uses five categories:

| Category | Meaning |
|----------|---------|
| 1 | Fully supporting all designated uses |
| 2 | Attaining standards (minor concerns) |
| 3 | Insufficient information to assess |
| 4A | Impaired — TMDL completed and approved |
| 4B/4C | Impaired — addressed through other control plans |
| 5 | Impaired — TMDL needed (the "303(d) list" proper) |

In this analysis, "impaired" includes all of Categories 4A, 4B, 4C, and 5 — waterbodies that are confirmed to be failing, regardless of whether a cleanup plan exists.

When a waterbody is listed as Category 5, DEP and EPA are legally required to develop and approve a TMDL before any further water quality improvements can be permitted. The TMDL process typically takes years to complete.

---

## Are MA's Impaired Waters Getting Better?

The short answer: no. Over the six reporting cycles in this dataset, the count of impaired assessment units has grown in every single cycle — from {{ site.data.facts_EPA303d.impaired_earliest }} impaired AUs in {{ site.data.facts_EPA303d.earliest_cycle }} to {{ site.data.facts_EPA303d.impaired_latest }} in {{ site.data.facts_EPA303d.latest_cycle }}, a {{ site.data.facts_EPA303d.impaired_pct_change }}% increase.

{% include charts/EPA303d_impaired_trend.html %}

Some caution is warranted in interpreting this trend. Over time, MA DEP has expanded its assessment coverage and updated its criteria — more comprehensive assessments naturally identify more impaired waters. The growth in the impaired count may partly reflect better monitoring rather than actual environmental deterioration. The most defensible interpretation is that the count of impaired AUs has not meaningfully declined over the period for which data is available.

The dominant water types are rivers and freshwater lakes, which together account for the majority of impaired AUs in every cycle. Estuaries — coastal mixing zones where rivers meet the ocean — represent a smaller but ecologically important category that appears in the data beginning with later cycles as assessment coverage expanded.

---

## What Is Causing Impairment?

The 2022 cycle, which is the most recent available, identifies over 90 distinct causes of impairment across Massachusetts waterbodies. The most widespread causes are bacterial indicators — both fecal coliform and *E. coli* — followed by dissolved oxygen, non-native aquatic plants, mercury in fish tissue, and nutrients (phosphorus, nitrogen).

{% include charts/EPA303d_causes_breakdown.html %}

The dominance of bacterial indicators ({{ site.data.facts_EPA303d.top_cause_1_n }} AUs for {{ site.data.facts_EPA303d.top_cause_1 }}, {{ site.data.facts_EPA303d.top_cause_2_n }} AUs for {{ site.data.facts_EPA303d.top_cause_2 }}) points directly to sewage-related pollution as the leading cause of water quality failure in Massachusetts. Bacteria from human waste are the primary criterion for beach and fishing closures, and are the most immediately visible consequence of combined sewer overflows (CSOs) and sanitary sewer overflows (SSOs).

**Dissolved oxygen** ({{ site.data.facts_EPA303d.top_cause_3_n }} AUs) impairment is caused by excess nutrient loading — primarily nitrogen and phosphorus — which fuels algal blooms. When algae die and decompose, the bacterial decomposition process depletes oxygen, suffocating aquatic life. Sewage and stormwater runoff from fertilized land are primary nutrient sources.

**Mercury in fish tissue** reflects decades of atmospheric deposition from coal combustion and industrial emissions — a legacy contamination problem that persists long after the original source is controlled.

**Non-native aquatic plants** (particularly fanwort, *Cabomba caroliniana*) represent a distinct category: ecological impairment from invasive species introduction rather than pollution. Their widespread appearance in the top causes reflects the scale of the problem in MA lakes and ponds.

---

## The Sewage Connection: Do CSO Operators Discharge Into Already-Impaired Waters?

One of the most consequential questions AMEND can now answer with this data: when CSO operators discharge untreated sewage during rain events, are they discharging into waterbodies that are *already* failing water quality standards?

To answer this, we linked the [MA EEA Data Portal CSO discharge records]({{ site.url }}{{ site.baseurl }}/data/EEADP_all.html) — covering June 2022 through present — to 303(d) status for each receiving waterway using a manually verified mapping table. The mapping covers {{ site.data.facts_EPA303d.n_cso_mapped }} of the {{ site.data.facts_EPA303d.n_cso_unique_wb }} distinct CSO-reporting waterways in the EEA Data Portal. Unmatched waterways are shown separately.

{% include charts/EPA303d_cso_impaired.html %}

The result is striking: **{{ site.data.facts_EPA303d.pct_vol_impaired_of_matched }}% of matched CSO discharge volume goes to waterbodies rated "Not Supporting" in the most recent 303(d) cycle.** Across all years of CSO data, {{ site.data.facts_EPA303d.vol_not_supporting_bgal }} billion gallons of discharge flowed into waterbodies already confirmed to be failing water quality standards. Every single one of the 35 matched CSO-reporting waterways is classified as "Not Supporting" at least one designated use.

Of the {{ site.data.facts_EPA303d.vol_total_bgal }} billion gallons of total reported CSO discharge, {{ site.data.facts_EPA303d.pct_vol_impaired_of_total }}% goes to matched impaired waterways, with the remaining {{ site.data.facts_EPA303d.vol_not_matched_bgal }} billion gallons discharged to waterways we could not match to a 303(d) record.

This finding does not prove that CSOs *caused* the 303(d) listings — the impairment assessments reflect a broad range of pollution sources, and the correlation between CSO locations and impaired waters could reflect the simple fact that both are concentrated in urban and industrial watersheds. But it does establish that there is minimal separation between where Massachusetts's sewage overflows and where its most degraded waters are. Massachusetts is not discharging into clean waters and getting away with it — it is discharging into waterbodies that are already failing the standards that define what "clean water" means under federal law.

---

## Are Cleanup Plans Being Completed? TMDL Progress

For every impaired waterbody in Category 5, MA DEP and EPA must develop a TMDL — a cleanup plan specifying the maximum allowable pollutant loads. This is a legally required step before water quality can improve.

{% include charts/EPA303d_tmdl_trend.html %}

Progress has been limited. In {{ site.data.facts_EPA303d.earliest_cycle }}, {{ site.data.facts_EPA303d.tmdl_with_earliest }} of {{ site.data.facts_EPA303d.impaired_earliest }} impaired AUs had a completed TMDL ({{ site.data.facts_EPA303d.tmdl_pct_earliest }}%). In {{ site.data.facts_EPA303d.latest_cycle }}, that fraction was {{ site.data.facts_EPA303d.tmdl_with_latest }} of {{ site.data.facts_EPA303d.impaired_latest }} ({{ site.data.facts_EPA303d.tmdl_pct_latest }}%).

In absolute terms, the number of AUs *without* a cleanup plan grew from {{ site.data.facts_EPA303d.tmdl_without_earliest }} to {{ site.data.facts_EPA303d.tmdl_without_latest }} — an increase of {{ site.data.facts_EPA303d.tmdl_without_latest | minus: site.data.facts_EPA303d.tmdl_without_earliest }} AUs with no plan. The number of AUs *with* a plan did grow (from {{ site.data.facts_EPA303d.tmdl_with_earliest }} to {{ site.data.facts_EPA303d.tmdl_with_latest }}), but this growth was outpaced by the expansion of the impaired list itself.

The geographic pattern of TMDL completion matters. Not all watershed programs move at the same pace. The map below shows, by watershed, how many impaired AUs have a completed TMDL versus how many are still waiting. Circle size reflects the count of impaired AUs; color reflects the fraction with a TMDL (green ≥ 50%, orange 25–49%, red < 25%).

<iframe src="{{ site.url }}{{ site.baseurl }}/assets/maps/EPA303d_tmdl_map.html" 
        width="100%" height="480" frameborder="0" scrolling="no"
        style="border:1px solid #ccc;border-radius:4px;margin:1em 0;"></iframe>

---

## Watershed Breakdown

Impairment is not evenly distributed. The watersheds with the most impaired assessment units in 2022 include both urbanized areas (where CSO and industrial discharges are concentrated) and coastal watersheds (Cape Cod, Buzzards Bay) where nitrogen loading from septic systems and land-based runoff is the primary driver.

{% include charts/EPA303d_watershed_impairment.html %}

Cape Cod's high rank reflects its shallow, nutrient-sensitive coastal ponds and estuaries, where dense development and aging septic systems have created widespread nitrogen impairment. Buzzards Bay and the South Coastal watershed face similar pressure from nitrogen and bacterial loading. The Taunton and Blackstone watersheds reflect more urban and industrial stressors.

---

## Conclusions

**Impaired water counts have grown every cycle, not declined.** Despite decades of investment in water quality programs, the count of assessment units rated as impaired has increased by {{ site.data.facts_EPA303d.impaired_pct_change }}% between {{ site.data.facts_EPA303d.earliest_cycle }} and {{ site.data.facts_EPA303d.latest_cycle }}. Some of this increase reflects expanded assessment coverage; none of it reflects a confirmed cleanup trend.

**Bacteria from sewage is the leading cause of impairment.** Fecal coliform and *E. coli* together account for the most commonly cited impairment cause, directly implicating sewage — from CSOs, SSOs, failing septic systems, and stormwater — as the dominant driver of Massachusetts water quality failure.

**CSO discharges are concentrated in already-impaired waters.** Every CSO-reporting waterway for which we have a 303(d) match is classified as "Not Supporting" at least one designated use. Seventy-five percent of all reported CSO discharge volume, by our calculation, flows into confirmed-impaired receiving waters. This is not a coincidence; it reflects the geographic concentration of aging combined sewer infrastructure in the same urban waterways that have been impaired for decades.

**TMDL completion has not kept pace with impairment growth.** The fraction of impaired AUs with a completed cleanup plan has remained roughly flat at ~38–40% for twelve years. The absolute number of AUs lacking a plan has grown. The legal mechanism for driving cleanup — the TMDL requirement — is not being deployed fast enough to turn the tide.

**The next cycle will be critical.** Massachusetts's 2024 Integrated List is currently in draft as of spring 2026, with EPA approval expected within the next 12–18 months. When it is approved and published by MassGIS, this analysis will update automatically. That cycle will be the first to reflect conditions after several recent years of high CSO discharge volume, and will be watched closely as an early indicator of whether recent infrastructure investments are yielding measurable improvements.

---

*This post was prepared with assistance from [Claude](https://www.anthropic.com/claude), an AI assistant, which helped structure the analysis, write code, and draft text. All data, methodology, and conclusions were reviewed and approved by [the site author](https://github.com/nesanders).*
