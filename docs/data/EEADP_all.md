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

One of these datasets, the historical drinking water quality measurement dataset, is significantly larger than the other (>200 MB in total).  Because this measurement-level drinking water quality reporting is not instrumental to the goals of {{ site.data.site_config.site_abbrev }}, we do not include it in our integrated database.  We do provide an archived version of the complete drinking water dataset below.

The data from this portal has been archived on this site, last updated on **{{ site.data.ts_update_EEADP.updated | date: "%-d %B %Y %I:%M %P" }}**.

## Download archive

In addition to including them in them in the integrated {{ site.data.site_config.site_abbrev }} Database, we provide our archives of each of these data assets in CSV format:

* [Enforcement](EEADP_enforcement.csv)
* [Facilities](EEADP_facility.csv)
* [Inspection](EEADP_inspection.csv)
* [Permits](EEADP_permit.csv)

* [Complete drinking water quality measurement (>200 MB, not included in database)](https://storage.googleapis.com/ns697-amend/EEADP_drinkingWater.csv)
* [Annualized drinking water quality measurement counts](EEADP_drinkingWater_annual.csv)

## Data tables

*Click on the table headers to re-sort by that field.*

### Enforcement

<!-- Note: need to have the for loop markup on the same line as the table rows as described here: http://stackoverflow.com/questions/35642820/jekyll-how-to-use-for-loop-to-generate-table-row-within-the-same-table-inside-m -->

| Enforcement Date | Enforcement Type | Facility Name | Penalty Assessed | Program | Town |
| --- | --- | --- |{% for row in site.data.EEADP_enforcement %}
| {{ row.EnforcementDate }} | {{ row.EnforcementType }} | {{ row.FacilityName }} | {{ row.PenaltyAssessed }} | {{ row.Program }} | {{ row.Town }} |{% endfor %}
{: .sortable}

