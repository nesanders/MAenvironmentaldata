---
layout: post
title: "(DRAFT) Three years of MA sewage pollution data: trends, rainfall, and persistent environmental justice disparities"
ancillary: 0
---

*This post is in DRAFT status. It has not yet been fully completed and reviewed.*

*This post extends the analysis from our earlier posts, ["Revisiting the environmental justice implications of CSOs with 2022 data"]({% post_url 2023-02-04-eea-dp-cso-ej %}) and ["The first year of data from MA's new sewage pollution notification system"]({% post_url 2023-10-20-eea-dp-cso-ej %}), now incorporating the full dataset through December 2025.*

In 2021, Massachusetts [enacted the Sewage Notification Act](https://malegislature.gov/Laws/SessionLaws/Acts/2020/Chapter322), which [requires public notification](https://www.mass.gov/regulations/314-CMR-1600-notification-requirements-to-promote-public-awareness-of-sewage-pollution) of combined sewer overflow (CSO) discharges.  The first discharge report appeared in the [MA EEA Data Portal]({{ site.url }}{{ site.baseurl }}/data/EEADP_all.html) in late June 2022.  We now have nearly three and a half years of data — enough to begin examining year-over-year trends, to assess whether reported discharge volumes are correlated with rainfall, and to evaluate whether the environmental justice disparities documented in our earlier analyses persist over time.

The [environmental justice data used in this analysis]({{ site.url }}{{ site.baseurl }}/data/EPA_EJSCREEN.html) comes from the US EPA EJSCREEN tool (2023 demographics; note that [EJScreen was removed from EPA's website](https://envirodatagov.org/epa-removes-ejscreen-from-its-website/) in early 2025 — archived data remains available on [our data page]({{ site.url }}{{ site.baseurl }}/data/EPA_EJSCREEN.html)). Latitude and longitude coordinates for the CSO outfalls were retrieved from [a state publication](https://www.mass.gov/doc/permittee-and-outfall-lists/download), also [archived on this site]({{ site.url }}{{ site.baseurl }}/data/ma_permittee-and-outfall-lists.xlsx). For this analysis, rainfall data was newly acquired from the [NOAA ACIS web service](https://www.rcc-acis.org/). Using the NOAA data, we count the number of days on which at least 1 inch of precipitation as recorded across an average of Massachusetss [NOAA GHCN](https://www.ncei.noaa.gov/products/land-based-station/global-historical-climatology-network-daily) & [NWS COOP](https://www.weather.gov/coop/overview) stations.

*[The code needed to reproduce this analysis using {{ site.data.site_config.site_abbrev }} data can be viewed and downloaded here](https://github.com/nesanders/MAenvironmentaldata/blob/master/analysis/EEA_DP_CSO_map.py)*

## Background on CSOs and EJ

For background information about CSO discharges and environmental justice, see the [2018 post on AMEND]({{ site.url }}{{ site.baseurl }}/2018/04/25/necir-cso-ej.html).

## Year-over-year trends in CSO discharge


### Annual discharge counts

Discharge counts reflect how many separate discharge events occurred, regardless of size.

{% include /charts/MAEEADP_through_2025_annual_count.html %}

2023 shows the highest number of discharge events with significant decline year-over-year since then, such that 2025 saw little more than half the number of events as 2023. However, because CSO events range widely in scale, a spike in counts does not always imply a proportional spike in volume and, as we will see, changes in weather conditions may be the primary explanation for this trend.


### How has sewage discharge changed over the years?

The chart below shows total annual CSO discharge volume alongside the annual count of heavy rain days (days with ≥ 1 inch of precipitation, averaged across Massachusetts GHCN/COOP stations).  CSO systems overflow in response to intense rainfall events rather than total precipitation, so heavy-rain-day counts are a causal driver of sewage discharges.  Note that reporting under the Sewage Notification Act began on June 30, 2022, so the 2022 discharge figure covers only the second half of the calendar year.

{% include /charts/MAEEADP_through_2025_annual_precip_discharge.html %}

2023 recorded the most heavy rain days of any recent year (15 days with ≥ 1 inch across MA stations), and correspondingly saw large CSO discharge volume. 2024 saw somewhat fewer heavy rain days (9) and even higher discharge volume. 2025 had significantly fewer days of heavy discharge (5) and, correspondingly, less than half the total discharge of 2023 and 2024.

That said, even in the drier years like 2025, discharge volumes remain substantial in absolute terms (billions of gallons).

### Does individual-day discharge track with rainfall?

The annual correlation above is suggestive, but CSO systems respond to individual storm events, not annual sums.  Most days — particularly dry ones — have zero reported discharges.  The chart below shows what fraction of days had any discharge at all, grouped by the prior 48-hour precipitation at MA weather stations. Each day is assigned to exactly one discharge type to render the stacked bars — whichever type (CSO-Untreated → CSO-Treated → Partially Treated → SSO → Other) occurs first in that priority order.

{% include /charts/MAEEADP_through_2025_rainfall_discharge_freq.html %}

On days following dry conditions (less than 0.05 inches in the prior 48 hours), there is roughly a one third chance of having any discharge statewide. On days when the prior 48 hours have seen at least 0.05 inches of rainfall statewide, that change jumps by about a third to ~45%. The rate of discharge does not grow substantially (actually, it appears to decrease somewhat) on moderate-to-very heavy rainfall days (>0.25 inches).

The cumulative distribution below makes the rainfall-discharge relationship more precise.  The dashed line shows the distribution of prior 48-hour rainfall across all days; a colored solid line to the *right* of the dashed line means that event type is disproportionately concentrated on wetter days relative to the average day. We can see that SSOs have the highest association with very wet weather days.

{% include /charts/MAEEADP_through_2025_rainfall_cdf.html %}

The scatter chart below breaks down this trend in terms of the volume of discharge.  Each point is a (day, discharge type) pair on which at least one incident was reported, plotted against the prior 48-hour precipitation.  Colors distinguish discharge types: untreated CSOs, treated CSOs, partially treated discharges, and sanitary sewer overflows (SSOs).

{% include /charts/MAEEADP_through_2025_rainfall_discharge_scatter.html %}

The y-axis is on a logarithmic scale to spread the large dynamic range of discharge volumes. There is no evident relationship between the severity of rainfall and the volume of CSO discharge. While SSO events tend to have limited total volume (often less than a million gallons), they are more associated with very heavy rainfall days, indicating that extreme [stormwater inflow](https://en.wikipedia.org/wiki/Infiltration_and_inflow) is a primary cause of Massachusetts SSOs. 

Bizer & Kirchhoff ([2022, *Water Science & Technology*](https://iwaponline.com/wst/article/86/11/2848/91816/Regression-modeling-of-combined-sewer-overflows-to)) studied CSO systems in Maryland and found that, in that system, discharge frequency increases with total rainfall, such that CSOs were all but certain to occur above 1.5 inches of rainfall.

**What about the dry-weather discharges?** A notable cluster of events occurs with near-zero prior-48-hour precipitation. Under [EPA's Nine Minimum Controls](https://www.epa.gov/sites/default/files/2015-10/documents/owm0030_2.pdf) and Massachusetts NPDES permits, [CSO discharges during dry weather are prohibited](https://www.mass.gov/guides/sanitary-sewer-systems-combined-sewer-overflows) and require immediate investigation. When they occur, typical causes include groundwater infiltration into aging pipes, illicit storm drain connections, and pump or equipment failures — all NPDES permit violations that utilities are required to investigate and correct. Some events near the left edge of the chart may also reflect precipitation that fell slightly outside the 48-hour window captured by our statewide station average. 

### Trends by sewer operator

The following chart shows year-over-year discharge volumes for the largest reporting operators, excluding 2022 (the partial first year).  Each line connects a single operator's reported volume across years, making it easier to see which operators drive the overall pattern.

{% include /charts/MAEEADP_through_2025_annual_volume_by_operator.html %}

Several large operators (e.g. MWRA, Lowell) account for a large share of total volume and also show the steepest declines since 2023, which may be correlated with favorable rainfall. Operators whose volumes remain elevated even in drier years (e.g., New Bedford and Holyoke) may face more persistent infrastructure challenges.

## Characteristics of the full dataset (June 2022 – December 2025)

### Discharge counts over time

The following chart shows the monthly count of discharge reports across all event types.  The seasonal pattern — higher in spring and fall wet seasons, lower in summer and winter — is consistent across all three full years.

{% include /charts/MAEEADP_through_2025_counts_per_month.html %}

The regularity of the seasonal cycle across years is consistent with CSO systems that overflow in response to precipitation: wet spring and fall seasons reliably produce more events regardless of annual totals.

### Discharge volume over time

The following chart shows total discharge volume by month. The [exceptionally wet winter](https://www.climate.gov/news-features/understanding-climate/us-climate-summary-january-2024) of 2024 and its [associated](https://www.cambridgepublichealth.org/updated-avoid-contact-with-the-alewife-brook-and-the-charles-river-in-cambridge-due-to-potential-harmful-bacteria-and-other-pollutants-until-january-13-2024/) [CSO discharges](https://mysticriver.org/news/2025/1/30/csos-on-the-mystic-2024) particularly is clearly visible.

{% include /charts/MAEEADP_through_2025_volume_per_month.html %}

### Volume by sewer operator

The following chart shows total discharge volume over the full period by sewer operator and event type.  A small number of operators account for the majority of reported volume.

{% include /charts/MAEEADP_through_2025_volume_per_operator.html %}

The concentration of volume among a few operators reflects both the size of their sewer systems and the degree to which those systems remain dependent on combined sewers and/or other persistent infrastructural defficiencies. It is notable that MWRA, Lowell, and Fall River continue to have substantial fractions of ['blended' discharge](https://openamend.org/2023/02/04/eea-dp-cso-ej.html#:~:text=According%20to%20the%20Massachusetts%20Water%20Resources%20Authority%20(MWRA)%2C%20%E2%80%98blended%E2%80%99%20discharge).

### What fraction of reports have non-zero, non-modeled discharge volumes?

**TODO: update this with annual breakdown**

The following chart shows, by event type and year, what share of discharge reports include a measured (non-modeled, non-zero) volume estimate.

{% include /charts/MAEEADP_through_2025_non_zero_volume.html %}

Roughly half of untreated CSO reports continue to rely on modeled rather than metered volume estimates.  This limits the precision of any volume-based analysis and underscores the need for expanded outfall metering.

### Volume by receiving waterbody

The following chart shows total reported discharge volume over the full period broken down by the receiving waterbody identified in the report.

{% include /charts/MAEEADP_through_2025_volume_per_waterbody.html %}

A small number of waterbodies — particularly those adjacent to large urban sewer systems — receive the overwhelming majority of reported CSO volume.

## Locations of CSO discharges

**TODO: Fix discharge coloring by watershed**

The map below shows the location of CSO outfalls in MA (points), with overlays showing the sum total of CSO discharge volume over the full period by watershed, municipality, and Census block group.  Use the layer controls to switch between geographic aggregations.  Darker shading indicates higher total discharge volume.

{% raw %}
<iframe frameborder="no" border="0" marginwidth="0" marginheight="0" width="700" height="400" src="../../../assets/maps/MAEEADP_through_2025_map_total.html"></iframe>
<p><em><a target="_blank" href="../../../assets/maps/MAEEADP_through_2025_map_total.html">Click here to view map in a separate page</a></em></p>
{% endraw %}

## Environmental Justice community characteristics

**TODO: Link to plots on earlier posts, which are unchanged.**

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

**TODO: Review and update**

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

*This post was prepared with assistance from [Claude](https://www.anthropic.com/claude), an AI assistant, which helped structure the analysis, write code, and draft text. All data, methodology, and conclusions were reviewed and approved by [the site author](https://github.com/nesanders).*
