---
title: New England Center for Investigative Reporting 2011 MA Combined Sewer Overflow data
author: NES
layout: data_listing
ancillary: 0
---

## Data source

In 2013, the [New England Center for Investigative Reporting](https://www.necir.org/) (NECIR) published an [examination of sewage overflows into New England waterways](https://www.necir.org/2013/04/20/raw-sewage-continues-to-contaminate-waterways-in-new-england/).  To support this work, NECIR undertook a region-wide census of [combined sewer overflow (CSO) discharges](https://www.mass.gov/guides/sanitary-sewer-systems-combined-sewer-overflows) in the year 2011 by contacting individual state authorities.  In MA, NECIR cited the MA Department of Environmental Protection and MA Water Resources Authority as their sources.

Because there is as yet no systematic monitoring or reporting system for these discharges, and because this census work has not been repeated and published since this effort, this is the most recent year for which statewide data is available.  The dataset includes a "note" column specifying the source of each reported discharge.  Also note that many of the CSO outfall locations are approximate, as noted in the file.

The NECIR 2011 dataset was published as a [Google Fusion Table](https://fusiontables.google.com/DataSource?docid=1k_SFSELhFDQlM2mZCGl6H0a4Lx9qHzA2uBhKNgE#rows:id=1).  These records have been archived on this site, last updated on **{{ site.data.ts_update_NECIR_CSO.updated | date: "%-d %B %Y" }}**.

## Download archive

In addition to including this data in the integrated {{ site.data.site_config.site_abbrev }} Database, we provide them in CSV format below.

* 2011 MA CSO discharge data [CSV format](NECIR_CSO_2011.csv)

## Data table: 2011 MA CSO discharges

<!-- Note: need to have the for loop markup on the same line as the table rows as described here: http://stackoverflow.com/questions/35642820/jekyll-how-to-use-for-loop-to-generate-table-row-within-the-same-table-inside-m -->

| Nearest Pipe Address | Municipality | Discharge Body | 2011 Discharges in Millions of Gallons | 2011 Discharge Count | Location | Notes|
| --- | --- | --- |{% for row in site.data.NECIR_CSO_2011 %}
| {{ row.Nearest_Pipe_Address }} | {{ row.Municipality }} | {{ row.DischargesBody }} | {{ row.2011_Discharges_MGal }} | {{ row.2011_Discharge_N }} | {{ row.Location }} | {{ row.Notes }}|{% endfor %}
{: .sortable}

