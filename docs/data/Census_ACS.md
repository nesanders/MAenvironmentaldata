---
title: US Census American Community Survey data
author: NES
layout: data_listing
ancillary: 1
---

## Data source

The US Census Bureau publishes results from its [American Community Survey (ACS)](https://www.census.gov/programs-surveys/acs/), based on a continuous nationwide survey that asks a variety of demographic, economic, and other questions of residents. We use the [Census API](https://www.google.com/search?q=census%20api) to retrieve data for selected questions from the 5-year survey estimates (which are less current than 1- and 3-year estimates, but more precise) for Massachusetts communities.  The data selected here is for calendar year 2014.

## Download archive

In addition to including it in the integrated {{ site.data.site_config.site_abbrev }} Database, we provide our archive of this data in [CSV format](Census_ACS_MA.csv).

## Data table

*Click on the table headers to re-sort by that field.*

<!-- Note: need to have the for loop markup on the same line as the table rows as described here: http://stackoverflow.com/questions/35642820/jekyll-how-to-use-for-loop-to-generate-table-row-within-the-same-table-inside-m -->

| County Subdivision | Population | Per Capita Income |
| --- | --- | --- |{% for row in site.data.Census_ACS_MA %}
| {{ row.Subdivision }} | {{ row.population_acs52014 }} | {{ row.per_capita_income_acs52014 }} |{% endfor %}
{: .sortable}

