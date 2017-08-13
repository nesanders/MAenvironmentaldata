---
title: Massachusetts Department of Environmental Protection staffing data
author: NES
layout: data_listing
ancillary: 0
---

## Data source

MA Department of Environmental Protection staff records dating back to 2004 are available on the [VisibleGovernment](https://qvs.visiblegovernment.us/QvAJAXZfc/notoolbar.htm?document=Clients/Massachusetts/Payroll/MA_Payroll.qvw).  These records have been archived on this site, last updated on **{{ site.data.ts_update_MADEP_staff.updated | date: "%-d %B %Y" }}**.

Additionally, the [MA office of the Comptroller of the Commonwealth](https://cthru.data.socrata.com/Government/Comptroller-of-the-Commonwealth-Payroll/rr3a-7twk) provides staffing data for each department.  This data is more detailed than the VisibleGovernment records, but extends only as far back as 2010.  These records have been archived on this site, last updated on **{{ site.data.ts_update_MADEP_staff_SODA.updated | date: "%-d %B %Y" }}**.

## Download archive

In addition to including this data in the integrated {{ site.data.site_config.site_abbrev }} Database, we provide them in CSV format below.

* VisibleGovernment data in [CSV format](MADEP_staff.csv)
* Comptroller's data in [CSV format](MADEP_staff_SODA.csv)

## Data table: VisibleGovernment

For brevity,  a random sample of 10 rows from the enforcement table is shown below for illustration as to the table's form and content.

<!-- Note: need to have the for loop markup on the same line as the table rows as described here: http://stackoverflow.com/questions/35642820/jekyll-how-to-use-for-loop-to-generate-table-row-within-the-same-table-inside-m -->

| Calendar Year | Employee Name | Job Title | Earnings ($) | Seniority (yrs since 2004)|
| --- | --- | --- |{% for row in site.data.MADEP_staff_sample %}
| {{ row.CalendarYear }} | {{ row.EmployeeName }} | {{ row.JobTitle }} | {{ row.Earnings }} | {{ row.Seniority }} |{% endfor %}
{: .sortable}
