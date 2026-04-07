---
title: Massachusetts Department of Environmental Protection budget data
author: NES
layout: data_listing
ancillary: 0
---

## Data source

**Primary source (FY2005–present):** [MA Comptroller CTHRU Socrata API](https://cthru.data.socrata.com/Government/Comptroller-of-the-Commonwealth-Fiscal-Year-App/kv7m-35wn) — the official state transparency portal for appropriations data. Provides the following environmental agency administration accounts:

| Agency | Account | Line Item |
|--------|---------|-----------|
| DEP (Department of Environmental Protection) | 22000100 | ENVIRONMENTAL COMPLIANCE |
| DCR (Department of Conservation & Recreation) | 28000100, 28100100 | ADMINISTRATION |
| EEA (Executive Office of Energy & Environmental Affairs) | 20011001, 20000100 | SECRETARIAT |
| Fish & Game | 23000100 | OFFICE OF FISHERIES & WILDLIFE |

**Historical data (FY2001–FY2004):** Archived from [MassBudget](http://massbudget.org/) (which became inaccessible in 2026). These rows do not auto-update.

**Last updated:** {{ site.data.ts_update_MassBudget_environmental.updated | date: "%-d %B %Y" }}

**Inflation adjustment:** All figures in the "inflation-adjusted" columns are expressed in fiscal-year dollars adjusted to FY2024 using the SSA Average Wage Index (AWI). The base year changed from 2016 to 2024 in April 2026.

## Download archive

In addition to including it in the integrated {{ site.data.site_config.site_abbrev }} Database, we provide the master budget summary:
	
* [Environmental agency budget summary (CSV format)](MassBudget_environmental_summary.csv) — contains FY2001–2026 data for DEP, DCR, EEA Secretariat, and Fish & Game administrations, both nominal and inflation-adjusted to FY2024 dollars. Total budget row includes sum of all four agencies (FY2005–2026 only).

## Data visualization

*Click on legend titles to add or remove series from the plot.  Right click and save image to export the figure.*

{% include charts/MADEP_budget_summary.html %}

## Data table

*Click on the table headers to re-sort by that field.*

The CSV file contains the following columns for each fiscal year:
- `DEPAdministration_noinf_float`, `DEPAdministration_inf_float` — DEP Administration (nominal and FY2024-adjusted)
- `DCRAdministration_noinf_float`, `DCRAdministration_inf_float` — DCR Administration
- `EEAAdministration_noinf_float`, `EEAAdministration_inf_float` — EEA Secretariat
- `FishGameAdministration_noinf_float`, `FishGameAdministration_inf_float` — Fish & Game
- `TotalBudget_noinf_float`, `TotalBudget_inf_float` — Sum of all four agencies (FY2005–2026 only)

### Summary table

| Fiscal Year | Total Environmental Budget (inflation adjusted) | Total Environmental Budget (not inflation adjusted) | DEP Administrative Budget (inflation adjusted) | DEP Administrative (not inflation adjusted) |
| --- | --- | --- |{% for row in site.data.MassBudget_environmental_summary %}
| {{ row.FiscalYear }} | {{ row.TotalBudget_inf }} | {{ row.TotalBudget_noinf }} | {{ row.DEPAdministration_inf }} | {{ row.DEPAdministration_noinf }} |{% endfor %}
{: .sortable}

### Line-item level tables (historical — not updated)

⚠️ The tables below show budget line items from the original MassBudget source through FY2018. These are **not updated** as of 2026 — the CTHRU API only provides summary-level budget data, not line-item details. These tables are retained for historical reference only.

### Line-item level table (inflation adjusted)

| Line Item | Name | FY01 | FY02 | FY03 | FY04 | FY05 | FY06 | FY07 | FY08 | FY09 | FY10 | FY11 | FY12 | FY13 | FY14 | FY15 | FY16 | FY17 | FY18_Gov |
| --- | --- | --- |{% for row in site.data.MassBudget_environmental_infadjusted %}
| {{ row.LineItem }} | {{ row.LineItemName }} | {{ row.FY01 }} | {{ row.FY02 }} | {{ row.FY03 }} | {{ row.FY04 }} | {{ row.FY05 }} | {{ row.FY06 }} | {{ row.FY07 }} | {{ row.FY08 }} | {{ row.FY09 }} | {{ row.FY10 }} | {{ row.FY11 }} | {{ row.FY12 }} | {{ row.FY13 }} | {{ row.FY14 }} | {{ row.FY15 }} | {{ row.FY16 }} | {{ row.FY17 }} | {{ row.FY18_Gov }} |{% endfor %}
{: .sortable}

### Line-item level table (not inflation adjusted)

| Line Item | Name | FY01 | FY02 | FY03 | FY04 | FY05 | FY06 | FY07 | FY08 | FY09 | FY10 | FY11 | FY12 | FY13 | FY14 | FY15 | FY16 | FY17 | FY18_Gov |
| --- | --- | --- |{% for row in site.data.MassBudget_environmental_noinfadjusted %}
| {{ row.LineItem }} | {{ row.LineItemName }} | {{ row.FY01 }} | {{ row.FY02 }} | {{ row.FY03 }} | {{ row.FY04 }} | {{ row.FY05 }} | {{ row.FY06 }} | {{ row.FY07 }} | {{ row.FY08 }} | {{ row.FY09 }} | {{ row.FY10 }} | {{ row.FY11 }} | {{ row.FY12 }} | {{ row.FY13 }} | {{ row.FY14 }} | {{ row.FY15 }} | {{ row.FY16 }} | {{ row.FY17 }} | {{ row.FY18_Gov }} |{% endfor %}
{: .sortable}
