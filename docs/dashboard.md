---
layout: post
title: "Live Data Dashboard"
permalink: /dashboard.html
---

**Last updated:** {{ site.data.ts_update_dashboard.updated | date: "%-d %B %Y at %H:%M UTC" }}

Charts on this page are regenerated automatically each Monday morning from the latest available data.
For full analysis and narrative context, follow the links in each section.

*For full details on how these dashbpards were built and updated, see the [GitHub Actions run history](https://github.com/nesanders/MAenvironmentaldata/actions/workflows/update-charts.yml)*

---

**Contents:**
[MA DEP Staffing](#staffing) &middot;
[Enforcement Actions](#enforcement) &middot;
[State Agency Budgets](#budgets) &middot;
[CSO Discharge Trends](#cso) &middot;
[303(d) Impaired Waters](#303d) &middot;
[MS4 Stormwater Compliance](#ms4) &middot;
[Lobbying Spend](#lobbying) &middot;
[CSO Data Quality Indicator](#data-quality) &middot;
[Discharge by Watershed](#watershed)

---

<a name="staffing"></a>

## MA DEP Staffing

**DEP staffing levels directly determine the agency's capacity to review permits, investigate violations, and enforce environmental law.**

Data: [MA DEP staff payroll records]({{ site.url }}{{ site.baseurl }}/data/MADEP_staff.html)
— [VisibleGovernment]({{ site.url }}{{ site.baseurl }}/data/MADEP_staff.html) through 2016,
[MA Comptroller]({{ site.url }}{{ site.baseurl }}/data/MADEP_staff.html) (SODA API) 2010–present.
Full analysis: [Staff Changes at the MADEP Over Time]({{ site.url }}{{ site.baseurl }}/2017/03/15/dep-staff-changes.html).

<details>
<summary>About this data and methodology</summary>

Payroll records from two sources are merged on employee name and calendar year, allowing a
continuous series from 2004 onward. Staffing counts are tabulated by calendar year. Funding
data comes from the MA Comptroller CTHRU (Socrata API) for FY2005–present, supplemented with 
<a href="{{ site.url }}{{ site.baseurl }}/data/MassBudget_environmental.html">MassBudget data</a> for FY2001–FY2004.
Budget figures are inflation-adjusted to 2024 dollars using the SSA Average Wage Index. Seniority is estimated
as the number of years each employee appears in the combined dataset relative to 2004, the
first year of records.

MA Comptroller payroll data has a publication lag of approximately 15 months. Data is currently available through calendar year 2024; records for 2025 are expected to appear in the API in approximately early 2027.

The correlation between annual DEP headcount and total agency budget is
{{ site.data.facts_DEPstaff.cor_staff_funding }}% (p={{ site.data.facts_DEPstaff.cor_staff_funding_p }}).
Note that the budget series uses reported administrative appropriations and may not capture
all funding sources. See the <a href="{{ site.url }}{{ site.baseurl }}/2017/03/15/dep-staff-changes.html">2017 staffing post</a>
for detailed caveats on data completeness and the merger of the two payroll sources.

</details>

### Overall staffing levels

{% include charts/dash_MADEP_staffing_overall.html %}

### Staffing vs. agency funding

{% include charts/dash_MADEP_staffing_overall_funding.html %}

### Staff seniority over time

{% include charts/dash_MADEP_staffing_seniority.html %}

*Note: Seniority data is only available through 2016 from VisibleGovernment payroll records. While staffing levels have been updated with more recent Comptroller data, seniority calculations are not available after 2016.*

---

<a name="enforcement"></a>

## MA DEP Enforcement Actions

**Enforcement actions measure whether DEP is actively holding polluters accountable.**

Data: [MA DEP enforcement actions]({{ site.url }}{{ site.baseurl }}/data/MADEP_enforcement_actions.html).
Full analysis: [Changes in Enforcement by MA DEP Over Time]({{ site.url }}{{ site.baseurl }}/2017/04/02/dep-enforcements.html).

<details>
<summary>About this data and methodology</summary>

Enforcement counts use EEA Data Portal records spanning 1996 to present. Routine administrative notices (Notice Of Non-Compliance, Field NONs, Boil Orders, and federal notices) are excluded—these are issued at high volume and do not reflect investigative or enforcement officer effort. Substantive enforcement actions counted include consent orders, unilateral orders, and penalty notices. Budget data comes from the MA Comptroller CTHRU API (FY2005–present) supplemented with cached MassBudget data (FY2001–FY2004), inflation-adjusted to 2024 dollars.

The correlation between annual enforcement counts and agency budget is
{{ site.data.facts_DEPenforce.cor_enforcement_funding }}%.
Administrative Consent Orders with Penalties (ACOPs) are identified as a subset of consent orders;
penalty amounts are estimated using bootstrap resampling with 90% confidence intervals.

See the <a href="{{ site.url }}{{ site.baseurl }}/2017/04/02/dep-enforcements.html">2017 enforcement post</a>
for detailed topic-level analysis.

</details>

### Total enforcement actions

{% include charts/dash_MADEP_enforcement_overall.html %}

### Enforcement actions vs. agency budget

{% include charts/dash_MADEP_enforcement_vsbudget.html %}

### Enforcement actions by type

{% include charts/dash_MADEP_enforcement_bytype.html %}

---

<a name="budgets"></a>

## State Environmental Agency Budgets

**State environmental agency budgets vary widely per capita; Massachusetts has the lowest per-capita environmental spending among New England states.**

Data: [ECOS State Environmental Agency Budget Report]({{ site.url }}{{ site.baseurl }}/data/ECOS_budget_history.html)
and [US Census state population estimates]({{ site.url }}{{ site.baseurl }}/data/Census_statepop.html).

<details>
<summary>About this data and methodology</summary>

The <a href="https://www.ecos.org/">Environmental Council of the States (ECOS)</a> collects annual budget
survey data from state environmental agencies. Per-capita figures are calculated by dividing
each state's reported agency budget by the Census Bureau's annual state population estimate.
Massachusetts is highlighted for easy comparison.

Cross-state comparability is imperfect: states define the scope of their "environmental agency"
differently — some include health, energy, or natural resources functions, others do not.
Year-over-year trends within a single state are more reliable than cross-state point-in-time
comparisons. Budget figures are adjusted for inflation using the SSA Average Wage Index.

</details>

### Per-capita environmental spending by state

*Note: ECOS budget data is fetched manually and does not update automatically each week. Current data covers FY2009–FY2023, last updated from the [ECOS FY2020–2023 Green Report](https://www.ecos.org/documents/ecos-green-report-status-of-state-environmental-agency-budgets-fiscal-years-2020-to-2023/) (published August 2025).*

{% include charts/dash_ECOS_budget_percap_peryear_bystate.html %}

---

<a name="cso"></a>

## CSO Discharge Trends

**Combined sewer overflows discharge untreated sewage into waterways during rain events. The charts below reflect conditions since the 2020 Sewage Notification Act took effect.**

Data: [MA EEA Data Portal — CSO discharge reports]({{ site.url }}{{ site.baseurl }}/data/EEADP_all.html),
covering June 2022 to present under the [Sewage Notification Act (Chapter 322 of 2020)](https://malegislature.gov/Laws/SessionLaws/Acts/2020/Chapter322).
Full analysis: [(DRAFT) Three years of MA sewage pollution data]({{ site.url }}{{ site.baseurl }}/2026/04/03/eea-dp-cso-ej.html).

<details>
<summary>About this data and methodology</summary>

Regulated sewer operators report CSO and SSO discharge events to the EEA Data Portal within
24 hours of occurrence. Each record includes event type, estimated discharge volume, affected
waterbody, and operator identity. Rainfall data comes from NOAA ACIS, averaging daily
precipitation across Massachusetts GHCN and NWS COOP weather stations.

Discharge counts and volumes are tabulated by month and year. The rainfall chart uses a
48-hour lookback window for precipitation totals, following
<a href="https://iwaponline.com/wst/article/86/11/2848/91816/">Bizer & Kirchhoff (2022)</a>.
Operator volumes are shown as annual trends for the top 10 operators, illustrating how each operator's 
discharge volumes change year-to-year. Note that 2022 data covers only the second half of the calendar year; 
the first full calendar year of data is 2023.

</details>

### Annual discharge volume and rainfall

{% include charts/dash_MAEEADP_dashboard_annual_precip_discharge.html %}

### Monthly discharge counts and rainfall

{% include charts/dash_MAEEADP_dashboard_counts_per_month.html %}

### Discharge volume by operator over time

{% include charts/dash_MAEEADP_dashboard_volume_per_operator.html %}

---

<a name="303d"></a>

## 303(d) Impaired Waters

**Massachusetts must identify waterbodies failing water quality standards every two years.
This data provides the outcome measure for AMEND's regulatory inputs.**

Data: [EPA 303(d) Integrated List of MA Impaired Waters]({{ site.url }}{{ site.baseurl }}/data/EPA_303d_ImpairedWaters.html).
Full analysis: [MA Impaired Waters: Trends, Causes, and the CSO Connection]({{ site.url }}{{ site.baseurl }}/2026/04/11/ma-impaired-waters-303d.html).

<details>
<summary>About this data and methodology</summary>

Section 303(d) of the Clean Water Act requires MA to publish a biennial Integrated List of Waters
identifying waterbodies that fail water quality standards. MA submits the list to EPA on April 1
of even-numbered years; EPA typically approves it within 6–18 months.

Data is sourced from MassGIS shapefiles. Available cycles: 2010, 2012, 2014, 2016, 2018, 2022.
The 2024/2026 cycle is currently in draft — AMEND will automatically incorporate it
when MassGIS publishes the approved data. Because cycles are released biennially, no new data
appears between cycles.

"Impaired" in the trend chart includes Categories 4A, 4B, 4C (impaired but with a cleanup plan)
and 5 (impaired, TMDL needed). Category 5 is the "303(d) list" proper. A TMDL (Total Maximum
Daily Load) is a legally required cleanup plan setting maximum allowable pollutant loads.

CSO discharges are linked to 303(d) status using a manually verified mapping of
{{ site.data.ts_update_ATTAINS_303d.latest_cycle }} assessment data for
{{ site.data.facts_EPA303d.n_cso_mapped }} of {{ site.data.facts_EPA303d.n_cso_unique_wb }} CSO-reporting
waterways. Every matched waterway is rated "Not Supporting" — none discharge into fully supporting waters.
Unmatched waterways are shown as "Not matched."

</details>

### Trend in impaired water count over time

{% include charts/dash_EPA303d_impaired_trend.html %}

### Persistence of impairment: original 2010 cohort vs. newly listed

{% include charts/dash_EPA303d_persistence.html %}

### Causes of impairment ({{ site.data.ts_update_ATTAINS_303d.latest_cycle }})

{% include charts/dash_EPA303d_causes_breakdown.html %}

### Top impairment causes across all reporting cycles

{% include charts/dash_EPA303d_causes_trend.html %}

### CSO discharges to impaired vs. non-impaired waters

{% include charts/dash_EPA303d_cso_impaired.html %}

### TMDL cleanup plan progress

{% include charts/dash_EPA303d_tmdl_trend.html %}

---

<a name="ms4"></a>

## MS4 Stormwater Compliance

Data: [MA MS4 Municipal Stormwater Annual Reports]({{ site.url }}{{ site.baseurl }}/data/MS4_annual_reports.html).
Full analysis: [Seven years of Massachusetts stormwater compliance]({{ site.url }}{{ site.baseurl }}/2026/04/24/ma-ms4-compliance.html).

<details>
<summary>About this data and methodology</summary>

MS4 annual reports are submitted as PDFs by ~276 Massachusetts municipalities regulated under EPA Region 1's Small MS4 General Permit (FY2019–FY2025). AMEND uses Google Gemini 2.5 Flash to extract structured compliance data — inspection counts, illicit discharge detections, system mapping progress — from each report. Non-traditional MS4 permittees (universities, military installations — permit prefix MAR042) and low-confidence extractions are excluded. Counts shown are medians across all reporting municipalities; totals are sums across municipalities reporting current-period (not cumulative) counts.

</details>

### MCM participation rate by year (% of municipalities with non-zero activity)

{% include charts/dash_MS4_participation_rate.html %}

### Illicit discharge detection and elimination by year

{% include charts/dash_MS4_idde_activity.html %}

### Stormwater system mapping progress

{% include charts/dash_MS4_mapping_progress.html %}

---

<a name="data-quality"></a>

## Data Quality Indicator: Estimated vs. Measured Discharge Volumes

Data: [MA EEA Data Portal — CSO discharge reports]({{ site.url }}{{ site.baseurl }}/data/EEADP_all.html).

<details>
<summary>About this data and methodology</summary>

When operators report discharge volumes rounded to the nearest 1,000 gallons, this likely indicates estimation rather than direct measurement. A higher fraction of estimated reports means less precise discharge accounting for that month. CSO operators may estimate discharge volume when direct measurement is not available, particularly during early-response phases of an event.

</details>

### Monthly fraction of estimated vs. measured discharge reports

{% include charts/dash_MAEEADP_dashboard_modeled_vs_metered_fraction.html %}

---

<a name="watershed"></a>

## Discharge by Watershed

Data: [MA EEA Data Portal — CSO discharge reports]({{ site.url }}{{ site.baseurl }}/data/EEADP_all.html).

<details>
<summary>About this data and methodology</summary>

Discharge volumes are aggregated to the watershed level using outfall location data from a
<a href="{{ site.url }}{{ site.baseurl }}/data/ma_permittee-and-outfall-lists.xlsx">state permittee and outfall list</a>.
The chart shows monthly cumulative discharge volume for the 8 watersheds with the highest total
discharge over the full reporting period to date.

</details>

### Monthly discharge volume by receiving watershed

{% include charts/dash_MAEEADP_dashboard_monthly_volume_watershed.html %}

---

<a name="lobbying"></a>

## Lobbying Spend on Environmental Bills

Data: [MA Secretary of State lobbying disclosures]({{ site.url }}{{ site.baseurl }}/data/MA_lobbying.html), 2005–present.

Lobbying disclosures filed semi-annually with the MA Secretary of State identify which organizations hired lobbyists, how much clients paid, and which specific bills were lobbied. Bills are scored for environmental relevance using Google Gemini embeddings; charts show only employers that lobbied at least one environmentally relevant bill. Compensation figures reflect total payments from each client to each lobbying entity per year.

Data last updated **{{ site.data.ts_update_MA_lobbying.updated | date: "%-d %B %Y" }}**. Refreshed automatically on a weekly basis; exits early when no new semi-annual filings are posted (filings are submitted twice yearly, so most weeks see no change).

### Annual lobbying spend on environmental bills

{% include charts/dash_lobbying_spend_trend.html %}

### Top employers — most recent complete year

{% include charts/dash_lobbying_top_employers.html %}

### Environmental bills lobbied per year

{% include charts/dash_lobbying_bill_intensity.html %}

### Lobbying spend vs. enforcement actions

{% include charts/dash_lobbying_vs_enforcement.html %}

---

*Charts regenerated weekly from the latest available data. Last update visible in the [Actions log](https://github.com/nesanders/MAenvironmentaldata/actions/workflows/update-charts.yml).*
