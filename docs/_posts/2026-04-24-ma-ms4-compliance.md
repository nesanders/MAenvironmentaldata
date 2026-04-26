---
layout: post
title: "(DRAFT) Seven years of Massachusetts stormwater compliance: what MS4 annual reports reveal"
ancillary: 0
---

*This post is in DRAFT status. It has not yet been fully completed and reviewed.*

Massachusetts cities and towns discharge stormwater directly to rivers, ponds, and coastal waters through networks of pipes and drains — Municipal Separate Storm Sewer Systems, or **MS4s**. Unlike combined sewers, MS4s are designed to carry only stormwater, but they remain a major pathway for phosphorus, bacteria, metals, and road salt into waterways. Since 2019, municipalities regulated under the [Massachusetts Small MS4 General Permit](https://www.epa.gov/npdes-permits/massachusetts-small-ms4-general-permit) have been required to submit annual compliance reports to EPA documenting their stormwater management programs.

These reports — submitted as PDFs with no structured data API — contain seven years of compliance activity across {{ site.data.facts_MS4.n_municipalities }} municipalities: outfall inspections, illicit discharge investigations, construction site enforcement, and TMDL pollution reduction progress. This analysis extracts and synthesizes that record for the first time.

*The data behind this analysis is documented on the [MS4 annual reports data page]({{ site.baseurl }}/data/MS4_annual_reports.html). [Analysis code](https://github.com/nesanders/MAenvironmentaldata/blob/master/analysis/MS4_compliance_viz.py) and [extraction pipeline](https://github.com/nesanders/MAenvironmentaldata/blob/master/get_data/get_MS4_annual_reports.py) are available on GitHub.*

---

## Background: The MS4 permit and what municipalities must report

Under [Section 402 of the Clean Water Act](https://www.epa.gov/cwa-404/clean-water-act-section-402-national-pollutant-discharge-elimination-system), operators of small MS4s must obtain NPDES stormwater permits and implement programs across six **Minimum Control Measures (MCMs)**:

| # | MCM | What municipalities must do | Metrics extracted |
|---|---|---|---|
| 1 | Public Education & Outreach | Distribute educational materials on stormwater impacts | Activities/events count |
| 2 | Public Participation | Involve the public in program development | Activities/meetings count |
| 3 | Illicit Discharge Detection & Elimination (IDDE) | Map outfalls, screen for non-stormwater flows, eliminate illicit connections | Outfalls total; outfalls screened; outfalls not accessed; illicit discharges found; illicit discharges eliminated; whether sampling was conducted; cumulative vs. current-period count type |
| 4 | Construction Site Runoff Control | Inspect active sites, enforce erosion controls | Sites inspected; violations found |
| 5 | Post-Construction Stormwater Management | Require and inspect best management practices (BMPs) for new development | Sites inspected; BMPs inspected |
| 6 | Pollution Prevention / Good Housekeeping | Inspect and maintain municipal facilities and infrastructure | Facilities inspected (catch basins or facilities per notes) |

The current permit covers a seven-year cycle (FY2019–FY2025). Municipalities additionally report progress toward waterbody-specific **Total Maximum Daily Load (TMDL)** pollution reduction targets where applicable.

**Data note:** This analysis uses AI-extracted structured data from {{ site.data.facts_MS4.n_reports }} annual report PDFs across {{ site.data.facts_MS4.n_municipalities }} municipalities, covering FY2019–FY2025. Non-traditional MS4 permittees (universities, state agencies, military installations — permit prefix MAR042) are excluded from municipal comparisons. Records with low extraction confidence are excluded. See the [data page]({{ site.baseurl }}/data/MS4_annual_reports.html) for methodology and known data gaps.

---

## Key findings

- **{{ site.data.facts_MS4.total_illicit_found | number_with_delimiter }}** illicit discharges identified across all municipalities over the permit cycle, with **{{ site.data.facts_MS4.total_illicit_eliminated | number_with_delimiter }}** eliminated
- **{{ site.data.facts_MS4.n_municipalities_tmdl_quantitative }}** municipalities reported quantitative TMDL reduction data (lbs/yr), primarily for Charles River phosphorus
- Outfall inspection activity is growing across the permit cycle; construction site inspection rates are more variable
- System mapping completion has increased steadily but coverage data is sparse in early years
- Municipalities with active CSO systems show detectably higher illicit discharge detection rates

---

## Permit compliance trajectory

How has participation in key MCM activities changed over the seven-year permit cycle? The chart below shows the fraction of municipalities reporting non-zero activity for three metrics each year: MCM3 outfall screening (current-period reporters only), MCM4 construction site inspections, and MCM6 facility inspections.

{% include charts/MS4_participation_rate.html %}

MCM6 facility inspection participation is highest and most stable, reflecting that catch basin and municipal facility inspections are an established routine for most communities. MCM4 construction site inspection rates are lower — not all municipalities have active construction activity every year. MCM3 outfall screening participation has grown across the permit cycle as municipalities complete system mapping and begin active screening programs.

Among the municipalities that reported both total outfall count and outfalls screened in a given year (~28% of all records), the chart below shows the distribution of screening completion rates over time.

{% include charts/MS4_mcm3_screening_rate.html %}

The median screening rate among this subset is high in most years, suggesting that municipalities with complete reporting data are generally making strong progress through their outfall inventories. The wide interquartile range in earlier years reflects communities at very different stages of program maturity.

---

## Illicit discharge detection and elimination

Illicit discharges — non-stormwater flows such as sanitary sewage, industrial effluent, or waste water — entering the separated storm sewer system are among the most direct water quality threats MS4 programs are designed to address. The chart below shows the total number of illicit discharges found and eliminated across all municipalities by report year, restricted to municipalities that report current-period (not cumulative) counts.

{% include charts/MS4_idde_activity.html %}

Across the full dataset, municipalities have collectively identified **{{ site.data.facts_MS4.total_illicit_found }}** illicit discharges and eliminated **{{ site.data.facts_MS4.total_illicit_eliminated }}** between 2009 and 2025. The gap between found and eliminated reflects discharges still under investigation or remediation at the time of reporting, as well as some municipalities that track eliminated counts with a lag.

---

## Stormwater system mapping progress

Before outfalls can be screened for illicit discharges, they must be located and mapped. The permit requires municipalities to complete stormwater system mapping — a foundational compliance task that many communities were still working through in the early permit years. The chart below shows how municipalities are distributed across five completion brackets by report year.

{% include charts/MS4_mapping_progress.html %}

The stacked bars show the count of municipalities in each completion range. The 100%-complete group visible from 2019 onward reflects municipalities that had already finished mapping before the permit cycle started. The total bar height varies by year because `system_mapping_pct_complete` is missing from approximately 58% of all reports — only municipalities that explicitly reported this field are shown.

**Note on methodology:** Raw reported values are non-monotonic — 132 municipality-year instances show a value lower than a prior year, almost certainly due to methodology changes (e.g. switching from percent of pipe-miles mapped to percent of outfalls mapped) rather than actual loss of mapping. This chart uses a value that is the running historical maximum per municipality, propagated forward across years where the field was left blank. This eliminates spurious individual regressions but does not fully eliminate year-to-year variation in bar heights: municipalities that filed a report in year Y but omitted the mapping field are not counted in year Y even if they previously reported 100%. The overall upward trend is robust.

---

## TMDL reduction progress

Municipalities with impaired waterbodies subject to Total Maximum Daily Load requirements must report progress toward meeting their wasteload allocations. The chart below shows reported phosphorus reduction achieved (lbs/yr) for the 85 municipalities with quantitative data, stacked by municipality.

{% include charts/MS4_tmdl_progress.html %}

Phosphorus dominates the quantitative TMDL record almost entirely. This reflects the structure of the permit itself: the Charles River phosphorus TMDL is the most developed and monitored in the state, with explicit per-municipality lbs/yr wasteload allocations written into the permit text. Other pollutants (nitrogen, bacteria, metals, chloride) appear in TMDL compliance sections but almost never with quantitative lbs/yr targets — municipalities typically report these as "in progress" or "not applicable." The few non-phosphorus records with numerical values contribute less than 15% of total reported reduction even in their best years. TMDL quantitative coverage is uneven overall: many municipalities list TMDL waterbodies without reporting numerical reduction achieved or wasteload allocation.

---

## Cross-dataset: illicit discharge detection in CSO municipalities

Twelve Massachusetts municipalities operate both an MS4 stormwater system and active combined sewer overflow (CSO) infrastructure — identified by joining the MS4 dataset to [EEA Data Portal CSO discharge records]({{ site.baseurl }}/data/EEADP_all.html) on municipality name. CSO municipalities have older, more interconnected sewer infrastructure with greater potential for cross-connections between storm and sanitary sewers. The chart below shows total illicit discharges found in CSO municipalities each year, broken out by municipality.

{% include charts/MS4_idde_vs_cso.html %}

New Bedford, Gloucester, and Lawrence account for the majority of detected illicit discharges among CSO municipalities. Non-CSO municipalities collectively found {{ site.data.facts_MS4.total_illicit_found | minus: 124 }} illicit discharges over the permit cycle across 241 municipalities — meaningful in aggregate but averaging under two per municipality over seven years, compared to roughly ten per municipality in CSO communities. The difference likely reflects both genuine infrastructure complexity in CSO systems and more mature IDDE programs in communities that have been actively managing combined sewer issues for decades.

---

## Data gaps

The following data limitations apply throughout this analysis:

| Field | ~% null | Implication |
|---|---|---|
| `mcm3_outfalls_total` | ~72% | Cannot compute outfall screening rate for most municipalities; trajectory chart uses raw screened count |
| `mcm5_sites_inspected` | ~75% | Post-construction inspection is the most poorly reported MCM; excluded from trend charts |
| `system_mapping_pct_complete` | ~58% | Mapping chart has wide coverage gaps, especially in earlier years; n annotated on chart |
| `mcm2_activities_count` | ~29% | Public participation counts inconsistently reported |

MCM3 IDDE counts: approximately 37% of municipalities with non-null IDDE counts report cumulatively since permit start rather than per-period. These municipalities are excluded from trend and totals charts above (retained only in the compliance trajectory chart's median calculation, labeled accordingly).

TMDL quantitative coverage is uneven — many municipalities list TMDL waterbodies without reporting numerical reduction achieved or wasteload allocation. Only the {{ site.data.facts_MS4.n_municipalities_tmdl_quantitative }} municipalities with both numerator and denominator are included in the TMDL progress chart.

---

## Limitations and future work

- **Cumulative vs. period count ambiguity:** The `mcm3_count_type` field distinguishes current-period from cumulative reporters, but relies on AI extraction of sometimes ambiguous report text. Misclassification is possible.
- **Extraction confidence:** 11 reports with low extraction confidence are excluded. An additional ~27% of records are classified medium confidence, meaning some fields may be imprecise.
- **Non-traditional MS4s excluded:** Universities, state agencies, and military installations (permit prefix MAR042) have fundamentally different infrastructure and are not comparable to municipal permittees.
- **Environmental justice:** This report does not include analysis of MS4 compliance by environmental justice factors. EJSCREEN data is at census block-group level with no direct municipality join; EJ analysis requires spatial aggregation of block-group data to town boundaries and is deferred.
- **Join to DEP enforcement:** MS4 permit violations and enforcement actions are not yet linked to this dataset; joining via permit number to the EEA Data Portal enforcement table in AMEND would allow this.
- **Join to 303(d) impairment trends:** Do municipalities showing TMDL progress correspond to improving 303(d) assessment unit status? This cross-dataset join is planned but not yet implemented. Given that very few 303(d) impairment statuses change with time, we expect to see little signal here.
