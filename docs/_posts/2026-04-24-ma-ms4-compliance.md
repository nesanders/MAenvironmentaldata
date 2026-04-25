---
layout: post
title: "Seven years of Massachusetts stormwater compliance: what MS4 annual reports reveal (DRAFT)"
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

How has activity across the key quantitative MCMs changed over the seven-year permit cycle? The chart below shows the median count per municipality for three metrics by report year: MCM4 construction site inspections, MCM6 facility inspections, and MCM3 outfall screening (restricted to municipalities that report current-period counts only — see data gaps section).

{% include charts/MS4_compliance_trajectory.html %}

MCM6 facility inspections are dominated by catch basin cleaning counts, which many municipalities report in large numbers. MCM4 construction site inspections show more variation, reflecting differences in development activity across municipalities. MCM3 outfall screening counts have grown as municipalities make progress toward completing their system mapping and screening requirements.

---

## Illicit discharge detection and elimination

Illicit discharges — non-stormwater flows such as sanitary sewage, industrial effluent, or wash water — entering the storm sewer system are among the most direct water quality threats MS4 programs are designed to address. The chart below shows the total number of illicit discharges found and eliminated across all municipalities by report year, restricted to municipalities that report current-period (not cumulative) counts.

{% include charts/MS4_idde_activity.html %}

Across the full dataset, municipalities have collectively identified **{{ site.data.facts_MS4.total_illicit_found }}** illicit discharges and eliminated **{{ site.data.facts_MS4.total_illicit_eliminated }}**. The gap between found and eliminated reflects discharges still under investigation or remediation at the time of reporting, as well as some municipalities that track eliminated counts with a lag.

---

## Stormwater system mapping progress

Before outfalls can be screened for illicit discharges, they must be located and mapped. The permit requires municipalities to complete stormwater system mapping — a foundational compliance task that many communities were still working through in the early permit years. The chart below shows how municipalities are distributed across five completion brackets by report year.

{% include charts/MS4_mapping_progress.html %}

The stacked bars show the count of municipalities in each completion range. The large 100%-complete group visible from 2019 onward reflects municipalities that had already finished mapping before the permit cycle started. The total bar height varies by year because `system_mapping_pct_complete` is missing from approximately 58% of all reports — only municipalities that explicitly reported this field are shown.

---

## TMDL reduction progress

Municipalities with impaired waterbodies subject to Total Maximum Daily Load requirements must report progress toward meeting their wasteload allocations. The chart below shows total reported reduction achieved (lbs/yr) summed across all municipalities with quantitative data, broken out by pollutant.

{% include charts/MS4_tmdl_progress.html %}

Charles River phosphorus dominates the quantitative record — the Charles River watershed has the most municipalities with explicit lbs/yr reduction targets established in the permit. Other pollutants and watersheds (nitrogen, bacteria, metals) appear in the data but with fewer municipalities reporting quantitative progress. **{{ site.data.facts_MS4.n_municipalities_tmdl_quantitative }}** municipalities contributed quantitative reduction data across the full dataset.

---

## Cross-dataset: illicit discharge detection in CSO municipalities

Municipalities with active combined sewer overflow (CSO) systems have more complex sewer infrastructure — older combined pipes, more interconnected systems — creating more opportunities for illicit connections and greater incentive for active IDDE programs. The chart below compares median illicit discharge detection rates between CSO and non-CSO municipalities by report year.

{% include charts/MS4_idde_vs_cso.html %}

CSO municipalities (identified from the [EEA Data Portal CSO discharge records]({{ site.baseurl }}/data/EEADP_all.html)) consistently show higher median illicit discharge detection rates than non-CSO municipalities. This likely reflects a combination of genuine infrastructure differences and more mature IDDE programs in communities that have been managing combined sewer issues for decades.

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
- **Environmental justice:** EJSCREEN data is at census block-group level with no direct municipality join; EJ analysis requires spatial aggregation of block-group data to town boundaries and is deferred.
- **Join to DEP enforcement:** MS4 permit violations and enforcement actions are not yet linked to this dataset; joining via permit number to the EEA Data Portal enforcement table is a promising next step.
- **Join to 303(d) impairment trends:** Do municipalities showing TMDL progress correspond to improving 303(d) assessment unit status? This cross-dataset join is planned but not yet implemented.
