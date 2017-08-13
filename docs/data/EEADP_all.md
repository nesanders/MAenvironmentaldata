---
title: MA Energy and Environmental Affairs Data Portal Assets
author: NES
layout: data_listing
ancillary: 0
---

## Data source

In August of 2017, the [MA Executive Office of Energy and Environmental Affairs](http://www.mass.gov/eea/) (EEA) [began operating](http://www.mass.gov/eea/pr-2017/eea-launches-online-data-and-public-access-system.html) an "Enterprise Data Portal" for certain state regulatory data.  Initially, this has included permit, facilities, inspections, and enforcement, and drinking water testing data; more data assets are promised "regularly." 

Definitions, FAQs, disclaimers, and other information related to these datasets is available in PDF format at the [EEA Data Portal website's help page](http://eeaonline.eea.state.ma.us/Portal/#!/help) and archived here:
	
* [FAQs](../assets/PDFs/EEADP_FAQ.pdf)
* [Terms and definitions](../assets/PDFs/EEADP_Definitions.pdf)

One of these datasets,

The data from this portal has been archived on this site, last updated on **{{ site.data.ts_update_EEADP.updated | date: "%-d %B %Y %I:%M %P" }}**.

## Download archive

In addition to including them in them in the integrated {{ site.data.site_config.site_abbrev }} Database, we provide our archives of each of these data assets in CSV format:

* [Annualized drinking water quality measurement counts](EEADP_drinkingWater_annual.csv)

EEADP_drinkingWater_head.csv
EEADP_enforcement.csv
EEADP_facility.csv
EEADP_inspection.csv
EEADP_permit.csv


## Data table

*Click on the table headers to re-sort by that field.*

<!-- Note: need to have the for loop markup on the same line as the table rows as described here: http://stackoverflow.com/questions/35642820/jekyll-how-to-use-for-loop-to-generate-table-row-within-the-same-table-inside-m -->

| State | 2000 | 2001 |2002 | 2003 | 2004 | 2005 | 2006 | 2007 | 2008 | 2009 | 2010 | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 |
| --- | --- | --- |{% for row in site.data.Census_statepop %}
| {{ row.State }} | {{ row.2000 }} | {{ row.2001 }} | {{ row.2002}} | {{ row.2003}} | {{ row.2004}} | {{ row.2005}} | {{ row.2006}} | {{ row.2007}} | {{ row.2008}} | {{ row.2009}} | {{ row.2010}} | {{ row.2011}} | {{ row.2012}} | {{ row.2013}} | {{ row.2014}} | {{ row.2015}} | {{ row.2016}} |{% endfor %}
{: .sortable}

