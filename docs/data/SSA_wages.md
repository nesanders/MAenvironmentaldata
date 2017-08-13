---
title: Social Security Administration wage data
author: NES
layout: data_listing
ancillary: 1
---

## Data source

The Social Security Administration publishes an [Average Wage Index (AWI)](https://www.ssa.gov/OACT/COLA/central.html), based on nationwide averages of net compensation, which we use to correct salary data for inflation.  When data is not yet available for recent years, we assume no inflation (AWI same as previous year).
 

## Download archive

In addition to including it in the integrated {{ site.data.site_config.site_abbrev }} Database, we provide our archive of this data in [CSV format](SSAWages_2016-12-09.csv).

## Data visualization

*Click on legend titles to add or remove series from the plot.  Right click and save image to export the figure.*

{% include charts/SSAwages.html %}

## Data table

*Click on the table headers to re-sort by that field.*

<!-- Note: need to have the for loop markup on the same line as the table rows as described here: http://stackoverflow.com/questions/35642820/jekyll-how-to-use-for-loop-to-generate-table-row-within-the-same-table-inside-m -->

| Year | AWI | % increase |
| --- | --- | --- |{% for row in site.data.SSAWages_2016-12-09 %}
| {{ row.Year }} | {{ row.AWI }} | {{ row.Increase }} |{% endfor %}
{: .sortable}

