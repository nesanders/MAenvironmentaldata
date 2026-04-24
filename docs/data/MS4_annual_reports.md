---
title: MA MS4 Municipal Stormwater Annual Reports
author: NES
layout: data_listing
ancillary: 0
---

## Data source

[Municipal Separate Storm Sewer Systems](https://www.epa.gov/npdes-permits/massachusetts-small-ms4-general-permit) (MS4s) are networks of pipes, ditches, and drains — owned by cities and towns — that collect stormwater runoff and discharge it directly to rivers, ponds, and coastal waters without treatment. Unlike combined sewers, MS4s are designed to carry only stormwater, but they remain a major pathway for pollutants including phosphorus, bacteria, metals, and road salt into Massachusetts waterways.

Under [Section 402 of the Clean Water Act](https://www.epa.gov/cwa-404/clean-water-act-section-402-national-pollutant-discharge-elimination-system), operators of MS4s must obtain NPDES stormwater permits and implement a Stormwater Management Program (SWMP) covering six [Minimum Control Measures](https://www.epa.gov/system/files/documents/2025-11/six-minimum-control-measures.pdf) (MCMs):

| # | MCM | What permittees must do |
|---|---|---|
| 1 | Public Education & Outreach | Distribute educational materials on stormwater impacts |
| 2 | Public Participation | Involve the public in SWMP development and implementation |
| 3 | Illicit Discharge Detection & Elimination (IDDE) | Map outfalls, screen for non-stormwater flows, eliminate illicit connections |
| 4 | Construction Site Runoff Control | Inspect active construction sites and enforce erosion controls |
| 5 | Post-Construction Stormwater Management | Require and inspect stormwater BMPs for new development |
| 6 | Pollution Prevention / Good Housekeeping | Inspect and maintain municipal facilities and catch basin infrastructure |

Approximately 316 Massachusetts municipalities and institutions operate under EPA Region 1's [Massachusetts Small MS4 General Permit](https://www.epa.gov/npdes-permits/massachusetts-small-ms4-general-permit).
Each permittee submits an annual report to EPA documenting their SWMP activities.
Reports are publicly available on the
[EPA Region 1 MA MS4 community page](https://www.epa.gov/npdes-permits/regulated-ms4-massachusetts-communities).

{% if site.data.ts_update_MS4 %}AMEND has archived **{{ site.data.ts_update_MS4.updated | date: "%-d %B %Y" }}** and indexed
**{{ site.data.MS4_report_index.size }}** annual report PDFs.{% else %}AMEND is actively archiving and indexing annual report PDFs.{% endif %}
The current permit cycle (Permit Years 1–7, FY2019–FY2025) is covered.

## AI extraction methodology

MS4 annual reports are semi-structured government forms submitted as PDFs, with no machine-readable structured data source. AMEND uses the [Google Gemini 2.5 Flash](https://ai.google.dev/gemini-api/docs) AI model with forced [function calling](https://ai.google.dev/gemini-api/docs/function-calling) to extract a standardized schema from each report.

**Pipeline:**

1. **Index scraping** — EPA's HTML listing page is scraped weekly for new report PDFs (same approach as the [NPDES permits dataset](EPARegion1_NPDES_permit_data.html)).
2. **PDF archive** — Each PDF is downloaded and archived on the AMEND backend for permanent public access.
3. **Portfolio detection** — Some municipalities submit PDF portfolios (embedded-file containers) that cannot be directly read. These are detected and extracted for processing. Approximately 25–40% of recent-year reports (FY2024–FY2025) appear to use this format.
4. **Structured extraction** — Each readable PDF is uploaded to the Gemini Files API and queried with a schema enforced via function calling. AMEND records source page references for every section, enabling manual verification of what data was extracted from which PDF page.
5. **Confidence rating** — The AI model assigns `high`, `medium`, or `low` confidence based on completeness and document quality.

**Known limitations:**

- **Cumulative vs. period counts**: The permit requires some counts (illicit discharges found/eliminated) to be cumulative since permit start; others are period-only. The `mcm3_count_type` field records which interpretation applies.
- **TMDL scope**: Some municipalities list only the TMDLs applicable to their specific waterbodies (`tmdl_municipality_specific = True`); others reproduce the general permit's full statewide TMDL list (`False`). Only municipality-specific entries are analytically meaningful for compliance tracking.
- **MCM6 catch basins vs. facilities**: Many municipalities report catch basin inspection counts under MCM6; the `mcm6_notes` field clarifies what the count refers to.
- **Non-traditional MS4s**: Universities and state agencies (permit prefix `MAR042`) operate under the same general permit but with different physical infrastructure. Their reports are included but MCM counts may not be comparable to municipal permittees.

## Data currency

This data is indexed from the
[EPA Region 1 MA MS4 community page](https://www.epa.gov/npdes-permits/regulated-ms4-massachusetts-communities),
{% if site.data.ts_update_MS4 %}last updated on **{{ site.data.ts_update_MS4.updated | date: "%-d %B %Y" }}**.{% else %}updated weekly.{% endif %}
AMEND checks weekly and will automatically incorporate new reports when EPA posts them.

## Download

* [MS4 report index](MS4_report_index.csv) — one row per discovered PDF, with EPA URL, GCS archive URL, municipality, and year
* [MS4 extracted data](MS4_extracted.csv) — one row per extracted report, with all MCM fields, TMDL waterbodies (JSON), and traceability fields

## Extraction failures

{% if site.data.MS4_failures.count and site.data.MS4_failures.count > 0 %}
{{ site.data.MS4_failures.count }} report{% if site.data.MS4_failures.count != 1 %}s{% endif %} could not be extracted successfully and are excluded from the dataset. These are logged automatically each time the pipeline runs.

| File | Municipality | Year | Reason |
|---|---|---|---|{% for f in site.data.MS4_failures.failures %}
| [{{ f.filename }}]({{ site.data.MS4_report_index | where: "filename", f.filename | map: "url" | first }}){:target="_blank"} | {{ f.municipality }} | {{ f.report_year }} | {{ f.notes }} |{% endfor %}
{% else %}
No extraction failures in the current dataset.
{% endif %}

## Sample extracted data

The table below shows extracted records from the dataset.
Click **Source PDF** to view the original EPA PDF; click **GCS Archive** for the AMEND archive copy.

*Click on the table headers to re-sort by that field.*

| Municipality | Year | Permit # | MCM1 Activities | MCM2 Activities | MCM3 Outfalls | MCM3 Illicit Found | MCM4 Sites | MCM5 Sites | MCM6 Facilities | Confidence | Source PDF | GCS Archive |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |{% assign ms4_sample = site.data.MS4_extracted | sort: "report_year" | reverse %}{% for row in ms4_sample limit:10 %}
| {{ row.municipality }} | {{ row.report_year }} | {{ row.permit_number }} | {{ row.mcm1_activities_count }} | {{ row.mcm2_activities_count }} | {{ row.mcm3_outfalls_total }} | {{ row.mcm3_illicit_found }} | {{ row.mcm4_sites_inspected }} | {{ row.mcm5_sites_inspected }} | {{ row.mcm6_facilities_inspected }} | {{ row.extraction_confidence }} | [PDF]({{ row.source_url }}){:target="_blank"} | [GCS]({{ row.gcs_url }}){:target="_blank"} |{% endfor %}
{: .sortable}
