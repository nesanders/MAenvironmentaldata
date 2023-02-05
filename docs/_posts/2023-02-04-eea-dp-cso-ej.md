---
layout: post
title: Revisiting the environmental justice implications of CSOs with 2022 data
ancillary: 0
---

In 2018, AMEND [featured]({% post_url 2018-04-25-necir-cso-ej %}) the first analysis of the distributional impacts of [combined sewer overflows (CSOs)](https://www.epa.gov/npdes/combined-sewer-overflows-csos) in Massachusetts, demonstrating that there were severe inequities in the extent to which different communities are burdened with sewage pollution based on race, language isolation, and income. This work was later published in the journal [Media and Communication](https://doi.org/10.17645/mac.v7i3.2136).

The analysis in 2018 was limited to [CSO data from 2011]({{ site.url }}{{ site.baseurl }}/data/NECIR_CSO.html) collected at that time by the [New England Center for Investigative Reporting](https://www.necir.org/).  Data from other years were not previously availble.

In 2021, Massachusetts [enacted a new law](https://malegislature.gov/Laws/SessionLaws/Acts/2020/Chapter322), the [Sewage Notification Act](https://www.wbur.org/news/2021/01/06/cso-notification-bill-sewage-river-baker), which [requires public notification](https://www.mass.gov/regulations/314-CMR-1600-notification-requirements-to-promote-public-awareness-of-sewage-pollution) of CSO discharges. This law generated a new data resource, a table in the [MA EEA Data Portal]({{ site.url }}{{ site.baseurl }}/data/EEADP_all.html) for CSO discharge events. 

The availability of this new dataset allows us to revisit the distributional impacts of CSO discharges in MA a decade after the dataset collected by NECIR in 2011. In particular, in this post, we examine the first full year of data collected under the new law, from 2022.  As we will see below, this new dataset has limitations, but it does allow us to draw some insight into how the water pollution conditions in the Commonwealth have changed over a decade that has seen the culmination of hundreds of millions of dollars of [sewage pollution mitigation work by MWRA](https://www.mwra.com/cso/pcmapa.html) and other sewer operators.

The [environmental justice data used in this analysis]({{ site.url }}{{ site.baseurl }}/data/EPA_EJSCREEN.html) comes from the [US EPA EJSCREEN tool](https://www.epa.gov/ejscreen/what-ejscreen). Latitude and longitude coordinates for the CSO outfalls were retrieved from [a state publication](https://www.mass.gov/doc/permittee-and-outfall-lists/download), also [archived on this site]({{ site.url }}{{ site.baseurl }}/data/ma_permittee-and-outfall-lists.xlsx).  Both the EJ SCREEN and CSO data are available in the [{{ site.data.site_config.site_abbrev }} database]({{ site.url }}{{ site.baseurl }}/data/index.html)

*[The code needed to reproduce this analysis using {{ site.data.site_config.site_abbrev }} data can be viewed and downloaded here](https://github.com/nesanders/MAenvironmentaldata/blob/master/analysis/EEA_DP_CSO_map.py)*

## Background on CSOs and EJ

For more background information about CSO discharges and environmental justice, see the [2018 post on AMEND]({{ site.url }}{{ site.baseurl }}/2018/04/25/necir-cso-ej.html).

## Characteristics of new CSO discharge dataset

## Locations of CSO discharges

The map below shows the location of CSO outfalls in MA (points), with overlays showing the sum total of CSO discharge volume in 2022 by watershed, municipality, and Census block group (use the control at right to toggle these layers).  Watershed names are labeled in blue.

{% raw %}
<iframe frameborder="no" border="0" marginwidth="0" marginheight="0" width="700" height="400" src="../../../assets/maps/MAEEADP_CSO_map_total.html"></iframe>
<p><em><a target="_blank" href="../../../assets/maps/MAEEADP_CSO_map_total.html">Click here to view map in a separate page</a></em></p>
{% endraw %}

You can click on each CSO outfall point to report information about its location, discharge frequency, and volume.

Additional mapping tools are available at [MassGIS](http://maps.massgis.state.ma.us/map_ol/ej.php) and [EJSCREEN](https://www.epa.gov/ejscreen/what-ejscreen).


## Environmental Justice community characteristics

The following maps visualize major EJ population characteristics by similar watershed, municipality, and Census block group levels as the previous map.  Refer to the [EJSCREEN data page]({{ site.url }}{{ site.baseurl }}/data/EPA_EJSCREEN.html) and links therein for more information about the definition of each demographic metric.  The watershed and municipal-level characteristics are calculated based on a population-weighted average over the Census block group-level data.

### Minority Racial Demographics

{% raw %}
<iframe frameborder="no" border="0" marginwidth="0" marginheight="0" width="700" height="400" src="../../../assets/maps/MAEEADP_CSO_map_EJ_MINORPCT.html"></iframe>
<p><em><a target="_blank" href="../../../assets/maps/MAEEADP_CSO_map_EJ_MINORPCT.html">Click here to view map in a separate page</a></em></p>
{% endraw %}



### Linguistic Isolation

{% raw %}
<iframe frameborder="no" border="0" marginwidth="0" marginheight="0" width="700" height="400" src="../../../assets/maps/MAEEADP_CSO_map_EJ_LINGISOPCT.html"></iframe>
<p><em><a target="_blank" href="../../../assets/maps/MAEEADP_CSO_map_EJ_LINGISOPCT.html">Click here to view map in a separate page</a></em></p>
{% endraw %}



### Low Income Status

{% raw %}
<iframe frameborder="no" border="0" marginwidth="0" marginheight="0" width="700" height="400" src="../../../assets/maps/MAEEADP_CSO_map_EJ_LOWINCPCT.html"></iframe>
<p><em><a target="_blank" href="../../../assets/maps/MAEEADP_CSO_map_EJ_LOWINCPCT.html">Click here to view map in a separate page</a></em></p>
{% endraw %}



## Aggregate level EJ population statistics

We aggregate the Census block group level EJSCREEN data to the watershed and municipality level to understand how these geographic areas vary in their EJ populations.  

## By watershed

{% include /charts/EJSCREEN_demographics_watershed.html %}


## By municipality

{% include /charts/EJSCREEN_demographics_municipality.html %}




## Correlation between CSO discharge and EJ factors

We explore the relationship between CSO discharge volumes within different geographic areas and their EJ population characteristics.  We use using bootstrap resampling to visualize the trend and uncertainty in the population-weighted mean discharge volume estimate in equal-sized bins of watersheds (figures below). We estimate the univariate dependence of CSO discharge on each EJ factor, and its 90% posterior (confidence) interval, with a population-weighted logarithmic regression model.  A detailed explanation of the methodology used in this analysis is provided [here]({% post_url 2019-03-23-necir-cso-ej_modeling %}).


### Relationship with linguistic isolation

Linguistic isolation is defined as the fraction of households with no adult who is a "very good" or better English speaker.  Click on the label in the plot legend to toggle display of the individual watershed points, which display detailed annotation when hovering your cursor.

{% include /charts/MAEEADP_EJSCREEN_correlation_bywatershed_LINGISOPCT.html %}

We find a statistically significant and moderately strong relationship between CSO discharge volumes and linguistic isolation.  More linguistically isolated communities, like the Mystic River watershed, have much higher CSO discharge volumes.  On average, **watersheds that have twice the level of linguistic isolation tend to have {{ site.data.facts_EEA_DP_CSO.depend_cso_LINGISOPCT }} the level of CSO discharge.**


### Relationship with racial minority demographics

The plot below is similar to the one above for linguistic isolation, except the x-axis reflects the fraction of the population identifying as non-white.

{% include /charts/MAEEADP_EJSCREEN_correlation_bywatershed_MINORPCT.html %}

Similar to the linguistic isolation trend, communities that are less predominantly white have much higher CSO discharge volumes.  On average, **watersheds that have twice the level of minority populations tend to have {{ site.data.facts_EEA_DP_CSO.depend_cso_MINORPCT }} the level of CSO discharge.**


### Relationship with income

The plot below is similar to the one above for linguistic isolation, except the x-axis reflects the fraction of the population with an income level less than twice the federal poverty limit.

{% include /charts/MAEEADP_EJSCREEN_correlation_bywatershed_LOWINCPCT.html %}

Similar to the linguistic isolation trend, communities that are less predominantly white have much higher CSO discharge volumes.  On average, **watersheds that have twice the level of low income populations tend to have {{ site.data.facts_EEA_DP_CSO.depend_cso_LOWINCPCT }} the level of CSO discharge.**


