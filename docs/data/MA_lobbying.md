---
title: MA Lobbying Disclosures
author: NES
layout: data_listing
ancillary: 0
---

## Data source

The [MA Secretary of State](https://www.sec.state.ma.us/LobbyistPublicSearch/) publishes semi-annual lobbying disclosure filings for all registered lobbyists and lobbying entities in Massachusetts. Filers report which clients hired them, how much each client paid, and which specific bills they lobbied on behalf of each client (with chamber, bill number, title, and position — Support, Oppose, or Neutral).

Data is available from 2005 (183rd General Court) through the present, spanning 22 years across 11 legislative sessions. Each two-year legislative session is identified by a General Court number (GC 183 = 2005–2006, GC 194 = 2025–2026, etc.).

To identify environmentally relevant bills, each bill's title is scored for semantic similarity to a set of environmental regulation seed phrases using Google Gemini embeddings (`gemini-embedding-2`). Bills with a cosine similarity score above 0.60 are flagged as `is_environmental`.

The data from this source has been archived on this site, last updated on **{{ site.data.ts_update_MA_lobbying.updated | date: "%-d %B %Y %I:%M %P" }}**.
Filings are refreshed automatically on a weekly basis; the script exits early when no new semi-annual filings have been posted.

## Download archive

* [Lobbying employers (entity–client–year)](MA_lobbying_employers.csv)
* [Lobbying bills (entity–client–bill–year)](MA_lobbying_bills.csv)
* [Legislature bill metadata](MA_legislature_bills.csv)

## Data tables

### Lobbying Employers

One row per (entity, client, year). Records how much each client paid each lobbying entity in a given year.

| Entity Name | Client Name | Year | Reg Type | Compensation |
| --- | --- | --- | --- | --- |{% for row in site.data.MA_lobbying_employers_sample %}
| {{ row.entity_name }} | {{ row.client_name }} | {{ row.year }} | {{ row.reg_type }} | {{ row.compensation }} |{% endfor %}
{: .sortable}

### Lobbying Bills

One row per (entity, client, bill, session). Records which bills each entity lobbied on behalf of each client, with the lobbying position.

| Entity Name | Client Name | Year | Chamber | Bill Number | Bill Title | Position |
| --- | --- | --- | --- | --- | --- | --- |{% for row in site.data.MA_lobbying_bills_sample %}
| {{ row.entity_name }} | {{ row.client_name }} | {{ row.year }} | {{ row.chamber }} | {{ row.bill_number }} | {{ row.bill_title }} | {{ row.position }} |{% endfor %}
{: .sortable}

### Legislature Bills

Bill metadata fetched from the [MA Legislature OpenAPI](https://malegislature.gov/api/swagger). Includes sponsor, committee, final status, and derived `passed` boolean. Bills are scored for environmental relevance using Gemini embeddings.

| Bill Number | General Court | Title | Sponsor | Committee | Status | Passed | Env. Score |
| --- | --- | --- | --- | --- | --- | --- | --- |{% for row in site.data.MA_legislature_bills_sample %}
| {{ row.bill_number }} | {{ row.general_court }} | {{ row.title }} | {{ row.sponsor_name }} | {{ row.committee }} | {{ row.status }} | {{ row.passed }} | {{ row.env_relevance_score }} |{% endfor %}
{: .sortable}
