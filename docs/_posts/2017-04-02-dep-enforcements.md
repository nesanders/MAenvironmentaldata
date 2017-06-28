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

## Fines

While it's difficult to fully quantify the total impact of enforcement actions, the penalty assessed is a useful indicator of impact.  

{% include /charts/MADEP_enforcement_fines_overall_stacked.html %}

## Enforcement types

{% include charts/MADEP_enforcement_bytopic.html %}

<!-- ** See "Data Enforcement Facts" slide -->

## Distribution of enforcement penalties

## Variation by town & demographics

## Discrepancy from FOIAed records

