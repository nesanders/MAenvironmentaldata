---
title: Massachusetts Department of Environmental Protection enforcement action data
author: NES
layout: data_listing
ancillary: 0
---

## Data source

MA Department of Environmental Protection enforcement actions are reported on the [MA DEP website](http://www.mass.gov/eea/agencies/massdep/service/enforcement/enforcement-actions-2017.html).  

These enforcements actions have been archived on this site, last updated on **{{ site.data.ts_update_MADEP_enforcement_actions.updated | date: "%-d %B %Y %I:%M %P" }}**.

## Download our archive of this data in [CSV format](MADEP_enforcement_actions.csv).

<!-- Note: need to have the for loop markup on the same line as the table rows as described here: http://stackoverflow.com/questions/35642820/jekyll-how-to-use-for-loop-to-generate-table-row-within-the-same-table-inside-m -->

| Year | Date | Description |
| --- | --- | --- |{% for row in site.data.MADEP_enforcement_actions %}
| {{ row.Year }} | {{ row.Date }} | {{ row.Text }} |{% endfor %}

