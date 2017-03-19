---
title: Massachusetts Department of Environmental Protection budget data
author: NES
layout: data_listing
ancillary: 0
---

## Data source

Massachussets environmental-related budget line item, including MA Department of Environmental Protection administration, records dating back to 2001 are availabe on the [MassBudget website](http://massbudget.org/browser/subcat.php?id=Environment&inflation=cpi#line_items).  

These records have been archived on this site, last updated on **{{ site.data.ts_update_MassBudget_environmental.updated | date: "%-d %B %Y" }}**.

## Download archive

We provide our archive of three tables from this source:
	
* [DEP global budget summary (CSV format)](MassBudget_environmental_summary.csv).
* [DEP line-item level budget (inflation adjusted; CSV format)](MassBudget_environmental_infadjusted.csv).
* [DEP line-item level budget (not inflation adjusted; CSV format)](MassBudget_environmental_noinfadjusted.csv).

## Data visualization

*Click on legend titles to add or remove series from the plot.*

{% include charts/MADEP_budget_summary.html %}

## Data table

*Click on the table headers to re-sort by that field.*


<!-- Note: need to have the for loop markup on the same line as the table rows as described here: http://stackoverflow.com/questions/35642820/jekyll-how-to-use-for-loop-to-generate-table-row-within-the-same-table-inside-m -->

| Fiscal Year | Total Environmental Budget (inflation adjusted) | Total Environmental Budget (not inflation adjusted) | DEP Administrative Budget (inflation adjusted) | DEP Administrative (not inflation adjusted) |
| --- | --- | --- |{% for row in site.data.MassBudget_environmental_summary %}
| {{ row.FiscalYear }} | {{ row.TotalBudget_inf }} | {{ row.TotalBudget_noinf }} | {{ row.DEPAdministration_inf }} | {{ row.DEPAdministration_noinf }} |{% endfor %}
{: .sortable}
