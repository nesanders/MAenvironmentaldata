---
layout: post
title: "(DRAFT) MA Impaired Waters: Trends, Causes, and the CSO Connection"
ancillary: 0
---

*This post is in DRAFT status. It has not yet been fully completed and reviewed.*

> **Recent development:** In April 2025, EPA finalized a [Statewide Total Maximum Daily Load for Pathogen-Impaired Waters](https://www.epa.gov/system/files/documents/2025-04/final-ma-statewide-tmdl-pathogen-impaired-waters.pdf) in Massachusetts — a single framework cleanup plan covering all waterbodies impaired by fecal coliform and *E. coli*. Because bacterial contamination is the most common cause of impairment in the state, this action could formally resolve the TMDL requirement for hundreds of assessment units. Whether it leads to measurable improvements in water quality depends on subsequent permit revisions, infrastructure investment, and enforcement. The data below reflects conditions through the 2022 reporting cycle, before this statewide TMDL was finalized.

Massachusetts has been [formally identifying](https://www.epa.gov/tmdl/region-1-approved-tmdls-state#tmdl-ma) (see also the [state TMDL   website](https://www.mass.gov/total-maximum-daily-loads-tmdls)) waterbodies that fail water quality standards since at least 2000. Under [Section 303(d) of the Clean Water Act](https://www.epa.gov/tmdl/overview-listing-impaired-waters-under-cwa-section-303d), states must submit a biennial ["303(d) list"](https://www.epa.gov/tmdl/impaired-waters-restoration-process-listing)] to EPA identifying every waterbody that fails to meet its water quality standards — and for each, develop a [**Total Maximum Daily Load (TMDL)**](https://www.epa.gov/tmdl/overview-total-maximum-daily-loads-tmdls), a cleanup plan specifying the maximum pollutant load a waterbody can receive and still meet standards.

The 303(d) list is an important complement to data on regulatory activity (permitting, inspections, enforcement): it reflects measured environmental conditions rather than government actions. The data used here comes from [MassGIS](https://www.mass.gov/info-details/massgis-data-massdep-2022-integrated-list-of-waters-305b303d), which publishes each approved reporting cycle as GIS shapefiles with associated attribute tables. So far, the available reporting cycles are 2010, 2012, 2014, 2016, 2018, and 2022 (the 2020 cycle was never published by MassGIS). This analysis thus covers {{ site.data.facts_EPA303d.n_cycles }} reporting cycles spanning twelve years.

*[The code used to produce this analysis can be viewed and downloaded here](https://github.com/nesanders/MAenvironmentaldata/blob/master/analysis/EPA_303d_viz.py)*

---

## Background: What Are 303(d) Impaired Waters?

A **303(d) listing** means a waterbody has failed to meet its designated use standards even after technology-based pollution controls are applied. Designated uses define the intended purpose of a waterbody — for example: swimming (recreation), aquatic life, fish consumption, or drinking water supply.

Each waterbody is assessed at the level of an **Assessment Unit (AU)**: a discrete, named segment of a waterbody with its own unique identifier. A single river may have multiple AUs assessed independently.

The assessment uses five [categories](https://floridadep.gov/dear/watershed-assessment-section/content/impaired-waters-listing-process#:~:text=What%20are%20the%20assessment%20categories):

| Category | Meaning |
|----------|---------|
| 1 | Fully supporting all designated uses |
| 2 | Attaining standards (minor concerns) |
| 3 | Insufficient information to assess |
| 4A | Impaired — TMDL completed and approved |
| 4B | Impaired — addressed through other control plans |
| 4C | Impaired by non-CWA pollutant (no TMDL required) |
| 5 | Impaired — TMDL needed (the "303(d) list" proper) |

In this analysis, "impaired" includes all of Categories 4A, 4B, 4C, and 5 — waterbodies confirmed to be failing at least one designated use, regardless of whether a cleanup plan exists.

When a waterbody is listed as Category 5, DEP and EPA are legally required to develop and approve a TMDL. The TMDL process typically takes years to complete.

---

## Trends in Impaired Water Counts

The count of impaired assessment units has grown in each reporting cycle, from {{ site.data.facts_EPA303d.impaired_earliest }} impaired AUs in {{ site.data.facts_EPA303d.earliest_cycle }} to {{ site.data.facts_EPA303d.impaired_latest }} in {{ site.data.facts_EPA303d.latest_cycle }}, a {{ site.data.facts_EPA303d.impaired_pct_change }}% increase.

{% include charts/EPA303d_impaired_trend.html %}

In physical terms, impaired river segments grew from {{ site.data.facts_EPA303d.river_miles_earliest }} to {{ site.data.facts_EPA303d.river_miles_latest }} miles over this period (a {{ site.data.facts_EPA303d.river_miles_pct_change }}% increase), and impaired lake area grew from {{ site.data.facts_EPA303d.lake_acres_earliest }} to {{ site.data.facts_EPA303d.lake_acres_latest }} acres.

One question in interpreting this trend is whether the growth reflects actual deterioration or expanded assessment coverage — MA DEP assesses more waterbodies over time, which could mechanically increase the count. Looking at the persistence of existing listings helps address this. Of the {{ site.data.facts_EPA303d.impaired_earliest }} AUs impaired in {{ site.data.facts_EPA303d.earliest_cycle }}, {{ site.data.facts_EPA303d.n_persistent }} ({{ site.data.facts_EPA303d.pct_persistent }}%) remained impaired through {{ site.data.facts_EPA303d.latest_cycle }}. Only {{ site.data.facts_EPA303d.n_delisted }} ({{ site.data.facts_EPA303d.pct_delisted }}%) were delisted over the twelve-year period. The overall growth in the list is primarily driven by the addition of newly assessed AUs rather than by recovery of previously listed ones.

The dominant water types are rivers and freshwater lakes, which together account for the majority of impaired AUs in every cycle. 573 impaired freshwater lakes and 366 impaired river AUs were present in 2010, growing to 648 and 620, respectively, in 2026. Estuaries are the third largest category — 239 impaired estuary AUs were recorded in 2010, growing to 296 in 2022. Rivers therefore had the greatest growth in recorded impaired AUs over this period.

---

## How Many Impaired Waters Have Been Delisted?

Of the {{ site.data.facts_EPA303d.impaired_earliest }} waterbody segments listed as impaired in {{ site.data.facts_EPA303d.earliest_cycle }}, {{ site.data.facts_EPA303d.n_in_all_cycles }} appear as impaired in all six reporting cycles — continuously listed for at least twelve years. The chart below tracks that original {{ site.data.facts_EPA303d.earliest_cycle }} cohort alongside AUs first listed in later cycles.

{% include charts/EPA303d_persistence.html %}

Over twelve years, {{ site.data.facts_EPA303d.n_delisted }} AUs were removed from the impaired list — {{ site.data.facts_EPA303d.pct_delisted }}% of those impaired in {{ site.data.facts_EPA303d.earliest_cycle }}. During the same period, {{ site.data.facts_EPA303d.n_newly_added }} AUs were added.

The {{ site.data.facts_EPA303d.n_delisted }} AUs that left the impaired list fall into three categories based on their status in the 2022 data. Each is shown in a separate table below. Click any column header to sort.

<style>
.delisted-tbl th { cursor:pointer; user-select:none; }
.delisted-tbl th::after { content:' ⇅'; font-size:0.75em; opacity:0.4; }
.delisted-tbl th.asc::after { content:' ↑'; opacity:1; }
.delisted-tbl th.desc::after { content:' ↓'; opacity:1; }
</style>
<script>
(function(){
  function makeSortable(tbl) {
    var ths = tbl.querySelectorAll('thead th');
    var sortCol = -1, sortAsc = true;
    ths.forEach(function(th, ci){
      th.addEventListener('click', function(){
        var tbody = tbl.querySelector('tbody');
        var rows = Array.from(tbody.querySelectorAll('tr'));
        sortAsc = (sortCol === ci) ? !sortAsc : true;
        sortCol = ci;
        ths.forEach(function(h){ h.classList.remove('asc','desc'); });
        th.classList.add(sortAsc ? 'asc' : 'desc');
        rows.sort(function(a, b){
          var av = a.cells[ci].textContent.trim();
          var bv = b.cells[ci].textContent.trim();
          var an = parseFloat(av), bn = parseFloat(bv);
          var cmp = (!isNaN(an) && !isNaN(bn)) ? an - bn : av.localeCompare(bv);
          return sortAsc ? cmp : -cmp;
        });
        rows.forEach(function(r){ tbody.appendChild(r); });
      });
    });
  }
  document.addEventListener('DOMContentLoaded', function(){
    document.querySelectorAll('.delisted-tbl').forEach(makeSortable);
  });
})();
</script>

{{ site.data.facts_EPA303d.n_delisted_removed }} AUs no longer appear in the 2022 assessment data at all. These may have been consolidated into differently numbered assessment units, removed from the assessment universe, or in some cases genuinely improved to the point of no longer requiring listing.

<details>
<summary>Removed from assessment entirely — {{ site.data.facts_EPA303d.n_delisted_removed }} assessment units</summary>
<div style="max-height:360px;overflow-y:auto;margin:1em 0;">
<table class="delisted-tbl">
<thead><tr><th>Assessment Unit</th><th>Waterbody</th><th>Watershed</th><th>Type</th><th>Size</th><th>Last Listed</th><th>Causes ({{ site.data.facts_EPA303d.earliest_cycle }})</th></tr></thead>
<tbody>
{% for row in site.data.EPA_303d_delisted_removed %}
<tr>
  <td>{{ row["Assessment Unit"] }}</td>
  <td>{{ row["Waterbody"] }}</td>
  <td>{{ row["Watershed"] }}</td>
  <td>{{ row["Type"] | capitalize }}</td>
  <td>{{ row["Size"] }} {{ row["Unit"] | downcase }}</td>
  <td>{{ row["Last Listed"] }}</td>
  <td style="font-size:0.85em">{{ row["Causes"] }}</td>
</tr>
{% endfor %}
</tbody>
</table>
</div>
</details>

{{ site.data.facts_EPA303d.n_delisted_cat2 }} AUs are now listed as Category 2 — meaning they are assessed as meeting water quality standards, though with some concern. This is the clearest indication of improvement among the three groups.

<details>
<summary>Now Category 2 (meeting standards) — {{ site.data.facts_EPA303d.n_delisted_cat2 }} assessment units</summary>
<div style="max-height:360px;overflow-y:auto;margin:1em 0;">
<table class="delisted-tbl">
<thead><tr><th>Assessment Unit</th><th>Waterbody</th><th>Watershed</th><th>Type</th><th>Size</th><th>Last Listed</th><th>Causes ({{ site.data.facts_EPA303d.earliest_cycle }})</th></tr></thead>
<tbody>
{% for row in site.data.EPA_303d_delisted_cat2 %}
<tr>
  <td>{{ row["Assessment Unit"] }}</td>
  <td>{{ row["Waterbody"] }}</td>
  <td>{{ row["Watershed"] }}</td>
  <td>{{ row["Type"] | capitalize }}</td>
  <td>{{ row["Size"] }} {{ row["Unit"] | downcase }}</td>
  <td>{{ row["Last Listed"] }}</td>
  <td style="font-size:0.85em">{{ row["Causes"] }}</td>
</tr>
{% endfor %}
</tbody>
</table>
</div>
</details>

{{ site.data.facts_EPA303d.n_delisted_cat3 }} AUs are now listed as Category 3 — insufficient data to make an assessment. These were removed from the impaired list not because of demonstrated improvement, but because current monitoring data is inadequate to support a listing decision.


<details>
<summary>Now Category 3 (insufficient data) — {{ site.data.facts_EPA303d.n_delisted_cat3 }} assessment units</summary>
<div style="max-height:360px;overflow-y:auto;margin:1em 0;">
<table class="delisted-tbl">
<thead><tr><th>Assessment Unit</th><th>Waterbody</th><th>Watershed</th><th>Type</th><th>Size</th><th>Last Listed</th><th>Causes ({{ site.data.facts_EPA303d.earliest_cycle }})</th></tr></thead>
<tbody>
{% for row in site.data.EPA_303d_delisted_cat3 %}
<tr>
  <td>{{ row["Assessment Unit"] }}</td>
  <td>{{ row["Waterbody"] }}</td>
  <td>{{ row["Watershed"] }}</td>
  <td>{{ row["Type"] | capitalize }}</td>
  <td>{{ row["Size"] }} {{ row["Unit"] | downcase }}</td>
  <td>{{ row["Last Listed"] }}</td>
  <td style="font-size:0.85em">{{ row["Causes"] }}</td>
</tr>
{% endfor %}
</tbody>
</table>
</div>
</details>

---

## What Is Causing Impairment?

The 2022 cycle identifies over 90 distinct causes of impairment across Massachusetts waterbodies. The most widespread are bacterial indicators — fecal coliform and *E. coli* — followed by dissolved oxygen, non-native aquatic plants, mercury in fish tissue, and nutrients.

{% include charts/EPA303d_causes_breakdown.html %}

The chart below shows how the top causes have changed across all six reporting cycles. Several patterns are notable.

Fecal coliform has been consistently the most common cause throughout the period, but *E. coli* goes from essentially zero to ~300 AUs between the 2014 and 2016 cycles. This does not reflect a sudden biological event: *E. coli* replaced fecal coliform as EPA's recommended bacterial indicator for primary contact recreation in [EPA's 2012 Recreational Water Quality Criteria](https://www.epa.gov/sites/default/files/2015-10/documents/rwqc2012.pdf). MA DEP incorporated *E. coli* assessment criteria into its [2016 Consolidated Assessment and Listing Methodology (CALM)](https://www.mass.gov/files/documents/2016/10/wy/2016calm.pdf), which is why it appears in the 2016 reporting cycle data; the underlying Massachusetts surface water quality standards were formally amended in 2021. The two indicators largely measure the same contamination.

The 2016 cycle also sees dissolved oxygen, nutrient/eutrophication biological indicators, fanwort, and fish passage barriers all appear or increase sharply — several going from near-zero to hundreds of AUs. This reflects methodological and categorical changes in how MA DEP conducted and reported assessments that cycle, not five simultaneous environmental events. Most notably, fanwort was split out from the broader "non-native aquatic plants" category, which explains the corresponding decline in that count after 2016.

Mercury in fish tissue has increased gradually — from 158 AUs in 2010 to 204 in 2022 — as expanding fish tissue monitoring programs identify more affected waterbodies, though the rate of increase is slow and uneven. Fish passage barriers grew sharply from 18 AUs in 2016 to 112 in 2018, a pattern consistent with the methodological expansions that characterized that cycle rather than a sudden proliferation of physical barriers.

{% include charts/EPA303d_causes_trend.html %}

**Bacterial contamination** is the leading cause ({{ site.data.facts_EPA303d.top_cause_1_n }} AUs for {{ site.data.facts_EPA303d.top_cause_1 }}, {{ site.data.facts_EPA303d.top_cause_2_n }} AUs for {{ site.data.facts_EPA303d.top_cause_2 }}). Bacteria from human waste are the primary basis for beach and fishing closures, and can originate from combined sewer overflows (CSOs), sanitary sewer overflows, failing septic systems, and stormwater runoff. The source attribution data for bacterial impairments shows that MS4 municipal stormwater systems are the most commonly cited source, followed by CSOs and septic systems — though "Source Unknown" accounts for the largest share, reflecting the difficulty of attributing impairment to a specific discharge.

{% include charts/EPA303d_bacterial_sources.html %}

**Swimming use.** In 2022, {{ site.data.facts_EPA303d.pcr_fail }} of the {{ site.data.facts_EPA303d.pcr_assessed }} assessed AUs — {{ site.data.facts_EPA303d.pct_pcr_failing }}% — do not meet the **Primary Contact Recreation** standard, which is the threshold for safe swimming.

**Dissolved oxygen** impairment ({{ site.data.facts_EPA303d.top_cause_3_n }} AUs) is driven by excess nutrients (nitrogen and phosphorus), which fuel algal blooms. When algae decompose, the process consumes oxygen, reducing the dissolved oxygen available to aquatic life. Common nutrient sources include sewage effluent and agricultural and stormwater runoff from fertilized land.

**Mercury in fish tissue** reflects decades of atmospheric deposition from coal combustion and industrial emissions — a legacy problem that persists long after the original sources are controlled.

**Non-native aquatic plants** (particularly fanwort, *Cabomba caroliniana*) represent ecological impairment from invasive species rather than chemical pollution, and are widespread in Massachusetts lakes and ponds.

---

## CSO Discharges and 303(d) Status

Combined sewer overflows (CSOs) are a distinct type of discharge from aging sewage infrastructure in urban areas: during heavy rain events, combined stormwater and sewage systems can overflow, releasing untreated wastewater directly to receiving waters. A natural question is whether these discharges occur in waterbodies that are already impaired under the 303(d) framework.

To examine this, we matched [MA EEA Data Portal CSO discharge records]({{ site.url }}{{ site.baseurl }}/data/EEADP_all.html) — covering June 2022 through present — to 303(d) status for each receiving waterway using a manually verified mapping table. The mapping covers {{ site.data.facts_EPA303d.n_cso_mapped }} of the {{ site.data.facts_EPA303d.n_cso_unique_wb }} distinct CSO-reporting waterways in the EEA Data Portal.

The {{ site.data.facts_EPA303d.n_cso_not_matched }} waterways that could not be matched fall into two categories. Some use highly localized names — drainage channels, unnamed brooks, or facility-specific designations — that do not correspond to any named assessment unit in the 303(d) dataset. Others are reported with names that differ enough from the 303(d) assessment unit names (e.g. abbreviations, alternate spellings) that a reliable match could not be established without manual verification for each entry. These unmatched discharges are shown separately in the chart as "Status unknown (no 303d match)" — their impairment status is not known, not confirmed clean.

{% include charts/EPA303d_cso_impaired.html %}

Among the {{ site.data.facts_EPA303d.n_cso_mapped }} matched waterways, all are rated "Not Supporting" in the most recent 303(d) cycle. Of the {{ site.data.facts_EPA303d.vol_total_bgal }} billion gallons of total reported CSO discharge, {{ site.data.facts_EPA303d.pct_vol_impaired_of_total }}% went to these confirmed-impaired waterways; the remaining {{ site.data.facts_EPA303d.vol_not_matched_bgal }} billion gallons discharged to waterways we could not match to a 303(d) record.

The chart below shows each group of waterways ranked by the fraction of their assessed AUs with bacterial impairment (fecal coliform or *E. coli*). Each red dot is one CSO-receiving waterway; hover for the waterway name and AU counts. The grey line shows all other 303(d) waterways.

{% include charts/EPA303d_cso_bact_cdf.html %}

Among non-CSO waterways, approximately 74% have zero assessed AUs with bacterial impairment. Among CSO-receiving waterways, most have 100% of their assessed AUs with bacterial impairment, and no waterway falls below 25%.

One question raised by this pattern is whether it reflects CSO outfalls specifically, or urbanization more broadly. The bar chart below shows the fraction of assessed AUs with bacterial impairment grouped by the predominant pollution source type attributed to each waterway by assessors. "CSO-receiving" uses the mapping table; all other groups exclude CSO-mapped waterways.

{% include charts/EPA303d_bacterial_source_groups.html %}

Waterways with CSO or MS4/urban stormwater attribution have the highest bacterial impairment rates (72% and 47% of assessed AUs respectively), followed by septic-influenced waterways (42%), agricultural waterways (32%), and others (30%). The gap between CSO and MS4 waterways is partly a function of selection: CSO-mapped waterways were specifically identified because they receive direct sewage discharges, while the MS4 group includes a broader mix of urban waterways. Impairment assessments reflect multiple pollution sources, and source attribution in the 303(d) data is often uncertain — "Source Unknown" is the most commonly recorded source overall.

This pattern reflects the geographic concentration of combined sewer infrastructure in older urban areas — the same watersheds where water quality impairment has historically been documented. The overlap does not by itself indicate that CSOs are the cause of the 303(d) listings, since impairment assessments reflect multiple pollution sources.

---

## TMDL Progress

For every Category 5 impaired waterbody, MA DEP and EPA must develop a TMDL before further water quality improvements can be required. The chart below tracks the share of impaired AUs with and without a completed TMDL across reporting cycles.

{% include charts/EPA303d_tmdl_trend.html %}

In {{ site.data.facts_EPA303d.earliest_cycle }}, {{ site.data.facts_EPA303d.tmdl_with_earliest }} of {{ site.data.facts_EPA303d.impaired_earliest }} impaired AUs had a completed TMDL ({{ site.data.facts_EPA303d.tmdl_pct_earliest }}%). In {{ site.data.facts_EPA303d.latest_cycle }}, {{ site.data.facts_EPA303d.tmdl_with_latest }} of {{ site.data.facts_EPA303d.impaired_latest }} had one ({{ site.data.facts_EPA303d.tmdl_pct_latest }}%). The number of AUs without a cleanup plan grew from {{ site.data.facts_EPA303d.tmdl_without_earliest }} to {{ site.data.facts_EPA303d.tmdl_without_latest }} over the same period.

Averaged across reporting cycles, approximately {{ site.data.facts_EPA303d.avg_net_tmdl_per_cycle }} net new TMDLs have been completed per two-year cycle. At that pace, and assuming no new listings, the current backlog of {{ site.data.facts_EPA303d.tmdl_without_latest }} AUs without a plan would not be cleared until around {{ site.data.facts_EPA303d.year_backlog_cleared }}. This is an illustrative projection based on recent rates, not a forecast.

The chart below tracks what happened to the {{ site.data.facts_EPA303d.n_cohort_cat5 }} AUs that were listed as Category 5 (TMDL needed, none yet) in 2010 — the earliest cycle in our data. Because 2010 is our starting point, the true wait for many of these AUs is longer than the chart shows; some had already been listed for years before 2010.

{% include charts/EPA303d_tmdl_survival.html %}

By 2022, {{ site.data.facts_EPA303d.pct_still_no_tmdl }}% of that original cohort — {{ site.data.facts_EPA303d.still_no_tmdl }} AUs — still had no completed cleanup plan.

This pattern is not unique to Massachusetts. The [National Academies has documented](https://nap.nationalacademies.org/catalog/10146/assessing-the-tmdl-approach-to-water-quality-management) that approximately 21,000 polluted water segments nationally require over 40,000 TMDLs, and states consistently cite limited personnel and funding as constraints on completion.

As noted above, EPA's April 2025 statewide pathogen TMDL for Massachusetts may change the picture for bacterial impairments specifically. By establishing load limits for all pathogen-impaired waters at once, it could formally satisfy the TMDL requirement for a large number of AUs — potentially shifting the fraction shown in future reporting cycles. The practical effect on water quality will depend on how the TMDL is implemented through individual permit requirements and infrastructure improvements.

The map below shows TMDL completion by watershed as of 2022. Circle size reflects the count of impaired AUs; color reflects the fraction with a completed TMDL (green ≥ 50%, orange 25–49%, red < 25%).

<iframe src="{{ site.url }}{{ site.baseurl }}/assets/maps/EPA303d_tmdl_map.html" 
        width="100%" height="480" frameborder="0" scrolling="no"
        style="border:1px solid #ccc;border-radius:4px;margin:1em 0;"></iframe>

---

## Watershed Breakdown

Impairment is not evenly distributed across the state. The watersheds with the most impaired AUs in 2022 include both heavily urbanized areas and coastal watersheds. The chart below breaks down impaired AUs by water type within each watershed.

{% include charts/EPA303d_watershed_impairment.html %}

Cape Cod's high count reflects its shallow, nutrient-sensitive coastal ponds and estuaries, where development pressure and aging septic systems have contributed to widespread nitrogen impairment. Buzzards Bay and the South Coastal watershed face similar conditions. The Taunton and Blackstone watersheds reflect more urban and industrial stressors.

---

## Summary

The 303(d) Integrated List provides the most direct available measure of water quality conditions in Massachusetts waterbodies. Several patterns are visible in the data from {{ site.data.facts_EPA303d.earliest_cycle }} through {{ site.data.facts_EPA303d.latest_cycle }}:

- The count of impaired AUs has grown in every reporting cycle, from {{ site.data.facts_EPA303d.impaired_earliest }} to {{ site.data.facts_EPA303d.impaired_latest }}. Most of this growth reflects newly assessed waterbodies rather than deterioration of previously passing ones, though the overall list of impaired waters has not declined.

- Bacterial contamination — fecal coliform and *E. coli* — is the most commonly cited cause of impairment, attributable to a mix of sources including stormwater, CSOs, and septic systems. {{ site.data.facts_EPA303d.pct_pcr_failing }}% of assessed waterbodies do not meet the standard for safe swimming.

- Among CSO-reporting waterways that could be matched to 303(d) records, all are classified as impaired in the 2022 cycle. CSO infrastructure is concentrated in urban areas where water quality impairment has historically been documented.

- The fraction of impaired AUs with a completed TMDL has remained roughly flat at 38–40% across all six cycles, while the absolute number without a plan has grown. EPA's April 2025 statewide pathogen TMDL may affect this metric in future cycles, though its water quality impact will depend on implementation.

- Massachusetts's 2024 Integrated List is in draft as of spring 2026. When approved and published by MassGIS, this analysis will update automatically.

---

*This post was prepared with assistance from [Claude](https://www.anthropic.com/claude), an AI assistant, which helped structure the analysis, write code, and draft text. All data, methodology, and conclusions were reviewed and approved by [the site author](https://github.com/nesanders).*
