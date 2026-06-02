# Static Browsable Site for MA Lobbying Data — Proposal

This document contains the prompt used to commission a separate AI agent to build
a static browsable site for the MA environmental lobbying dataset.

---

## Agent Prompt

You are building a **standalone static website** that makes the Massachusetts lobbying
dataset explorable by journalists, researchers, and the general public. The site will
be hosted on GitHub Pages and must work entirely without a backend — all data is
loaded as pre-built JSON files at page load, and all filtering/search runs client-side.

### Source data

The source data is a set of CSV/parquet files exported from the AMEND project
(`github.com/nesanders/MAenvironmentaldata`). For this site, you will work from
pre-built JSON exports (described below). You do NOT need to access any databases
or APIs at runtime.

The key tables are:

1. **Bills** (`bills.json`) — one record per unique MA legislative bill that was
   lobbied. Fields:
   - `bill_id` (string, e.g. "H1234") — links to `malegislature.gov/Bills/{gc}/{bill_id}`
   - `bill_number` (int), `general_court` (int, 186–194)
   - `bill_title` (string)
   - `summary` (string, 1–3 sentence LLM summary)
   - `categories` (array of strings, e.g. ["Environmental Protection", "Energy"])
   - `tags` (array of strings, e.g. ["Renewable energy sources", "Pollution control"])
   - `is_env_llm` (bool) — LLM environmental classification
   - `env_relevance_score` (float, 0–1) — embedding similarity score
   - `cluster_id` (int), `cluster_label` (string)
   - `n_supporters` (int), `n_opposers` (int), `n_neutrals` (int)
   - `passed` (bool or null)

2. **Employers** (`employers.json`) — one record per unique lobbying client (employer).
   Fields:
   - `client_name` (string) — the paying employer (not the lobbying firm)
   - `n_bills_total` (int), `n_bills_env` (int)
   - `env_fraction` (float, 0–1) — fraction of their bills that are environmental
   - `total_compensation` (float) — total disclosed lobbying spend across all years
   - `env_compensation` (float) — proportionally allocated env lobbying spend
   - `years_active` (array of ints)
   - `top_tags` (array of strings — top 5 tags from their env bills)
   - `positions` (object: `{support: int, oppose: int, neutral: int}`)

3. **Lobbyists** (`lobbyists.json`) — one record per unique lobbying firm (entity).
   Fields:
   - `entity_name` (string)
   - `n_clients` (int), `n_env_clients` (int)
   - `total_compensation` (float)
   - `years_active` (array of ints)

4. **Edges** (`edges.json`) — one record per (employer, bill) lobbying disclosure.
   Fields:
   - `client_name` (string)
   - `entity_name` (string)
   - `bill_number` (int), `general_court` (int)
   - `year` (int)
   - `position` (string: "Support" | "Oppose" | "Neutral" | "")

5. **Cluster labels** (`clusters.json`) — one record per k-means cluster.
   Fields: `cluster_id`, `label`, `n_bills`, `n_env_bills`

### Site architecture

Build the site with **plain HTML, CSS, and vanilla JavaScript** (no frameworks, no
bundlers). GitHub Pages serves static files; there is no Node.js build step.
Each page loads its data via `fetch()` from the same origin. Use
`<script type="module">` for ES module imports across pages.

**File structure:**

```
index.html           — landing page with summary stats + search entry point
bills/
  index.html         — searchable/filterable bill list
  [bill_id].html     — per-bill detail page (generated at build time via a script)
employers/
  index.html         — searchable employer list with scatter plot
  [client_slug].html — per-employer detail page (generated at build time)
lobbyists/
  index.html         — lobbyist firm list
data/
  bills.json
  employers.json
  lobbyists.json
  edges.json
  clusters.json
assets/
  style.css
  search.js          — shared fuzzy-search / filter logic
  charts.js          — shared lightweight charting helpers (use Chart.js from CDN)
build/
  build_pages.py     — Python script that generates the per-entity static pages
```

### Pages specification

#### `index.html` — Landing page

- Header with site title: "MA Environmental Lobbying Explorer"
- Subtitle: "Browse 20 years of MA Legislature lobbying disclosures filtered to
  environmental and climate policy"
- Summary stat cards (loaded from `employers.json` + `bills.json`):
  - Total env bills in dataset
  - Total lobbying clients (employers)
  - Legislative sessions covered (GC186–194, 2009–2026)
  - Total disclosed lobbying spend (sum of compensation)
- Search bar that searches bill titles and employer names simultaneously,
  with a dropdown to jump to the bill or employer page
- "Explore by" section with three cards linking to bills/, employers/, lobbyists/
- Footer with link to the source AMEND project and data license (CC BY 4.0)

#### `bills/index.html` — Bill list

- Filter controls:
  - Text search (bill title / summary)
  - Category multi-select dropdown (from all categories in bills.json)
  - Tags multi-select dropdown (from all tags)
  - Environmental only toggle (default on)
  - General Court range slider (186–194)
  - Passed/active/unknown radio
- Results table (virtualized if > 500 rows):
  - Columns: Bill ID (link to detail page), Title, GC, Categories, Env score, # Clients, Passed
  - Default sort: n_supporters + n_opposers descending (most-lobbied first)
- Pagination: 50 per page

#### `bills/[bill_id].html` — Per-bill detail page

Generated by `build/build_pages.py` for every bill with `is_env_llm = True`.

Content:
- Bill title + link to `malegislature.gov`
- LLM summary (1–3 sentences)
- Metadata chips: General Court, Categories, Tags, Env score, Passed?
- "Who lobbied this bill" table:
  - Columns: Employer (link to employer page), Lobbying firm, Year, Position
  - Sorted by year desc
- Simple stacked bar: # supporters vs # opposers (if any)
- "See also" links: 3 most similar bills (by shared tags + cluster)

#### `employers/index.html` — Employer list

- Filter controls:
  - Text search (employer name)
  - Min env fraction slider (0–100%)
  - Min total spend slider
  - Year active multi-select (which GC sessions)
- Interactive scatter plot (Chart.js or Plotly CDN):
  - X: total_compensation ($K, log scale)
  - Y: env_fraction (%)
  - Dot size: n_bills_env
  - Color: env_fraction quartile (green → grey)
  - Click a dot → navigate to employer detail page
  - Hover tooltip: name, spend, env%
- Results table below the scatter (synced with filters):
  - Columns: Employer name (link), Env bills, Total spend ($K), Env fraction (%), Years active
  - Default sort: env_compensation descending

#### `employers/[client_slug].html` — Per-employer detail page

Generated for every employer with `n_bills_env >= 1`.

Content:
- Employer name + summary stats bar (total spend, env bills, env fraction, years active)
- Top tags bar chart (top 8 tags from their env bills, horizontal bar)
- Position breakdown: Support / Oppose / Neutral count + a small donut chart
- Bills lobbied table:
  - Columns: Bill ID (link), Title, Year, Position, Env score
  - Toggle: show env only / show all
- Timeline chart: bills per year + compensation per year (dual axis)
- "Most often opposed by" section: top 5 employers that filed opposite positions
  on the same bills as this employer (computed from edges.json)

#### `lobbyists/index.html` — Lobbyist firm list

- Table of lobbying firms sorted by total_compensation descending
- Columns: Firm name, Total clients, Env clients, Total compensation, Years active
- Filter: text search, env-clients-only toggle

### Data build script (`build/build_pages.py`)

This Python script (run once, or in CI) generates the static per-entity pages.
It reads the 5 JSON files from `data/` and:

1. For each env bill in `bills.json`, writes `bills/{bill_id}.html` from a
   Jinja2 template (`build/templates/bill.html`).
2. For each employer with `n_bills_env >= 1` in `employers.json`, writes
   `employers/{client_slug}.html` from `build/templates/employer.html`
   (slug = `re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')`).
3. Writes `bills/index.html` and `employers/index.html` with the full JSON
   payloads inlined as `<script>window.__DATA__ = {...}</script>` for instant load.

Run it with: `python build/build_pages.py`

Dependencies: Python 3.10+, Jinja2. No other external packages.

### JSON export script (`build/export_json.py`)

This Python script (run against the AMEND project DB and parquet) exports the
5 JSON files. It lives in the AMEND repo, not this repo.

Key logic:
- `bills.json`: query `MA_Lobbying_Bills_Scored` + parquet for LLM columns;
  compute `n_supporters`, `n_opposers`, `n_neutrals` from `MA_Lobbying_Bills`.
- `employers.json`: compute aggregates from `MA_Lobbying_Employers` + `MA_Lobbying_Bills`
  + parquet env flag.
- `edges.json`: direct export of `MA_Lobbying_Bills` with position field.
- Run from `get_data/`: `python export_json.py`

### Styling

Use a minimal, readable CSS design:
- Font: system-ui / -apple-system stack (no web fonts)
- Primary color: `#2c7a45` (forest green) — used for environmental highlights
- Neutral color: `#555555`
- Background: `#f9f9f6` (off-white)
- Card shadow: `box-shadow: 0 1px 3px rgba(0,0,0,0.12)`
- Tables: striped rows, no outer border, sticky header
- Mobile responsive: single-column layout below 600px

### Non-goals (explicitly out of scope)

- User accounts, authentication, or saved searches
- Server-side rendering or dynamic routes
- Real-time data updates (data is updated by re-running the export script and
  committing the JSON files)
- The bills with `is_env_llm = False` do not need individual detail pages
  (they appear in employer pages and can link to `malegislature.gov` directly)

### Repository setup

Initialize a new GitHub repository: `ma-lobbying-explorer` (public).
Create a `gh-pages` branch or configure Pages to serve from `main / root`.
Add a `README.md` with:
- Site description and live URL
- How to update the data (re-run `export_json.py` in the AMEND repo, copy
  JSON files here, run `build_pages.py`, commit and push)
- License: data CC BY 4.0, code MIT

---

*This proposal was drafted on 2026-06-01 as part of the AMEND environmental
data project. See the source repo at `github.com/nesanders/MAenvironmentaldata`.*
