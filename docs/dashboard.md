---
layout: post
title: "Live Data Dashboard"
permalink: /dashboard.html
---

Charts on this page are regenerated automatically each week from the latest available data.
For full analysis and narrative context, follow the links in each section.

*[GitHub Actions run history](https://github.com/nesanders/MAenvironmentaldata/actions/workflows/update-charts.yml)*

---

## MA DEP Staffing

Data: [MA DEP staff payroll records]({{ site.url }}{{ site.baseurl }}/data/MADEP_staff.html)
— [VisibleGovernment]({{ site.url }}{{ site.baseurl }}/data/MADEP_staff.html) through 2016,
[MA Comptroller]({{ site.url }}{{ site.baseurl }}/data/MADEP_staff.html) (SODA API) 2010–present.
Full analysis: [Staff Changes at the MADEP Over Time]({{ site.url }}{{ site.baseurl }}/2017/03/15/dep-staff-changes.html).

<details>
<summary>About this data and methodology</summary>

Payroll records from two sources are merged on employee name and calendar year, allowing a
continuous series from 2004 onward. Staffing counts are tabulated by calendar year. Funding
data comes from the <a href="{{ site.url }}{{ site.baseurl }}/data/MassBudget_environmental.html">MassBudget environmental appropriations database</a>,
inflation-adjusted to 2015 dollars using the SSA Average Wage Index. Seniority is estimated
as the number of years each employee appears in the combined dataset relative to 2004, the
first year of records.

The correlation between annual DEP headcount and total agency budget is
{{ site.data.facts_DEPstaff.cor_staff_funding }}% (p={{ site.data.facts_DEPstaff.cor_staff_funding_p }}).
Note that the budget series uses reported administrative appropriations and may not capture
all funding sources. See the <a href="{{ site.url }}{{ site.baseurl }}/2017/03/15/dep-staff-changes.html">2017 staffing post</a>
for detailed caveats on data completeness and the merger of the two payroll sources.

</details>

### Overall staffing levels

{% include charts/dash_MADEP_staffing_overall.html %}

### Staffing vs. agency funding

*Note: budget data shown reflects 2015 inflation-adjusted values and does not update automatically. Current MassBudget source is unavailable as of 2026.*

{% include charts/dash_MADEP_staffing_overall_funding.html %}

### Staff seniority over time

{% include charts/dash_MADEP_staffing_seniority.html %}

*Note: Seniority data is only available through 2016 from VisibleGovernment payroll records. While staffing levels have been updated with more recent Comptroller data, seniority calculations are not available after 2016.*

---

## MA DEP Enforcement Actions

Data: [MA DEP enforcement actions]({{ site.url }}{{ site.baseurl }}/data/MADEP_enforcement_actions.html).
Full analysis: [Changes in Enforcement by MA DEP Over Time]({{ site.url }}{{ site.baseurl }}/2017/04/02/dep-enforcements.html).

<details>
<summary>About this data and methodology</summary>

Enforcement action counts are tallied by calendar year from DEP's publicly released enforcement
reports. Environmental media topics (wetlands, Chapter 91, NPDES, water supply, etc.) are
assigned by keyword matching on enforcement record descriptions. Budget data is the same
inflation-adjusted MassBudget series used in the staffing section.

The correlation between annual enforcement counts and agency budget is
{{ site.data.facts_DEPenforce.cor_enforcement_funding }}%.
Administrative Consent Orders with Penalties (ACOPs) are identified as a subset of consent orders;
penalty amounts are estimated using bootstrap resampling with 90% confidence intervals.
See the <a href="{{ site.url }}{{ site.baseurl }}/2017/04/02/dep-enforcements.html">2017 enforcement post</a>
for the full methodology.

</details>

### Total enforcement actions

{% include charts/dash_MADEP_enforcement_overall.html %}

### Enforcement actions vs. agency budget

*Note: budget data shown reflects 2015 inflation-adjusted values and does not update automatically. Current MassBudget source is unavailable as of 2026.*

{% include charts/dash_MADEP_enforcement_vsbudget.html %}

### Enforcement actions by topic

{% include charts/dash_MADEP_enforcement_bytopic.html %}

---

## State Environmental Agency Budgets

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

*Note: ECOS budget data is fetched manually and does not update automatically each week. Last updated [check commit history](https://github.com/nesanders/MAenvironmentaldata).*

{% include charts/dash_ECOS_budget_percap_peryear_bystate.html %}

---

## CSO Discharge Trends

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

## Modeled vs. Metered Discharge Reports

Data: [MA EEA Data Portal — CSO discharge reports]({{ site.url }}{{ site.baseurl }}/data/EEADP_all.html).

<details>
<summary>About this data and methodology</summary>

Reported discharge volumes often contain round numbers that suggest estimation rather than
direct metering. Using a heuristic that flags volumes rounded to the nearest 1,000 gallons
as "likely modeled," this chart shows the monthly fraction of reports using estimated versus
metered discharge volumes. CSO operators may estimate discharge volume when direct measurement
is not available, particularly during early-response phases of an event.

</details>

### Monthly fraction of likely-modeled discharge reports

{% include charts/dash_MAEEADP_dashboard_modeled_vs_metered_fraction.html %}

---

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

*Charts regenerated weekly from the latest available data. Last update visible in the [Actions log](https://github.com/nesanders/MAenvironmentaldata/actions/workflows/update-charts.yml).*
