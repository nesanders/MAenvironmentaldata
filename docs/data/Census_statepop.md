---
title: US Census State Population Estimate data
author: NES
layout: data_listing
ancillary: 1
---

## Data source

The US Census Bureau publishes state-level resident population estimates for each decadal survey as well as intercensus estimates for intervening years.  According to the [detailed methodology published on the Census website](https://www2.census.gov/programs-surveys/popest/technical-documentation/methodology/2010-2016/2016-natstcopr-meth.pdf), the estimates are based on a demographic cohort method that accounts for births, deaths, and migration on top of the base population estimate from the decadal survey.  The Census Bureau has reported accuracies to about 3% at the county level.

In addition to the state-level data, the table includes estimates for the national population as well as geographic regions.

## Download archive

In addition to including it in the integrated {{ site.data.site_config.site_abbrev }} Database, we provide our archive of this data in [CSV format](Census_statepop.csv).

## Data table

*Click on the table headers to re-sort by that field.*

<!-- Note: need to have the for loop markup on the same line as the table rows as described here: http://stackoverflow.com/questions/35642820/jekyll-how-to-use-for-loop-to-generate-table-row-within-the-same-table-inside-m -->

| State | 2000 | 2001 |2002 | 2003 | 2004 | 2005 | 2006 | 2007 | 2008 | 2009 | 2010 | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 |
| --- | --- | --- |{% for row in site.data.Census_statepop %}
| {{ row.State }} | {{ row.2000 }} | {{ row.2001 }} | {{ row.2002}} | {{ row.2003}} | {{ row.2004}} | {{ row.2005}} | {{ row.2006}} | {{ row.2007}} | {{ row.2008}} | {{ row.2009}} | {{ row.2010}} | {{ row.2011}} | {{ row.2012}} | {{ row.2013}} | {{ row.2014}} | {{ row.2015}} | {{ row.2016}} |{% endfor %}
{: .sortable}

