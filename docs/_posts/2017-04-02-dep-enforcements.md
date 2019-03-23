---
layout: post
title: Changes in Enforcement by MA Department of Environmental Protection Over Time
ancillary: 0
---

While a coalition of local, state, and federal agencies are responsible for enforcing environmental regulations, the MA Department of Environmental Protection (DEP) has a pivotal role in environmental law enforcement in the Commonwealth. The analysis presented below draws from the [MA DEP enforcement data]({{ site.url }}{{ site.baseurl }}/data/MADEP_enforcement_actions.html) in the [{{ site.data.site_config.site_abbrev }} database]({{ site.url }}{{ site.baseurl }}/data/index.html), which has been collected by scraping the public reports listed on DEP's website.

Recently, DEP has also made separate data on their enforcement activities public via two other sources.  The [MA Executive Office of Energy and Environmental Affairs Data Portal](../data/EEADP_all.html) has published a listing of enforcement actions, and an annualized tally of enforcements was [provided to The Boston Globe](https://www.bostonglobe.com/metro/2017/03/08/amid-cuts-steep-drop-enforcement-environmental-rules/YYgddkmijr5PC4U7WBmS0H/story.html) in response to a Freedom of Information Act request.  The total number of enforcements per year identified by each of these sources conflict significantly.  This analysis focused on the published reports on the DEP website specified above.  This analysis also does not address enforcement actions taken by municipalities, the MA Attorney General, or US Environmental Protection Agency (EPA).

The reported enforcement actions used in this analysis are up to date as of **{{ site.data.ts_update_MADEP_enforcement_actions.updated | date: "%-d %B %Y %I:%M %P" }}**.

*[The code needed to reproduce this analysis using {{ site.data.site_config.site_abbrev }} data can be viewed and downloaded here](https://github.com/nesanders/MAenvironmentaldata/blob/master/analysis/MADEP_enforcements_viz.py)*

## Enforcement activity

The total number of individual enforcement actions reported by DEP over the past decade has not varied consistently.  It peaked in 2007 with nearly 500 enforcements.  In 2016, the total number of enforcements was less than half that.  The modern low was less than that, less than 200 in 2012.

{% include /charts/MADEP_enforcement_overall.html %}

In just the past few years, the decline has been more steady, falling about 15% annually since 2014.  This acute decline coincides with the dramatic rise in staff buyouts since 2015, as described in our [MA DEP staffing analysis]({{ site.url }}{{ site.baseurl }}/2017/03/15/dep-staff-changes.html).

The rise and fall in enforcement levels over time has tracked closely with the [changes in MA DEP budgets]({{ site.url }}{{ site.baseurl }}/2017/03/15/dep-staff-changes.html).  There is a {{ site.data.facts_DEPenforce.cor_enforcement_funding }}% correlation between the annual agency budget and the number of enforcement actions reported.  Recent history indicates that when more resources allocated to MA DEP, the agency is a more active enforcer of environmental law.

{% include /charts/MADEP_enforcement_vsbudget.html %}

**DEP's level of reported enforcement activity has declined in near lockstep with the agency's funding levels.**

## Enforcement types

{% include charts/MADEP_enforcement_bytopic.html %}

The chart above shows the variation of DEP enforcement levels on a variety of topics over time.  The topics were extracted from the textual descriptions of the reported enforcements by simple keyword matching.  We can draw several conclusions from this data.

The dominant enforcement mechanism for MA DEP is the consent order, a type of no-trial settlement, which is used in {{ site.data.facts_DEPenforce.yearly_avg_consentorder }}% of actions.

Only {{ site.data.facts_DEPenforce.yearly_2004_watersupply }}% of enforcement actions cited water supply issues in 2004.  This rate rose sharply over this period, to {{ site.data.facts_DEPenforce.yearly_2016_watersupply }}% in 2016, and has seemed to plateau near this heightened level since about 2013.  Water supply issues are now a significant fraction of all the agency's enforcement actions.

Averaging across this period, enforcement actions specifically reference [MA Chapter 91 law](http://www.mass.gov/eea/agencies/massdep/water/watersheds/chapter-91-the-massachusetts-public-waterfront-act.html), the Public Waterfront Act which guarantees public access and trust to coastal and inland waterways, only {{ site.data.facts_DEPenforce.yearly_ch91 }}% of the time.  The [National Pollutant Discharge Elimination System](https://www.epa.gov/npdes) (NPDES), the regulatory program for much of the Clean Water Act, is typically referenced in only {{ site.data.facts_DEPenforce.yearly_npdes }}% of actions.

Wetlands-related enforcement has declined from more than 16% at peak to only 8% in 2016, a decline of {{ site.data.facts_DEPenforce.yearly_avg_delta2016_wetlands }}%.

Enforcements that reference [supplemental environmental projects](https://www.epa.gov/enforcement/supplemental-environmental-projects-seps) (SEPs), an environmentally beneficial project taken on voluntarily by a violator as partial mitigation for a financial penalty, have declined markedly and steadily.  SEPs were referenced in 1 out of every 17 enforcements in 2004, versus 1 in every 50 enforcements in 2016.

Meanwhile, the use of unilateral orders has grown dramatically.  1 in 6 enforcements in 2016 involved a unilateral order, versus 1 in 67 in 2004.

**The focus and methods of DEP's reported enforcement efforts have shifted over time, leading to less emphasis on topics like wetlands and a growing reliance on unilateral orders, among other changes.**


## Fines

While it's difficult to fully quantify the total impact of enforcement actions, ~70% of consent orders have financial penalties associated with them.  (These are ACOPs, Administrative Consent Orders with Penalties.)  The penalty assessed is a useful indicator of impact.

However, the fraction of consent orders with penalties has declined over time, from more than 80% in 2005 to about 65% in 2016.  We use a statistical test to evaluate how significant those changes over time truly are.  The plot below uses [bootstrap resampling](https://en.wikipedia.org/wiki/Bootstrap_(statistics)) to estimate the fraction of consent orders that carry penalties per year, and the uncertainty in this value given the less-than-infinite number of consent orders we have to estimate that fraction (the 90% confidence interval).  The results indicate that the changes over time are highly significant, shifting on a scale much larger than the 90% confidence interval.

{% include /charts/MADEP_enforcement_ACOP_byyear.html %}

The plot below shows each individual consent order, so the stacked bars represent the total amount of fines issues per year.  (Depending on your browser, you may need to mouse over the bars to see the individual penalties.)

{% include /charts/MADEP_enforcement_fines_overall_stacked.html %}

We can further understand the impact of penalties on violators by looking at the distribution of fine amounts.  This plot shows that fines have been levied over a large range of amounts, from less than $1,000 to more than $20,000,000.  The plot below shows that the typical (mode) enforcement action is in the range of $10,000 - $30,000, with fines less than $800 or greater than $100,000 being rare.

{% include charts/MADEP_enforcement_fine_dist.html %}

The plot below uses [bootstrap resampling](https://en.wikipedia.org/wiki/Bootstrap_(statistics)) to estimate the median enforcement value per year (again, the 90% confidence interval is shown).  The analysis shows that the median enforcement amount has varied by about 20% over this period, but these shifts are not very significant - they could be explained by randomness in what violations happened to come up in those years rather than systematic policy shifts.

{% include charts/MADEP_enforcement_fine_avg_bootstrap.html %}

**The fraction of DEP consent orders carrying financial penalties has declined over time.  The distribution of penalty amounts, which are typically $10,000 to $30,000, has not changed significantly.**


## Variation by municipality & demographics

Below, we explore the municipality-by-municipality variation of historical enforcement.  The map below illustrates the total number of enforcements recorded in each town since the start of reporting in 2004.  Zoom in and click on an individual city or town to see the total count of enforcements and a listing of the enforcements that have carried the highest penalties.

{% raw %}
<iframe frameborder="no" border="0" marginwidth="0" marginheight="0" width="700" height="400" src="../../../assets/maps/MADEP_enforcements_town_total.html"></iframe>
<p><em><a target="_blank" href="../../../assets/maps/MADEP_enforcements_town_total.html">Click here to view map in a separate page</a></em></p>
{% endraw %}

While the strongest predictor of total enforcement actions by municipality is the population of the town or city, other factors also correlate with total enforcements.  The chart below illustrates a subtle correlation between the average per capita enforcement rate and the median income in the town, based on [2014 US Census American Community Survey data](../data/Census_ACS.html).  The trend shown below is based on a population-weighted average over all towns and cities, and the uncertainty contour is estimated via bootstrap resampling.  The trend is calculated based on equal-sized bins of municipalities.  You can click on the legend titles in the plot to overlay points representing each individual town and city, including towns above or below 25,000 residents in size.

While there is substantial variation across municipalities, the weighted-average trend illustrates a declining relationship from about 130 enforcements per 100,000 residents among municipalities with median income of about $30,000 per year to only about 40 enforcements per 100,000 residents among municipalities with the highest incomes (median much greater than $50,000 per year).

{% include charts/MADEP_enforcement_bytown_income.html %}

Note that the penalties inferred from the textual descriptions of the enforcement actions posted on the MA DEP website, used in this analysis, may refer to Administrative Consent Orders with Penalties from MA DEP, civil penalties assessed by the Attorney General, or indirect penalties such as the estimated costs of demanded compliance.

**The trend of increasing enforcement activity among towns with lower income levels may reflect the history of industrial activity, decaying infrastructure, and other burdens within low-income communities in Massachusetts.**


## Municipalities with highest level of historical enforcement.

Finally, we present tables of the cities and towns (with population  greater than 25,000) that have had the highest historical level of enforcement activity or penalties per capita.

### Cities and towns (population > 25,000) with highest per capita rate of reported enforcement actions

| Municipality | DEP enforcements | DEP penalties ($1,000) | Per capita income ($k) | Population | Enforcements per capita (per 100,000 residents) | Penalties per capita ($1M per 100,000 people) | 
| --- | --- | --- | --- |{% for row in site.data.table_MADEP_enforcement_topcities_enforcements %}
{% for col in row %} {{ col[1] }} | {% endfor %} {% endfor %}
{: .sortable}

### Cities and towns (population > 25,000) with highest per capita rate of reported enforcement penalties

| Municipality | DEP enforcements | DEP penalties ($1,000) | Per capita income ($k) | Population | Enforcements per capita (per 100,000 residents) | Penalties per capita ($1M per 100,000 people) | 
| --- | --- | --- | --- |{% for row in site.data.table_MADEP_enforcement_topcities_penalties %}
{% for col in row %} {{ col[1] }} | {% endfor %} {% endfor %}
{: .sortable}
