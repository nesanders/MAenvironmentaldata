---
layout: post
title: "Three years of MA sewage pollution data: trends, rainfall, and persistent environmental justice disparities"
ancillary: 0
---

*This post extends the analysis from our earlier posts, ["Revisiting the environmental justice implications of CSOs with 2022 data"]({% post_url 2023-02-04-eea-dp-cso-ej %}) and ["The first year of data from MA's new sewage pollution notification system"]({% post_url 2023-10-20-eea-dp-cso-ej %}), now incorporating the full dataset through December 2025.*

In 2021, Massachusetts [enacted the Sewage Notification Act](https://malegislature.gov/Laws/SessionLaws/Acts/2020/Chapter322), which [requires public notification](https://www.mass.gov/regulations/314-CMR-1600-notification-requirements-to-promote-public-awareness-of-sewage-pollution) of combined sewer overflow (CSO) discharges.  The first discharge report appeared in the [MA EEA Data Portal]({{ site.url }}{{ site.baseurl }}/data/EEADP_all.html) in late June 2022.  We now have nearly three and a half years of data — enough to begin examining year-over-year trends, to assess whether reported discharge volumes are correlated with rainfall, and to evaluate whether the environmental justice disparities documented in our earlier analyses persist over time.

The [environmental justice data used in this analysis]({{ site.url }}{{ site.baseurl }}/data/EPA_EJSCREEN.html) comes from the [US EPA EJSCREEN tool](https://www.epa.gov/ejscreen/what-ejscreen) (2023 demographics). Latitude and longitude coordinates for the CSO outfalls were retrieved from [a state publication](https://www.mass.gov/doc/permittee-and-outfall-lists/download), also [archived on this site]({{ site.url }}{{ site.baseurl }}/data/ma_permittee-and-outfall-lists.xlsx). The Massachusetts heavy-rain-day data used for context counts, for each calendar year, the number of days on which at least 1 inch of precipitation was recorded at each MA GHCN/COOP station (averaged across stations reporting that year), drawn from the [NOAA ACIS web service](https://www.rcc-acis.org/).  A 1-inch daily threshold is a common operational benchmark for events capable of triggering CSO overflows.

*[The code needed to reproduce this analysis using {{ site.data.site_config.site_abbrev }} data can be viewed and downloaded here](https://github.com/nesanders/MAenvironmentaldata/blob/master/analysis/EEA_DP_CSO_map.py)*

## Background on CSOs and EJ

For background information about CSO discharges and environmental justice, see the [2018 post on AMEND]({{ site.url }}{{ site.baseurl }}/2018/04/25/necir-cso-ej.html).

## Year-over-year trends in CSO discharge

### How does annual discharge compare across years, and how much is explained by rainfall?

The chart below shows total annual CSO discharge volume alongside the annual count of heavy rain days (days with ≥ 1 inch of precipitation, averaged across Massachusetts GHCN/COOP stations).  CSO systems overflow in response to intense rainfall events rather than total precipitation, so heavy-rain-day counts are a more direct driver of discharge than monthly averages.  Note that 2022 is a partial year — reporting under the Sewage Notification Act began on June 30, 2022, so the 2022 discharge figure covers only the second half of the calendar year.

{% include /charts/MAEEADP_through_2025_annual_precip_discharge.html %}

The pattern is striking: 2023 recorded the most heavy rain days of any recent year (~14 days with ≥ 1 inch across MA stations), and correspondingly saw the largest CSO discharge volume.  In contrast, 2024 and 2025 both had fewer heavy rain days (~10 and ~8 respectively), and discharge volumes fell accordingly.  This co-movement supports the interpretation that year-over-year variation in CSO discharge is largely weather-driven.

That said, even in the drier years of 2024 and 2025, discharge volumes remain substantial in absolute terms.  Reductions in discharge volume appear to reflect fewer extreme events, not improvements to underlying infrastructure.

### Does individual-day discharge track with rainfall?

The annual correlation above is suggestive, but CSO systems respond to individual storm events, not annual averages.  Most days — particularly dry ones — have zero reported discharges.  The chart below shows what fraction of days had any discharge at all, grouped by the prior 48-hour precipitation at MA weather stations.

{% include /charts/MAEEADP_through_2025_rainfall_discharge_freq.html %}

The pattern is clear: on days following dry conditions (less than 0.05 inches in the prior 48 hours), barely any discharges are reported.  That fraction rises steeply with rainfall, reaching the majority of heavy-rain days.

The scatter chart below shows the volume of those discharge days in more detail.  Each point is a (day, discharge type) pair on which at least one incident was reported, plotted against the prior 48-hour precipitation.  Colors distinguish discharge types: untreated CSOs (the largest category), treated CSOs, partially treated discharges, and sanitary sewer overflows (SSOs).

{% include /charts/MAEEADP_through_2025_rainfall_discharge_scatter.html %}

The y-axis is on a logarithmic scale to spread the large dynamic range of discharge volumes. The rainfall-responsiveness of the system is unmistakable: the highest-discharge days are tightly coupled to recent heavy precipitation, while the bulk of low-discharge events cluster near zero prior rainfall.  SSO events appear across the full rainfall range, consistent with their distinct failure modes (pump failures, force main breaks) that can occur independent of storm conditions.

**What about the dry-weather discharges?** A notable cluster of events occurs with near-zero prior-48-hour precipitation. Under [EPA's Nine Minimum Controls](https://www.epa.gov/sites/default/files/2015-10/documents/owm0030_2.pdf) and Massachusetts NPDES permits, [CSO discharges during dry weather are prohibited](https://www.mass.gov/guides/sanitary-sewer-systems-combined-sewer-overflows) and require immediate investigation. When they occur, typical causes include groundwater infiltration into aging pipes, illicit storm drain connections, and pump or equipment failures — all NPDES permit violations that utilities are required to investigate and correct. Some events near the left edge of the chart may also reflect precipitation that fell slightly outside the 48-hour window captured by our statewide station average. Bizer & Kirchhoff ([2022, *Water Science & Technology*](https://iwaponline.com/wst/article/86/11/2848/91816/Regression-modeling-of-combined-sewer-overflows-to)) found that log-transformed regression best fits CSO volume-rainfall relationships, consistent with the power-law pattern visible here.

### Annual discharge counts

While volume is the most important measure of the burden of sewage pollution, discharge counts tell a slightly different story — they reflect how many separate discharge events occurred, regardless of size.

{% include /charts/MAEEADP_through_2025_annual_count.html %}

The count trends broadly mirror volume, with 2023 showing the highest number of discharge events.  Because CSO events range widely in scale, a spike in counts does not always imply a proportional spike in volume.

### Trends by sewer operator

The following chart shows year-over-year discharge volumes for the largest reporting operators, excluding 2022 (the partial first year).  Each line connects a single operator's reported volume across years, making it easier to see which operators drive the overall pattern.

{% include /charts/MAEEADP_through_2025_annual_volume_by_operator.html %}

Several large operators (e.g. MWRA, Deer Island) account for a disproportionate share of total volume and also show the steepest year-to-year swings correlated with rainfall.  Operators whose volumes remain elevated even in drier years may face more persistent infrastructure challenges.

## Characteristics of the full dataset (June 2022 – December 2025)

### Discharge counts over time

The following chart shows the monthly count of discharge reports across all event types.  The seasonal pattern — higher in spring and fall wet seasons, lower in summer and winter — is consistent across all three full years.

{% include /charts/MAEEADP_through_2025_counts_per_month.html %}

The regularity of the seasonal cycle across years is consistent with CSO systems that overflow in response to precipitation: wet spring and fall seasons reliably produce more events regardless of annual totals.

### Discharge volume over time

The following chart shows total discharge volume by month. The scale of the 2023 wet season is clearly visible.

{% include /charts/MAEEADP_through_2025_volume_per_month.html %}

Several months in 2023 individually exceed the total volume of entire quarters in other years, illustrating how a single period of intense rainfall can dominate annual statistics.

### Volume by sewer operator

The following chart shows total discharge volume over the full period by sewer operator and event type.  A small number of operators account for the majority of reported volume.

{% include /charts/MAEEADP_through_2025_volume_per_operator.html %}

The concentration of volume among a few operators reflects both the size of their sewer systems and the degree to which those systems remain dependent on combined sewers.

### What fraction of reports have non-zero, non-modeled discharge volumes?

The following chart shows, by event type and year, what share of discharge reports include a measured (non-modeled, non-zero) volume estimate.

{% include /charts/MAEEADP_through_2025_non_zero_volume.html %}

Roughly half of untreated CSO reports continue to rely on modeled rather than metered volume estimates.  This limits the precision of any volume-based analysis and underscores the need for expanded outfall metering.

### Volume by receiving waterbody

The following chart shows total reported discharge volume over the full period broken down by the receiving waterbody identified in the report.

{% include /charts/MAEEADP_through_2025_volume_per_waterbody.html %}

A small number of waterbodies — particularly those adjacent to large urban sewer systems — receive the overwhelming majority of reported CSO volume.

## Locations of CSO discharges

The map below shows the location of CSO outfalls in MA (points), with overlays showing the sum total of CSO discharge volume over the full period by watershed, municipality, and Census block group.  Use the layer controls to switch between geographic aggregations.  Darker shading indicates higher total discharge volume.

{% raw %}
<iframe frameborder="no" border="0" marginwidth="0" marginheight="0" width="700" height="400" src="../../../assets/maps/MAEEADP_through_2025_map_total.html"></iframe>
<p><em><a target="_blank" href="../../../assets/maps/MAEEADP_through_2025_map_total.html">Click here to view map in a separate page</a></em></p>
{% endraw %}

## Environmental Justice community characteristics

The following maps visualize major EJ population characteristics at the watershed, municipality, and Census block group levels, using 2023 EPA EJSCREEN demographics.  These maps provide context for interpreting the discharge-EJ correlations below.

### Minority Racial Demographics

The percentage of Census block group residents who identify as non-white.  Areas with higher minority populations are shown in darker shades.

{% raw %}
<iframe frameborder="no" border="0" marginwidth="0" marginheight="0" width="700" height="400" src="../../../assets/maps/MAEEADP_through_2025_map_EJ_MINORPCT.html"></iframe>
<p><em><a target="_blank" href="../../../assets/maps/MAEEADP_through_2025_map_EJ_MINORPCT.html">Click here to view map in a separate page</a></em></p>
{% endraw %}

### Linguistic Isolation

The percentage of households where no adult speaks English "very well," a measure of language access barriers.

{% raw %}
<iframe frameborder="no" border="0" marginwidth="0" marginheight="0" width="700" height="400" src="../../../assets/maps/MAEEADP_through_2025_map_EJ_LINGISOPCT.html"></iframe>
<p><em><a target="_blank" href="../../../assets/maps/MAEEADP_through_2025_map_EJ_LINGISOPCT.html">Click here to view map in a separate page</a></em></p>
{% endraw %}

### Low Income Status

The percentage of residents with incomes below twice the federal poverty level.

{% raw %}
<iframe frameborder="no" border="0" marginwidth="0" marginheight="0" width="700" height="400" src="../../../assets/maps/MAEEADP_through_2025_map_EJ_LOWINCPCT.html"></iframe>
<p><em><a target="_blank" href="../../../assets/maps/MAEEADP_through_2025_map_EJ_LOWINCPCT.html">Click here to view map in a separate page</a></em></p>
{% endraw %}

## Aggregate EJ population statistics

The charts below summarize the distribution of EJ indicators across geographic units, weighted by population.  They provide context for how EJ characteristics are distributed across the areas that bear CSO discharge burdens.

### By watershed

{% include /charts/EJSCREEN_demographics_watershed.html %}

Watersheds that receive more CSO discharge tend to score higher on all three EJ indicators, a pattern explored in more detail in the regression analysis below.

### By municipality

{% include /charts/EJSCREEN_demographics_municipality.html %}

The municipality-level distribution shows similar patterns, with more urbanized municipalities (which tend to have older combined sewer infrastructure) also showing elevated EJ indicator values.

## Correlation between CSO discharge and EJ factors

We explore the relationship between total CSO discharge volumes (June 2022 – December 2025) within different geographic areas and their EJ population characteristics.  The methodology is identical to our earlier analyses: bootstrap resampling to visualize population-weighted mean discharge in equal-sized bins, with a population-weighted logarithmic regression model to estimate univariate dependence.  A detailed explanation is [here]({% post_url 2019-03-23-necir-cso-ej_modeling %}) and model diagnostics for this analysis are [here]({% post_url 2026-04-03-eea-dp-cso-ej_modeling %}).

### Relationship with linguistic isolation

{% include /charts/MAEEADP_through_2025_EJSCREEN_correlation_bywatershed_LINGISOPCT.html %}

Across the full three-year period, we continue to find a statistically significant relationship between CSO discharge and linguistic isolation.  On average, **watersheds that have twice the level of linguistic isolation tend to have {{ site.data.facts_MAEEADP_through_2025.depend_cso_LINGISOPCT_Watershed }} the level of CSO discharge.**

### Relationship with racial minority demographics

{% include /charts/MAEEADP_through_2025_EJSCREEN_correlation_bywatershed_MINORPCT.html %}

The relationship with racial minority demographics remains strong over the full period.  On average, **watersheds that have twice the level of minority populations tend to have {{ site.data.facts_MAEEADP_through_2025.depend_cso_MINORPCT_Watershed }} the level of CSO discharge.**

### Relationship with income

{% include /charts/MAEEADP_through_2025_EJSCREEN_correlation_bywatershed_LOWINCPCT.html %}

The income gradient is similarly persistent.  On average, **watersheds that have twice the level of low income populations tend to have {{ site.data.facts_MAEEADP_through_2025.depend_cso_LOWINCPCT_Watershed }} the level of CSO discharge.**

## Year-by-year EJ correlation

To test whether the EJ disparity is stable over time or driven by a single anomalous year, we fit the same watershed-level power-law regression independently for each calendar year (2023–2025; 2022 is excluded as a partial year beginning June 30).  We also include the 2011 estimate from the [original NECIR analysis]({% post_url 2018-04-25-necir-cso-ej %}) as a long-run reference point, extending the timeline back over a decade.  The chart shows the posterior median 2× growth ratio for each EJ variable in each year.

{% include /charts/MAEEADP_through_2025_annual_ej_beta_evolution.html %}

*The 2× growth ratio is the estimated multiplicative difference in CSO discharge volume between a watershed at the median EJ indicator level and one at twice that level.  Values above 1 indicate higher discharge burden in more-disadvantaged communities.  \*The 2011 point uses 2011 EJSCREEN demographics and NECIR discharge data; 2023–2025 use 2023 EJSCREEN demographics and EEA Data Portal data — a direct year-to-year comparison should account for these differences.*

The EJ disparities are consistent across years.  For minority population share, the 2× growth ratio was {{ site.data.facts_MAEEADP_through_2025.annual_ej_MINORPCT_2023 }} in 2023, {{ site.data.facts_MAEEADP_through_2025.annual_ej_MINORPCT_2024 }} in 2024, and {{ site.data.facts_MAEEADP_through_2025.annual_ej_MINORPCT_2025 }} in 2025.  For low-income share: {{ site.data.facts_MAEEADP_through_2025.annual_ej_LOWINCPCT_2023 }}, {{ site.data.facts_MAEEADP_through_2025.annual_ej_LOWINCPCT_2024 }}, and {{ site.data.facts_MAEEADP_through_2025.annual_ej_LOWINCPCT_2025 }}, respectively.  For linguistic isolation: {{ site.data.facts_MAEEADP_through_2025.annual_ej_LINGISOPCT_2023 }}, {{ site.data.facts_MAEEADP_through_2025.annual_ej_LINGISOPCT_2024 }}, and {{ site.data.facts_MAEEADP_through_2025.annual_ej_LINGISOPCT_2025 }}.  Point estimates are stable and consistently elevated across all three years.

## Conclusions

With nearly three and a half years of data from Massachusetts's sewage notification system, several patterns have become clear.

**Rainfall is the dominant driver of year-over-year variation in discharge volume.** The exceptional rainfall of 2023 drove a large spike in reported discharges, while drier conditions in 2024 and 2025 brought volumes down somewhat. This underscores the importance of comparing discharge trends on a rainfall-normalized basis, and of investing in infrastructure that can handle increasingly intense precipitation events as climate change progresses.

**Environmental justice disparities in sewage burden are persistent and consistent year-to-year.** Across all three full calendar years (2023–2025), communities with higher concentrations of racial minority, low income, and linguistically isolated residents bear disproportionately high levels of CSO discharge. Per-year regression estimates (watershed level) show the minority-population 2× growth ratio ranging from {{ site.data.facts_MAEEADP_through_2025.annual_ej_MINORPCT_2025 }} to {{ site.data.facts_MAEEADP_through_2025.annual_ej_MINORPCT_2023 }} across years — elevated in every year, and not trending downward.

**Significant data gaps remain.** Roughly half of untreated CSO discharge reports continue to use modeled (rather than metered) volume estimates, limiting the precision of this analysis. Investments in outfall metering would substantially improve the quality and utility of this public dataset.

---

*This post was prepared with assistance from [Claude](https://www.anthropic.com/claude) (Anthropic), an AI assistant, which helped structure the analysis, write code, and draft text. All data, methodology, and conclusions were reviewed and approved by the site authors.*
