---
title: EPA Massachusetts EJSCREEN data
author: NES
layout: data_listing
ancillary: 0
---

## Data source

The US Environmental Protection Agency (EPA) provides a tabulated environmental justice (EJ) dataset and mapping tool called [EJSCREEN](https://www.epa.gov/ejscreen/what-ejscreen).  The EJSCREEN dataset consists of information across a variety of environmental indicators like stream toxicity, demographic indicators like the percentage of residents reporting membership in a racial minority group, and EJ indexes like ozone pollution levels for each [US Census block group](https://www.census.gov/geo/reference/gtc/gtc_bg.html).  This data originates from the US Census, EPA, and other sources.

The US EPA provides extensive [documentation](https://www.epa.gov/sites/production/files/2017-09/documents/2017_ejscreen_technical_document.pdf) and a description of [limitations and caveats](https://www.epa.gov/ejscreen/limitations-and-caveats-using-ejscreen) for this data on their website.

The US EPA makes the tabulated EJSCREEN data available on an [FTP site](ftp://newftp.epa.gov/EJSCREEN/).  The 2017 version of these records have been filtered to MA Census block groups and archived on this site, last updated on **{{ site.data.ts_update_EPA_EJSCREEN_MA_2017.updated | date: "%-d %B %Y" }}**.

A [data dictionary for the EJSCREEN data](https://catalog.data.gov/harvest/object/77fc38d8-0d52-45e8-91ef-86bde657aae5/original) is avaiable at [data.gov](https://data.gov/).

## Download archive

In addition to including this data in the integrated {{ site.data.site_config.site_abbrev }} Database, we provide them in CSV format below.

* 2017 US EPA EJSCREEN data for MA [CSV format](EPA_EJSCREEN_MA_2017.csv)
* 2017 US EPA EJSCREEN technical documentation [PDF format](../assets/PDFs/EPA_EJSCREEN_2017_Documentation.pdf)

## Data table: 2017 MA EJSCREEN Data

For brevity, a random sample of 10 rows from the enforcement table is shown below for illustration as to the table's form and content.  Because there are more than 100 columns in this dataset, only a few are shown here for illustration.

<!-- Note: need to have the for loop markup on the same line as the table rows as described here: http://stackoverflow.com/questions/35642820/jekyll-how-to-use-for-loop-to-generate-table-row-within-the-same-table-inside-m -->

| Block Group ID | State | Ozone | Racial Minority Pct | Land Area|
| --- | --- | --- |{% for row in site.data.EPA_EJSCREEN_MA_2017_sample %}
| {{ row.ID }} | {{ row.ST_ABBREV }} | {{ row.OZONE }} | {{ row.MINORPCT }} | {{ row.AREALAND }} |{% endfor %}
{: .sortable}

