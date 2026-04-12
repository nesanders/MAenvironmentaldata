---
title: EPA 303(d) Integrated List of MA Impaired Waters
author: NES
layout: data_listing
ancillary: 0
---

## Data source

[Section 303(d) of the Federal Clean Water Act](https://www.epa.gov/tmdl/overview-identifying-and-restoring-impaired-waters-under-section-303d-cwa)
requires states to identify waterbodies that fail to meet water quality standards even after
technology-based pollution controls are applied. Massachusetts submits a biennial
**Integrated List of Waters** to EPA on April 1 of even-numbered years, combining a full 305(b)
water quality assessment with the required 303(d) impaired waters listing. EPA typically reviews
and approves submissions within 6–18 months.

The Integrated List is the primary tool for tracking water quality outcomes in Massachusetts. It
forms the basis for **[TMDL (Total Maximum Daily Load)](https://www.epa.gov/tmdl)** development —
legally required cleanup plans that set the maximum amount of a pollutant a waterbody can receive
while still meeting standards. Every waterbody listed as impaired in Category 5 must have a TMDL
developed for it.

EPA maintains the national [ATTAINS (Assessment, Total Maximum Daily Load Tracking and
Implementation System)](https://www.epa.gov/waterdata/attains) database, which stores all state
303(d) submissions. MA's approved list cycles and EPA correspondence are documented on the
[EPA Region 1 Impaired Waters page](https://www.epa.gov/tmdl/region-1-impaired-waters-and-303d-lists-state).
Individual waterbody conditions can be explored via EPA's
[How's My Waterway](https://mywaterway.epa.gov/state/MA/water-quality-overview) tool.

**Assessment categories:**

| Category | Meaning |
|----------|---------|
| 1 | Fully Supporting all designated uses |
| 2 | Attaining standards (some minor concern) |
| 3 | Insufficient information to assess |
| 4A | Impaired — TMDL completed and approved |
| 4B | Impaired — addressed through other required plans |
| 4C | Impaired — addressed through alternative control requirement |
| 5 | Impaired — TMDL needed (the "303(d) list" proper) |

**Data available in {{ site.data.site_config.site_abbrev }}:** Reporting cycles 2010, 2012, 2014, 2016, 2018,
and 2022. The 2020 cycle was not published by MassGIS. The 2024/2026 cycle is in draft as of
April 2026 and will be added when EPA approves the MA submission.

This data is sourced from
[MassGIS (Massachusetts Bureau of Geographic Information)](https://www.mass.gov/info-details/massgis-data-massdep-2022-integrated-list-of-waters-305b303d),
which publishes each approved cycle as shapefiles with tabular attribute files.

The data from MassGIS has been archived on this site, last updated on
**{{ site.data.ts_update_ATTAINS_303d.updated | date: "%-d %B %Y %I:%M %P" }}**
(latest cycle: **{{ site.data.ts_update_ATTAINS_303d.latest_cycle }}**).
AMEND checks weekly and will automatically incorporate new data when MassGIS publishes a new cycle;
because data is only released biennially, no new data will appear between cycles.

## Download archive

* [303(d) impairments (all cycles)](EPA_303d_impairments.csv) — one row per assessment unit × designated use × impairment cause × cycle

## Data visualization

### Trend in impaired waters over time

{% include charts/EPA303d_impaired_trend.html %}

### Causes of impairment ({{ site.data.ts_update_ATTAINS_303d.latest_cycle }})

{% include charts/EPA303d_causes_breakdown.html %}

## Data table

A random sample of 10 rows from the full dataset is shown below for illustration.

| Cycle | Waterbody | Watershed | Water Type | Use | Attainment | Cause | Category |
| --- | --- | --- | --- | --- | --- | --- | --- |{% for row in site.data.EPA_303d_impairments_sample %}
| {{ row.reportingCycle }} | {{ row.waterbody }} | {{ row.watershed }} | {{ row.waterType }} | {{ row.designatedUse }} | {{ row.attainment }} | {{ row.cause }} | {{ row.category }} |{% endfor %}
{: .sortable}
