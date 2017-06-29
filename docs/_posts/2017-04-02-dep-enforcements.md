---
layout: post
title: Changes in Enforcement by MA Department of Environmental Protection Over Time
---

While a coalition of local, state, and federal agencies are responsible for enforcing environmental regulations, the MA Department of Environmental Protection (DEP) has a pivotal role in environmental law enforcement in the Commonwealth. The analysis presented below draws from the [MA DEP enforcement data]({{ site.url }}{{ site.baseurl }}/data/MADEP_enforcement_actions.html) in the [{{ site.data.site_config.site_abbrev }} database]({{ site.url }}{{ site.baseurl }}/data/index.html), which has been collected by scraping the public reports listed on DEP's website.

This analysis does not address enforcement actions taken by municipalities, the MA Attorney General, or US Environmental Protection Agency (EPA).

These enforcement actions are up to date as of **{{ site.data.ts_update_MADEP_enforcement_actions.updated | date: "%-d %B %Y %I:%M %P" }}**.

*[The code needed to reproduce this analysis using {{ site.data.site_config.site_abbrev }} data can be viewed and downloaded here](https://github.com/nesanders/MAenvironmentaldata/blob/master/analysis/MADEP_enforcements_viz.py)*

## Enforcement activity

The total number of individual enforcement actions reported by DEP over the past decade has not varied consistently.  It peaked in 2007 with nearly 500 enforcements.  In 2016, the total number of enforcements was less than half that.  The modern low was less than that, lower than 200 in 2012.

{% include /charts/MADEP_enforcement_overall.html %}

In just the past few years, the decline has been more steady, falling about 15% annually since 2014.  Only 61 enforcements were reported through the end of May, 2016.  This acute decline coincides with the dramatic rise in staff buyouts since 2015, as described in our [MA DEP staffing analysis]({{ site.url }}{{ site.baseurl }}/2017/03/15/dep-staff-changes.html).

The rise and fall in enforcement levels over time has tracked closely with the [changes in MA DEP budgets]({{ site.url }}{{ site.baseurl }}/2017/03/15/dep-staff-changes.html).  There is a {{ site.data.facts_DEPenforce.cor_enforcement_funding }}% correlation between the annual agency budget and the number of enforcement actions reported.  Recent history indicates that when more resources allocated to MA DEP, the agency is a more active enforcer of environmental law.

{% include /charts/MADEP_enforcement_vsbudget.html %}


## Enforcement types

{% include charts/MADEP_enforcement_bytopic.html %}

We can draw several conclusions from this data.

The dominant enforcement mechanism for MA DEP is the consent order, a type of no-trial settlement, which is used in {{ site.data.facts_DEPenforce.yearly_avg_consentorder }}% of actions.

Only {{ site.data.facts_DEPenforce.yearly_2004_watersupply }}% of enforcement actions cited water supply issues in 2004.  This rate rose sharply over this period, to {{ site.data.facts_DEPenforce.yearly_2016_watersupply }}% in 2016, and has seemed to plateau near this heightened level since about 2013.  Water supply issues are now a significant fraction of all the agency's enforcement actions.

Averaging across this period, enforcement actions specifically reference [MA Chapter 91 law](http://www.mass.gov/eea/agencies/massdep/water/watersheds/chapter-91-the-massachusetts-public-waterfront-act.html), the Public Waterfront Act which guarantees public access and trust to coastal and inland waterways, only {{ site.data.facts_DEPenforce.yearly_ch91 }}% of the time.  The [National Pollutant Discharge Elimination System](https://www.epa.gov/npdes) (NPDES), the regulatory program for much of the Clean Water Act, is typically referenced in only {{ site.data.facts_DEPenforce.yearly_npdes }}% of actions.

Wetlands-related enforcement has declined from more than 16% at peak to only 8% in 2016, a decline of {{ site.data.facts_DEPenforce.yearly_avg_delta2016_wetlands }}%.

## Fines

While it's difficult to fully quantify the total impact of enforcement actions, ~70% of consent orders have financial penalties associated with them.  (These are ACOPs, Administrative Consent Orders with Penalties.)  The penalty assessed is a useful indicator of impact.

However, the fraction of consent orders with penalties has been steadily declining over time, from more than 80% in 2005 to about 65% in 2016.

<!-- Number of enforcements carrying penalties -->


The plot below shows each individual consent order, so the stacked bars represent the total amount of fines issues per year.  (Depending on your browser, you may need to mouse over the bars to see the individual penalties.)

{% include /charts/MADEP_enforcement_fines_overall_stacked.html %}

We can further understand the impact of penalties on violators by looking at the distribution of fine amounts.  This plot shows that fines have been levied over a large range of amounts, from less than $1,000 to more than $20,000,000.  The plot below shows that the typical (mode) enforcement action is in the range of $10,000 - $30,000, with fines less than $800 or greater than $100,000 being rare.

{% include charts/MADEP_enforcement_fine_dist.html %}

We can use a statistical test to see if the typical fine amount has increased or decreased with time.  The plot below uses [bootstrap resampling](https://en.wikipedia.org/wiki/Bootstrap_(statistics)) to estimate the median enforcement value per year, and the uncertainty in this value given the less-than-infinite number of enforcements we have to estimate the median (90% confidence interval).  The analysis shows that the median enforcement amount has varied by about 20% over this period, but these shifts are not very significant - they could be explained by randomness in what violations happened to come up in those years rather than systematic policy shifts.

{% include charts/MADEP_enforcement_fine_avg_bootstrap.html %}



## Variation by town & demographics

## Discrepancy from FOIAed records

