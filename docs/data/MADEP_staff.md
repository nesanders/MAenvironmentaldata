---
title: Massachusetts Department of Environmental Protection staffing data
author: NES
layout: data_listing
---

## Data source

MA Department of Environmental Protection staff records dating back to 2004 are availabe on the [VisibleGovernment](https://qvs.visiblegovernment.us/QvAJAXZfc/notoolbar.htm?document=Clients/Massachusetts/Payroll/MA_Payroll.qvw).  

These enforcements actions have been archived on this site, last updated on **{{ site.data.ts_update_MADEP_enforcement_actions.updated | date: "%-d %B %Y" }}**.

## Download our archive of this data in [CSV format](MADEP_staff.csv).

<!-- Note: need to have the for loop markup on the same line as the table rows as described here: http://stackoverflow.com/questions/35642820/jekyll-how-to-use-for-loop-to-generate-table-row-within-the-same-table-inside-m -->

| Calendar Year | Employee Name | Job Title | Earnings ($) | Seniority (yrs since 2004)|
| --- | --- | --- |{% for row in site.data.MADEP_staff %}
| {{ row.CalendarYear }} | {{ row.EmployeeName }} | {{ row.JobTitle }} | {{ row.Earnings }} | {{ row.Seniority }} |{% endfor %}

