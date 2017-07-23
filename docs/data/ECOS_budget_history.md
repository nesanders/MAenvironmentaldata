---
title: The Environmental Council of States state environmental budget data
author: NES
layout: data_listing
ancillary: 0
---

## Data source

[The Environmental Council of States ](https://www.ecos.org) periodically publishes reports that collect total budgets, contributions from the three major sources (state general funds, fees, and the federal government) and other information about state environmental agencies.  These reports are based on surveys of state governments, and are generally limited to include information from states that respond to those surveys.  The specific data collection practices associated with each state annual budget are documented in the reports themselves, available here:

* [2009-2011 ECOS report (published August 2010)](../assets/ECOS_reports/ECOS_state env budget, green report, 2009-2011.pdf)
* [2011-2013 ECOS report (published September 2012)](../assets/ECOS_reports/September-2012-Green-Report.pdf)
* [2015-2017 ECOS report (published March 2017)](../assets/ECOS_reports/Budget-Report-FINAL-3_15_17-Final-4.pdf)

The years 2011 and 2013 are included in two of the above reports.  In some cases, different figures are reported for the same state in these years between the two overlapping reports, presumably reflecting changes between the enacted budget and actual expenditures.  In our analyses, we use the data from the later report, and also provide the earlier data in our archive labeled as "2011_old" and "2013_old".

We adopt the Environmental Agency Budget with the state revolving fund component included, as reported by ECOS, as the key budget figure.

Each ECOS report includes detailed information about how the data was collected and caveats associated with the interpretation of the figures.  In particular, the 2017 - 2017 ECOS report explains: "ECOS cautions comparing overall state EAB totals in this report to previous ECOS state EAB report totals. ECOS recognizes that clean water and drinking water SRF infrastructure funding is an important and significant source of federal funding that supports protection of human health and environment at the state and local level. This report only includes clean water and drinking water SRF from a state’s overall EAB calculations if a state agency reported a portion or all of these funds were a part of their overall budget. In past ECOS budget reports, clean water and drinking water SRF were added to state agency EAB based on EPA appropriation data for states that excluded these funds from their budget calculation."  We do not adjust for this

Note also that the values in this table are not adjusted for monetary inflation.  We do adjust for inflation in some analyses derived from this data.

The data from these reports have been archived on this site, last updated on **{{ site.data.ts_update_ECOS_budget_history.updated | date: "%-d %B %Y %I:%M %P" }}**.

See [https://ballotpedia.org/Environmental_spending_in_the_50_states](Ballotpedia) for an alternate accounting of state environmental budget figures.

## Download archive

We provide our archive of this data in [CSV format](ECOS_budget_history.csv).

## Data visualization

*Right click and save image to export the figure.*

The fiscal data in these visualizations has been corrected for inflation to 2016 dollars using the [SSA wage data](SSA_wages.html).

### State agency budgets comparison by year:

{% include /charts/ECOS_budget_peryear_bystate.html %}

### State agency budget per capita comparison by year:

{% include /charts/ECOS_budget_percap_peryear_bystate.html %}


## Data table

*Click on the table headers to re-sort by that field.*


<!-- Note: need to have the for loop markup on the same line as the table rows as described here: http://stackoverflow.com/questions/35642820/jekyll-how-to-use-for-loop-to-generate-table-row-within-the-same-table-inside-m -->


| State | Year | Budget Detail | Value | 
| --- | --- | --- | --- |{% for row in site.data.ECOS_budget_history %}
| {{ row.State }} | {{ row.Year }} | {{ row.BudgetDetail }} | {{ row.value }} |{% endfor %}
{: .sortable}

