---
layout: post
title: Environmental justice implications of CSO outfall distribution
---

Many of the sewer systems throughout Massachusetts are designed to discharge raw or partially treated sewage into rivers and other public waters when the sewers become overwhelmed, for example during rainstorm events.  These [combined sewer overflow (CSO)](https://www.epa.gov/npdes/combined-sewer-overflows-csos) discharges can endanger public health by exposing people to elevated levels of bacteria in waters they may use for recreation, and have ecological impacts including the introduction of chemical contaminants to the ecosystem and contributing to eutrophication (excessive nutrient).  This analysis seeks to understand if and how the spatial distribution of these CSO discharges in Massachusetts differentially impacts vulnerable populations, in order to interpret the [Environmental Justice](https://www.epa.gov/environmentaljustice) (EJ) implications of these systems.

The [CSO data used in this analysis]({{ site.url }}{{ site.baseurl }}/data/NECIR_CSO.html) comes from the [New England Center for Investigative Reporting](https://www.necir.org/) based on a survey of New England CSOs they performed in 2011.  Unfortunately, more recent data is not available statewide because there is not a standardized reporting system for these discharges.  The [environmental justice data used in this analysis]({{ site.url }}{{ site.baseurl }}/data/EPA_EJSCREEN.html) comes from the [US EPA EJSCREEN tool](https://www.epa.gov/ejscreen/what-ejscreen).  Both are available in the [{{ site.data.site_config.site_abbrev }} database]({{ site.url }}{{ site.baseurl }}/data/index.html)

*[The code needed to reproduce this analysis using {{ site.data.site_config.site_abbrev }} data can be viewed and downloaded here](https://github.com/nesanders/MAenvironmentaldata/blob/master/analysis/NECIR_CSO_map.py)*

## Background on CSOs and EJ

These sewage discharges are associated with Combined Sewer Systems (CSSs), which are common in older urbanized districts like the major municipalities in New England.  Unlike separated sewer systems, which carry stormwater and sanitary sewage in separate pipes, combined systems comingle these flows.  As a result, excess flow in the stormwater system (as occurs during major rain events) inevitably leads to an overflow of the sanitary as well as the stormwater sewage.  The discharges occur at CSO outfalls, which are discharge pipes designed to transmit sewage flows to water bodies external to the sewage system, often rivers.

The [US EPA's National Pollutant Discharge Elimination System](https://www.epa.gov/npdes/combined-sewer-overflows-csos) (NPDES) provides regulations and procedures for permitting, controlling, and mitigating the effects of CSOs.  While NPDES mandates the elimination of CSO discharges during dry weather as a "minimum control," dry weather discharges nonetheless can happen if the CSS is not functioning properly.

The [MA DEP website](https://www.mass.gov/guides/sanitary-sewer-systems-combined-sewer-overflows) includes a [listing of all CSO permittes](https://www.mass.gov/files/documents/2016/08/vw/csopermittees.pdf) (mostly municipalities and the Massachusetts Water Resources Authority) in the state.

While there are many ways to define the Environmental Justice movement, part of the [Commonwealth's policy on EJ](https://www.mass.gov/service-details/objectives-of-environmental-justice) is to recognize that all people should have equal right to live in and enjoy and clean and healthful environment and have equal protection under and meaningful involvement in establishing environmental policies.  The movement has a [rich history](https://www.epa.gov/environmentaljustice/environmental-justice-timeline) of leadership by people of color dating back to the American Civil Rights movement of the 1960's and the action organized by Dr. Martin Luther King around sanitation workers in Memphis.  

Many governments and organizations view EJ as a critical policy issue due to the recognition that there has not historically been equity in this area; that vulnerable populations have historically borne a disproportionate share of environmental pollution.  Massachusetts has [specific quantitative definitions](http://www.mass.gov/eea/agencies/massdep/service/justice/) of what it means to be an EJ community based on population thresholds related to income, race, and language use.

## Locations of CSO discharges

The map below shows the location of CSO outfalls in MA (points), with overlays showing the sum total of CSO discharge volume in 2011 by watershed, municipality, and Census block group (use the control at right to toggle these layers).  Watershed names are labeled in blue.

{% raw %}
<iframe frameborder="no" border="0" marginwidth="0" marginheight="0" width="700" height="400" src="../../../assets/maps/NECIR_CSO_map_total.html"></iframe>
<p><em><a target="_blank" href="../../../assets/maps/NECIR_CSO_map_total.html">Click here to view map in a separate page</a></em></p>
{% endraw %}

You can click on each CSO outfall point to report information about its location, discharge frequency, and volume.

Additional mapping tools are available at [MassGIS](http://maps.massgis.state.ma.us/map_ol/ej.php) and [EJSCREEN](https://www.epa.gov/ejscreen/what-ejscreen).


## Environmental Justice community characteristics

The following maps visualize major EJ population characteristics by similar watershed, municipality, and Census block group levels as the previous map.  Refer to the [EJSCREEN data page]({{ site.url }}{{ site.baseurl }}/data/EPA_EJSCREEN.html) and links therein for more information about the definition of each demographic metric.  The watershed and municipal-level characteristics are calculated based on a population-weighted average over the Census block group-level data.

### Minority Racial Demographics

{% raw %}
<iframe frameborder="no" border="0" marginwidth="0" marginheight="0" width="700" height="400" src="../../../assets/maps/NECIR_CSO_map_EJ_MINORPCT.html"></iframe>
<p><em><a target="_blank" href="../../../assets/maps/NECIR_CSO_map_EJ_MINORPCT.html">Click here to view map in a separate page</a></em></p>
{% endraw %}



### Linguistic Isolation

{% raw %}
<iframe frameborder="no" border="0" marginwidth="0" marginheight="0" width="700" height="400" src="../../../assets/maps/NECIR_CSO_map_EJ_LINGISOPCT.html"></iframe>
<p><em><a target="_blank" href="../../../assets/maps/NECIR_CSO_map_EJ_LINGISOPCT.html">Click here to view map in a separate page</a></em></p>
{% endraw %}



### Low Income Status

{% raw %}
<iframe frameborder="no" border="0" marginwidth="0" marginheight="0" width="700" height="400" src="../../../assets/maps/NECIR_CSO_map_EJ_LOWINCPCT.html"></iframe>
<p><em><a target="_blank" href="../../../assets/maps/NECIR_CSO_map_EJ_LOWINCPCT.html">Click here to view map in a separate page</a></em></p>
{% endraw %}



## Aggregate level EJ population statistics

We aggregate the Census block group level EJSCREEN data to the watershed and municipality level to understand how these geographic areas vary in their EJ populations.  

## By watershed

{% include /charts/EJSCREEN_demographics_watershed.html %}


## By municipality

{% include /charts/EJSCREEN_demographics_municipality.html %}




## Correlation between CSO discharge and EJ factors

We explore the relationship between CSO discharge volumes within different geographic areas and their EJ population characteristics.


### Relationship with linguistic isolation

The plot below uses [bootstrap resampling](https://en.wikipedia.org/wiki/Bootstrap_(statistics)) to estimate the average volume of CSO discharge as a function of linguistic isolation, and the uncertainty in this value given the less-than-infinite number of observed discharges we have to estimate that (the 90% confidence interval).  Linguistic isolation is defined as the fraction of households with no adult who is a "very good" or better English speaker.  

{% include /charts/NECIR_EJSCREEN_correlation_bywatershed_LINGISO.html %}

While the total number of watersheds within MA to measure this relationship is small, the results suggest a statistically significant and strong relationship between CSO discharge volumes and linguistic isolation.  More linguistically isolated communities, like the Mystic River watershed, have much higher CSO discharge volumes on average.  On average, watersheds that have twice the level of linguistic isolation tend to have three times the level of CSO discharge.


