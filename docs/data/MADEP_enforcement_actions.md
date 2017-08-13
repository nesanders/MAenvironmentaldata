---
title: Massachusetts Department of Environmental Protection enforcement action data
author: NES
layout: data_listing
ancillary: 0
---

## Data source

MA Department of Environmental Protection enforcement actions are reported on the [MA DEP website](http://www.mass.gov/eea/agencies/massdep/service/enforcement/enforcement-actions-2017.html).  We infer the value of penalties associated with each enforcement by automated searching of the description string; this results in some errors when e.g. the penalty is extended across multiple years ("fees of $1000 for each of these three years").

These enforcement actions have been archived on this site, last updated on **{{ site.data.ts_update_MADEP_enforcement_actions.updated | date: "%-d %B %Y %I:%M %P" }}**.

## Download archive

In addition to including it in the integrated {{ site.data.site_config.site_abbrev }} Database, we provide our archive of this data in [CSV format](MADEP_enforcement_actions.csv).

## Data visualization

*Right click and save image to export the figure.*

{% include /charts/MADEP_enforcement_overall.html %}

{% include /charts/MADEP_enforcement_fines_overall.html %}


## Data table

For brevity,  a random sample of 10 rows from the enforcement table is shown below for illustration as to the table's form and content.

<!-- Note: need to have the for loop markup on the same line as the table rows as described here: http://stackoverflow.com/questions/35642820/jekyll-how-to-use-for-loop-to-generate-table-row-within-the-same-table-inside-m -->

| Year | Date | Description | Penalty amount | Municipalities | 
| --- | --- | --- | --- |{% for row in site.data.MADEP_enforcement_actions_sample %}
| {{ row.Year }} | {{ row.Date }} | {{ row.Text }} | {{ row.Fine }} | {{ row.municipality }} |{% endfor %}
{: .sortable}

