---
layout: post
title: Staff Changes at the MADEP Over Time
---

A key element of the evolution of the role and effectiveness of environmental regulation in Massachusetts is the staffing of our most prominent environmental agency, the Department of Environmental Protection (DEP). The analysis presented below draws from the [MA DEP staffing]({{ site.url }}{{ site.baseurl }}/data/MADEP_staff.html) and [budget data]({{ site.url }}{{ site.baseurl }}/data/MassBudget_environmental.html) in the [{{ site.data.site_config.site_abbrev }} database]({{ site.url }}{{ site.baseurl }}/data/index.html).

*[The code needed to reproduce this analysis using {{ site.data.site_config.site_abbrev }} data can be viewed and downloaded here](https://github.com/nesanders/MAenvironmentaldata/blob/master/analysis/MADEP_staff.py)*

<!-- ![]({{ site.url }}{{ site.baseurl }}/assets/figures/MADEP_staff_earnings_by_role.png) -->

## Overall staffing levels

As of the end of 2016, overall DEP staffing levels have been reduced by about 20% overall from 2009 levels.  Starting in 2010, we can use the [Comptroller's staffing records]({{ site.url }}{{ site.baseurl }}/data/MADEP_staff.html) to further break down these positions by full time versus part time and contractor roles.  Full time staff have grown somewhat as a fraction of overall DEP employment since 2010.

{% include charts/MADEP_staffing_overall.html %}

Note that the overall DEP staffing level is of course directly related to [overall DEP administration funding levels]({{ site.url }}{{ site.baseurl }}/data/MassBudget_environmental.html).  We find these two quantities are correlated at a level of {{ site.data.facts_DEPstaff.cor_staff_funding }}%.

{% include charts/MADEP_staffing_overall_funding.html %}

## Employees by role

We can better understand the staffing picture at DEP by breaking the staff down by role types within the agency, focusing on the critical roles of environmental analyst, engineer, regional planners, and program coordinator.  Indexing these numbers to 2004 levels, we see relatively constant employment (and some growth) for analysts, while the most technical staff, engineers, have steadily declined by a cumulative total of more than 20%. The planning staff stands at only about half what it was in 2004.  The ranks of program coordinators rose about 10% from 2014-2016, though this rise corresponds to a sharp decrease in experience level for this role (shown below).

{% include charts/MADEP_staffing_rolevolume.html %}

We calculate "seniority" as the number of years each employee has accumulated at the agency, from the start of our data in 2004.  The seniority "gain" is then the number of years per employee added of subtracted by hiring or firing, i.e. discounting the direct passage of time.  The gain would be 0 if the same staff were employed indefinitely.  By this measure, we see that seniority at the agency has declined persistently since 2004.  The decline accelerated for analysts, engineers, and coordinators after 2014.

{% include charts/MADEP_staffing_seniority.html %}

Perhaps the strongest indicator of seniority and experience in the agency is the average salary level for staff in each role type. After adjusting for wage inflation, this measure largely mirrors position level.  Particularly for the key positions of environmental analyst, engineer, regional planners, and program coordinator, the charge below shows a steady increase in average earnings from about 2007-2013, but an accelerating decline in seniority since then.  

{% include charts/MADEP_staffing_wagehistory.html %}

## Buyouts

Part of the story of the shifting seniority levels is explained by the buyout program at DEP over time.  As illustrated below, there was a particularly large buyout program executed in 2015, which led to about six times more retirees due to buyout than in a typical year, 140 employees in total at a cost of about $1.2 million.  2016 levels were similar.

{% include charts/MADEP_staffing_buyout.html %}

[MassLive wrote about the buyout packages](http://www.masslive.com/politics/index.ssf/2015/03/agencies_overseeing_revenue_we.html) and their possible effects when they were introduced by the Baker administration in early 2015.  The article quotes a DEP employee:

> David, a Department of Environmental Protection employee who asked only to be identified by first name, said he worries that new staff will not be hired in time to be trained by existing staff. "The institutional knowledge of how to enforce the regulations that we're supposed to enforce, and the history of what led to our current policies, a lot of that's going to be lost," he said.
