---
layout: post
title: Revisiting the environmental justice implications of CSOs with 2022 data
ancillary: 0
---

In 2018, AMEND [featured]({% post_url 2018-04-25-necir-cso-ej %}) the first analysis of the distributional impacts of [combined sewer overflows (CSOs)](https://www.epa.gov/npdes/combined-sewer-overflows-csos) in Massachusetts, demonstrating that there were severe inequities in the extent to which different communities are burdened with sewage pollution based on race, language isolation, and income. This work was later published in the journal [Media and Communication](https://doi.org/10.17645/mac.v7i3.2136).

The analysis in 2018 was limited to [CSO data from 2011]({{ site.url }}{{ site.baseurl }}/data/NECIR_CSO.html) collected at that time by the [New England Center for Investigative Reporting](https://www.necir.org/).  Data from other years were not previously availble.

In 2021, Massachusetts [enacted a new law](https://malegislature.gov/Laws/SessionLaws/Acts/2020/Chapter322), the [Sewage Notification Act](https://www.wbur.org/news/2021/01/06/cso-notification-bill-sewage-river-baker), which [requires public notification](https://www.mass.gov/regulations/314-CMR-1600-notification-requirements-to-promote-public-awareness-of-sewage-pollution) of CSO discharges. This law generated a new data resource, a table in the [MA EEA Data Portal]({{ site.url }}{{ site.baseurl }}/data/EEADP_all.html) for CSO discharge events. 

The availability of this new dataset allows us to revisit the distributional impacts of CSO discharges in MA a decade after the dataset collected by NECIR in 2011. In particular, in this post, we examine the first five months of data collected under the new law, from the second half of 2022.  As we will see below, this new dataset has limitations, but it does allow us to draw some insight into how the water pollution conditions in the Commonwealth have changed over a decade that has seen the culmination of hundreds of millions of dollars of [sewage pollution mitigation work by MWRA](https://www.mwra.com/cso/pcmapa.html) and other sewer operators.

When comparing results in this analysis to the previous analysis of 2011 data, keep in mind that the 2022 data is available only for July through December and does not constitute a full year of reporting.

The [environmental justice data used in this analysis]({{ site.url }}{{ site.baseurl }}/data/EPA_EJSCREEN.html) comes from the [US EPA EJSCREEN tool](https://www.epa.gov/ejscreen/what-ejscreen). Latitude and longitude coordinates for the CSO outfalls were retrieved from [a state publication](https://www.mass.gov/doc/permittee-and-outfall-lists/download), also [archived on this site]({{ site.url }}{{ site.baseurl }}/data/ma_permittee-and-outfall-lists.xlsx).  Both the EJ SCREEN and CSO data are available in the [{{ site.data.site_config.site_abbrev }} database]({{ site.url }}{{ site.baseurl }}/data/index.html)

*[The code needed to reproduce this analysis using {{ site.data.site_config.site_abbrev }} data can be viewed and downloaded here](https://github.com/nesanders/MAenvironmentaldata/blob/master/analysis/EEA_DP_CSO_map.py)*

## Background on CSOs and EJ

For more background information about CSO discharges and environmental justice, see the [2018 post on AMEND]({{ site.url }}{{ site.baseurl }}/2018/04/25/necir-cso-ej.html).

## Characteristics of new CSO discharge dataset

The first sewage discharge report in the EEA Data Portal was from June 30th, 2022.  In this analysis, we consider only final validated reports (i.e. `reporterClass == 'Verified Data Report'`), not initial public notifications (i.e. we exclude reports of class `Public Notification Report`).

### How many reports were there?

Looking at the **count** of discharge reports over time, we can see that reports substantially began in July of 2021. 
As expected, the report volume recedes somewhat in the late-fall / winter months (November and later) when rainfall decreases.

We can also see that the vast majority of reports are for untreated CSOs.
A smaller fraction of reports are for treated CSOs.
Very few 'blended' discharges and SSOs are being reported.

{% include /charts/EEA_DP_CSO_counts_per_month.html %}

However, looking at the **volume** (i.e. severity) of discharges reported over time shows a very different picture.
Still, the plurality of discharge volume each month is from untreated CSOs, whose effluent can be expected to carry the greatest risk to public health from bacterial load.
Still, only a small volume of discharges can be attributed to treated CSOs.
However, while they are a small fraction of the count of discharges, the volume of partially treated CSO and 'blended' discharge is very high relative to their count.
In December of 2022, the plurality of discharge was actually in the form of 'blended' discharge.

{% include /charts/EEA_DP_CSO_volume_per_month.html %}

According to the [Massachusetts Water Resources Authority](https://www.mwra.com/harbor/html/blending_reporting.htm) (MWRA), 'blended' discharge from their system constitutes "excess primary-treated flow [that has been] diverted around the secondary process and then blended with the secondary effluent before being disinfected and discharged." 
In other words, part of the effluent in this discharge skipped the stage where microbes are applied to break down solids and contaminants (the secondary treatment process), meaning that the toxicity of the discharge may be higher than fully treated sewage.
The notification regulations [required](https://www.mass.gov/doc/314-cmr-1600-notification-requirements-to-promote-public-awareness-of-sewage-pollution-note-to-reviewers/download) reporting of 'blended' discharges following public comment from the [Massachusetts Rivers Alliance](https://www.massriversalliance.org/sewage-right-to-know) and other advocates.

In the analysis below, we combine discharges of all types (i.e. we treat every gallon of discharge as equivalent).

### What fraction of reports have non-zero, non-modeled discharge volumes?

The [final discharge notification regulations](https://www.mass.gov/doc/314-cmr-1600-notification-requirements-to-promote-public-awareness-of-sewage-pollution-1/download) require reporting of discharge volumes after the event has ceased, but give sewer operators some leeway in what they report.
In particular, some sewer operators have not installed metering systems to directly measure the amount of sewage they discharge and, instead, are allowed to report the "Estimated volume of the discharge or overflow based on the average discharge or overflow from data reported to the Department and/o rEPA for the prior three calendar years, taking into consideration historical information for the projected rainfall event, if possible, as set forth in the permittee’s CSO Public Notification Plan."

Unfortunately, the state Data Portal does not indicate which reports come from modeled (3-year average) data and which are directly metered.
As a simplistic way to estimate the number of modeled (non-metered) reports, we look for reports that are rounded.
To generate the plot below, any report rounded to the nearest 1,000 gallons is assumed to be a modeled volume estimate.

Roughly half of untreated CSO discharges seem to be based on modeled estimates. The number of treated and blended CSO discharges that are modeled is much lower. Furthermore, a small fraction (a few percent) of 'final validated reports' contain no volume information about the discharge.

{% include /charts/EEA_DP_CSO_non_zero_volume.html %}

### How does this vary by sewer operator?

Different sewer operators have vastly different patterns of discharge by effluent type.
The six largest dischargers by volume are Lowell Regional, the City of Fall River, the City of New Bedford, and Springfield Water & Sewer, the MWRA (which encompasses many cities and towns in the Greater Boston area), and the City of Holyoke.
Among these, New Bedford and Springfield report almost entirely untreated CSO discharge.
Lowell, meanwhile, reports primarily 'blended' discharge.
The MWRA reports a fairly even mix of treated CSO and 'blended' discharge.
Fall River, meanwhile, reports mostly non-'blended' partially treated discharge.
Holyoke reports mostly untrteated CSO and some treated CSO discharge.

{% include /charts/EEA_DP_CSO_volume_per_operator.html %}

## Locations of CSO discharges

The map below shows the location of CSO outfalls in MA (points), with overlays showing the sum total of CSO discharge volume in 2022 by watershed, municipality, and Census block group (use the control at right to toggle these layers).  Watershed names are labeled in blue.

{% raw %}
<iframe frameborder="no" border="0" marginwidth="0" marginheight="0" width="700" height="400" src="../../../assets/maps/MAEEADP_2022_map_total.html"></iframe>
<p><em><a target="_blank" href="../../../assets/maps/MAEEADP_2022_map_total.html">Click here to view map in a separate page</a></em></p>
{% endraw %}

You can click on each CSO outfall point to report information about its location, discharge frequency, and volume.

Additional mapping tools are available at [MassGIS](http://maps.massgis.state.ma.us/map_ol/ej.php) and [EJSCREEN](https://www.epa.gov/ejscreen/what-ejscreen).


## Environmental Justice community characteristics

The following maps visualize major EJ population characteristics by similar watershed, municipality, and Census block group levels as the previous map.  Refer to the [EJSCREEN data page]({{ site.url }}{{ site.baseurl }}/data/EPA_EJSCREEN.html) and links therein for more information about the definition of each demographic metric.  The watershed and municipal-level characteristics are calculated based on a population-weighted average over the Census block group-level data.

### Minority Racial Demographics

{% raw %}
<iframe frameborder="no" border="0" marginwidth="0" marginheight="0" width="700" height="400" src="../../../assets/maps/MAEEADP_2022_map_EJ_MINORPCT.html"></iframe>
<p><em><a target="_blank" href="../../../assets/maps/MAEEADP_2022_map_EJ_MINORPCT.html">Click here to view map in a separate page</a></em></p>
{% endraw %}



### Linguistic Isolation

{% raw %}
<iframe frameborder="no" border="0" marginwidth="0" marginheight="0" width="700" height="400" src="../../../assets/maps/MAEEADP_2022_map_EJ_LINGISOPCT.html"></iframe>
<p><em><a target="_blank" href="../../../assets/maps/MAEEADP_2022_map_EJ_LINGISOPCT.html">Click here to view map in a separate page</a></em></p>
{% endraw %}



### Low Income Status

{% raw %}
<iframe frameborder="no" border="0" marginwidth="0" marginheight="0" width="700" height="400" src="../../../assets/maps/MAEEADP_2022_map_EJ_LOWINCPCT.html"></iframe>
<p><em><a target="_blank" href="../../../assets/maps/MAEEADP_2022_map_EJ_LOWINCPCT.html">Click here to view map in a separate page</a></em></p>
{% endraw %}



## Aggregate level EJ population statistics

We aggregate the Census block group level EJSCREEN data (2017 edition) to the watershed and municipality level to understand how these geographic areas vary in their EJ populations.

## By watershed

{% include /charts/EJSCREEN_demographics_watershed.html %}


## By municipality

{% include /charts/EJSCREEN_demographics_municipality.html %}




## Correlation between CSO discharge and EJ factors

We explore the relationship between CSO discharge volumes within different geographic areas and their EJ population characteristics.  We use bootstrap resampling to visualize the trend and uncertainty in the population-weighted mean discharge volume estimate in equal-sized bins of watersheds (figures below). We estimate the univariate dependence of CSO discharge on each EJ factor, and its 90% posterior (confidence) interval, with a population-weighted logarithmic regression model.  For the purpose of this correlation analysis, 2023 EPA EJSCREEN demographic data is used. A detailed explanation of the methodology used in this analysis is provided [here]({% post_url 2019-03-23-necir-cso-ej_modeling %}) and additional model diagnostics are available [here]({% post_url 2023-02-04-eea-dp-cso-ej_modeling %}).


### Relationship with linguistic isolation

Linguistic isolation is defined as the fraction of households with no adult who is a "very good" or better English speaker.  Click on the label in the plot legend to toggle display of the individual watershed points, which display detailed annotation when hovering your cursor.

{% include /charts/MAEEADP_2022_EJSCREEN_correlation_bywatershed_LINGISOPCT.html %}

We find a statistically significant and moderately strong relationship between CSO discharge volumes and linguistic isolation.  More linguistically isolated communities, like the Mystic River watershed, have much higher CSO discharge volumes.  On average, **watersheds that have twice the level of linguistic isolation tend to have {{ site.data.facts_EEA_DP_CSO.depend_cso_LINGISOPCT_Watershed }} the level of CSO discharge.**


### Relationship with racial minority demographics

The plot below is similar to the one above for linguistic isolation, except the x-axis reflects the fraction of the population identifying as non-white.

{% include /charts/MAEEADP_2022_EJSCREEN_correlation_bywatershed_MINORPCT.html %}

Similar to the linguistic isolation trend, communities that are less predominantly white have much higher CSO discharge volumes.  On average, **watersheds that have twice the level of minority populations tend to have {{ site.data.facts_EEA_DP_CSO.depend_cso_MINORPCT_Watershed }} the level of CSO discharge.**


### Relationship with income

The plot below is similar to the one above for linguistic isolation, except the x-axis reflects the fraction of the population with an income level less than twice the federal poverty limit.

{% include /charts/MAEEADP_2022_EJSCREEN_correlation_bywatershed_LOWINCPCT.html %}

Similar to the linguistic isolation trend, communities that are less predominantly white have much higher CSO discharge volumes.  On average, **watersheds that have twice the level of low income populations tend to have {{ site.data.facts_EEA_DP_CSO.depend_cso_LOWINCPCT_Watershed }} the level of CSO discharge.**

# Conclusions

The new sewage discharge notification system and the data table of discharge reports now integrated with the MA EEA Data Portal provide a powerful tool for monitoring and understanding the effects of sewage pollution in Massachusetts.
Although the analysis presented here represents only the first six months of data reported under this system, it helps us anticipate what we can seek to learn as monitoring continues over time.
Unfortunately, these initial results suggest that the inequities in our water infrastructure have not been substantially mitigated in the past decade. 
The significant overburdening of environmental justice communities by water pollution is an ongoing challenge.
Watersheds with higher concentrations of low income, racial minority, and linguistically isolated residents continue to bear far higher levels of sewage pollution.


