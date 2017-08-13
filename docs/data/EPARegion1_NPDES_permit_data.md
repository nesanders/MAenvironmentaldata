---
title: EPA Region 1 NPDES permit documets
author: NES
layout: data_listing
ancillary: 0
---

## Data source

The federal Evironmental Protection Agency (EPA) Region 1 (New England) stores permits issued under the National Pollutant Discharge Elimination System (NPDES) program on their website in draft and final form, for each state.  These can be found on their website here:

### Final permits

* [CT final permits](https://www3.epa.gov/region1/npdes/permits_listing_ct.html)
* [MA final permits](https://www3.epa.gov/region1/npdes/permits_listing_ma.html)
* [ME final permits](https://www3.epa.gov/region1/npdes/permits_listing_me.html)
* [NH final permits](https://www3.epa.gov/region1/npdes/permits_listing_nh.html)
* [RI final permits](https://www3.epa.gov/region1/npdes/permits_listing_ri.html)
* [VT final permits](https://www3.epa.gov/region1/npdes/permits_listing_vt.html)

### Draft permits

* [CT final permits](https://www3.epa.gov/region1/npdes/draft_permits_listing_ct.html)
* [MA final permits](https://www3.epa.gov/region1/npdes/draft_permits_listing_ma.html)
* [ME final permits](https://www3.epa.gov/region1/npdes/draft_permits_listing_me.html)
* [NH final permits](https://www3.epa.gov/region1/npdes/draft_permits_listing_nh.html)
* [RI final permits](https://www3.epa.gov/region1/npdes/draft_permits_listing_ri.html)
* [VT final permits](https://www3.epa.gov/region1/npdes/draft_permits_listing_vt.html)


These permits have been archived on this site, last updated on **{{ site.data.ts_update_EPARegion1_NPDES_permit.updated | date: "%-d %B %Y %I:%M %P" }}**.

## Download archive

In addition to including it in the integrated {{ site.data.site_config.site_abbrev }} Database, we provide our archive of this data in [CSV format](EPARegion1_NPDES_permit_data.csv).

## Data table

*Click on the table headers to re-sort by that field.*


<!-- Note: need to have the for loop markup on the same line as the table rows as described here: http://stackoverflow.com/questions/35642820/jekyll-how-to-use-for-loop-to-generate-table-row-within-the-same-table-inside-m -->

| State | Stage | Watershed | Facility name | Date of Issuance | PDF link |
| --- | --- | --- | --- | --- | --- |{% for row in site.data.EPARegion1_NPDES_permit_data %}
| {{ row.State | upcase }} | {{ row.Stage }} | {{ row.Watershed }} | {{ row.Facility_name_clean }} | {{ row.Date_of_Issuance }} | {{ row.gs_path }} |{% endfor %}
{: .sortable}

