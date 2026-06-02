# Static Browsable Site for MA Lobbying Data — Proposal

This document contains the prompt used to commission a separate AI agent to build
a static browsable site for the MA legislative lobbying dataset.

---

## Agent Prompt

You are building a **standalone static website** that makes the Massachusetts lobbying
dataset explorable by journalists, researchers, and the general public. The site covers
**all bills with any lobbying record** — not just environmental ones. Environmental
classification is one filter among many, not a scope constraint.

The site will be hosted on GitHub Pages and must work entirely without a backend — all
data is loaded as pre-built JSON files at page load, and all filtering, routing, and
rendering runs client-side in the browser. There is no build step that generates a
page per entity; instead, bill and employer detail views are rendered on-the-fly by
reading the URL query string (e.g. `bills.html?id=H1234&gc=194`).

### Source data

The source data is exported from the AMEND project (`github.com/nesanders/MAenvironmentaldata`).
You will work from pre-built JSON exports (described below). You do NOT need to access
any databases or APIs at runtime.

The key tables are:

1. **Bills** (`data/bills.json`) — one record per unique MA legislative bill that was
   lobbied. Fields:
   - `bill_id` (string, e.g. "H1234") — links to `malegislature.gov/Bills/{gc}/{bill_id}`
   - `bill_number` (int), `general_court` (int, 186–194)
   - `bill_title` (string)
   - `summary` (string or null — 1–3 sentence LLM summary; null if not yet generated)
   - `categories` (array of strings, e.g. ["Environmental Protection", "Energy"]; empty array if no summary)
   - `tags` (array of strings, e.g. ["Renewable energy sources", "Pollution control"]; empty if no summary)
   - `is_env_llm` (bool) — LLM environmental classification (false if no summary)
   - `env_relevance_score` (float 0–1) — embedding similarity score (0 if not embedded)
   - `cluster_id` (int or null), `cluster_label` (string or null)
   - `n_supporters` (int), `n_opposers` (int), `n_neutrals` (int), `n_no_position` (int)
   - `passed` (bool or null)

2. **Employers** (`data/employers.json`) — one record per unique lobbying client (employer).
   Fields:
   - `client_name` (string) — the paying employer (not the lobbying firm)
   - `client_slug` (string) — URL-safe slug: `re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')`
   - `n_bills_total` (int), `n_bills_env` (int)
   - `env_fraction` (float 0–1) — fraction of their bills that are environmental
   - `total_compensation` (float) — total disclosed lobbying spend across all years
   - `env_compensation` (float) — proportionally allocated env lobbying spend
   - `years_active` (array of ints)
   - `top_tags` (array of strings — top 5 LLM tags from their env bills; empty if no env bills)
   - `positions` (object: `{support: int, oppose: int, neutral: int, none: int}`)

3. **Lobbyists** (`data/lobbyists.json`) — one record per unique lobbying firm (entity).
   Fields:
   - `entity_name` (string)
   - `entity_slug` (string) — URL-safe slug
   - `n_clients` (int), `n_env_clients` (int)
   - `total_compensation` (float)
   - `years_active` (array of ints)

4. **Edges** (`data/edges.json`) — one record per (employer, bill) lobbying disclosure.
   Fields:
   - `client_name` (string)
   - `entity_name` (string)
   - `bill_number` (int), `general_court` (int)
   - `bill_id` (string)
   - `year` (int)
   - `position` (string: "Support" | "Oppose" | "Neutral" | "")

5. **Cluster labels** (`data/clusters.json`) — one record per k-means cluster.
   Fields: `cluster_id`, `label`, `n_bills`, `n_env_bills`

**Data sizes to plan for:** ~26,000 bills, ~4,500 employers, ~1,200 lobbyist firms,
~200,000 edges. Keep JSON files small: strip whitespace (`json.dumps(..., separators=(',',':'))`).
At these sizes, `bills.json` will be ~8–12 MB and `edges.json` ~15–20 MB uncompressed.
GitHub Pages serves gzip-compressed responses automatically, so wire size will be 2–4×
smaller, but you should still lazy-load `edges.json` only when a detail view needs it.

### URL and routing design

There is **no server-side routing**. All navigation uses query strings on flat HTML files,
which GitHub Pages can serve without a 404 problem:

| View | URL pattern |
|------|-------------|
| Landing page | `index.html` |
| Bill list | `bills.html` |
| Bill detail | `bills.html?id=H1234&gc=194` |
| Employer list | `employers.html` |
| Employer detail | `employers.html?name=associated-industries-of-massachusetts-aim` |
| Lobbyist list | `lobbyists.html` |
| Lobbyist detail | `lobbyists.html?name=some-firm-slug` |

Each `.html` file checks `new URLSearchParams(location.search)` on load:
- If no query params → render the list/search view
- If detail params present → render the detail view

This means every file is one page that renders two views. No build step. No per-entity
HTML files. All internal links (e.g. in the bill list, an employer name is a link) just
append `?name=slug` to the appropriate page URL.

### File structure

```
index.html           — landing page with summary stats + search bar
bills.html           — bill list + bill detail (query-driven)
employers.html       — employer list + employer detail (query-driven)
lobbyists.html       — lobbyist list + lobbyist detail (query-driven)
data/
  bills.json         — ~26k bills, all fields above
  employers.json     — ~4.5k employers
  lobbyists.json     — ~1.2k firms
  edges.json         — ~200k edges (lazy-loaded)
  clusters.json      — 25 clusters
assets/
  style.css
  app.js             — shared data loading, routing, and rendering utilities
  charts.js          — Chart.js wrappers for the reused chart types
build/
  export_json.py     — run in the AMEND repo to regenerate the JSON files
```

No Jinja2, no templating engine, no build step. Just `fetch()` + DOM manipulation.

### Shared JS architecture (`assets/app.js`)

```js
// Global data cache — populated by loadData()
window.__DATA__ = { bills: null, employers: null, lobbyists: null, clusters: null };

// Call once at page load; edges are NOT loaded here — only on demand
async function loadData() { ... }

// Read URL params and decide list vs. detail view
function routePage(listFn, detailFn, paramKey) {
  const p = new URLSearchParams(location.search);
  if (p.has(paramKey)) detailFn(p);
  else listFn();
}

// Shared paginated table renderer
function renderTable(container, columns, rows, opts = {}) { ... }

// Shared fuzzy text filter
function fuzzyFilter(rows, query, fields) { ... }
```

Each page calls `loadData()` then `routePage(...)` in its own `<script type="module">`.

### Pages specification

#### `index.html` — Landing page

- Site title: "MA Lobbying Explorer" (not "Environmental Lobbying Explorer" — covers all bills)
- Subtitle: "Browse 20 years of Massachusetts Legislature lobbying disclosures"
- Summary stat cards (computed from `bills.json` + `employers.json` at load time):
  - Total bills with any lobbying record
  - Total distinct employers (clients)
  - Legislative sessions covered (GC186–194, 2009–2026)
  - Total disclosed lobbying compensation
- Optional highlight: "X of those bills were flagged as environmentally relevant"
  (with a link to `bills.html?env=1` as a pre-filtered view)
- Global search bar: searches bill titles + employer names simultaneously;
  results dropdown shows top 5 matches in each category with links to their detail views
- Three explorer cards: Bills → `bills.html`, Employers → `employers.html`,
  Lobbyists → `lobbyists.html`
- Footer: link to AMEND project, data license (CC BY 4.0), last-updated date

#### `bills.html` — Bill list and bill detail

**List view** (no query params):

- Filter controls (all update the URL via `history.replaceState` so the filtered
  view is bookmarkable / shareable):
  - Text search (bill title / summary)
  - Environmental only toggle (default **off** — shows all bills by default)
  - Category multi-select dropdown
  - Tags multi-select dropdown
  - General Court range slider (186–194)
  - Position activity: "has supporters", "has opposers", "contested" (both)
  - Passed filter: All / Passed / Not passed / Unknown
- Results table (50 per page, with total count displayed):
  - Columns: Bill ID (links to `bills.html?id=H1234&gc=194`), Title, GC,
    Categories, # Clients, Supported/Opposed, Env?, Passed
  - Default sort: `n_supporters + n_opposers` descending
  - Row click → navigate to detail view
- The "Env?" column shows a 🌿 icon for `is_env_llm = true` bills

**Detail view** (`?id=H1234&gc=194`):

- Rendered entirely client-side from `bills.json` + lazy-loaded `edges.json`
- Content:
  - Bill title (h1) + "← Back to bill list" breadcrumb
  - External link chip: "View on malegislature.gov ↗"
  - Metadata row: GC badge, 🌿 env badge (if applicable), env score, cluster label,
    categories chips, tags chips, Passed badge
  - LLM summary block (if present; grey italic if null)
  - "Who lobbied this bill" table:
    - Lazy-loads `edges.json`, filters to this bill's (bill_number, general_court)
    - Columns: Employer (link to `employers.html?name=slug`), Lobbying firm
      (link to `lobbyists.html?name=slug`), Year, Position (colour-coded chip)
    - Sorted by year desc
  - Mini stacked bar (Chart.js): # supporters vs # opposers vs # neutral
  - "See also" — 3 bills with the most shared tags + same cluster_id (computed
    client-side from `bills.json`)

#### `employers.html` — Employer list and employer detail

**List view** (no query params):

- Filter controls:
  - Text search (employer name)
  - Environmental focus slider: min env fraction (0–100%)
  - Min total spend filter (text input, $K)
  - "Active in session" multi-select (GC186–GC194 checkboxes)
- Interactive scatter (Chart.js, loaded from `employers.json`):
  - X: total_compensation (log scale), Y: env_fraction × 100
  - Bubble size: √(n_bills_total), capped at 30px
  - Color: env_fraction quartile (green shades)
  - Click → navigate to that employer's detail view
  - Hover tooltip: name, spend, env%, n bills
  - Scatter syncs with the filter controls — only matching employers are shown
- Table below scatter (synced with same filters):
  - Columns: Employer (link to detail), Total bills, Env bills, Env fraction,
    Total spend ($K), Years active
  - Default sort: total_compensation desc

**Detail view** (`?name=associated-industries-of-massachusetts-aim`):

- Content:
  - Employer name (h1) + "← Back to employer list" breadcrumb
  - Summary stats bar: Total spend · Env bills · Env fraction · Years active
  - Top tags horizontal bar (Chart.js, from `top_tags` in employers.json)
    (only shown if n_bills_env > 0)
  - Position breakdown donut (Support / Oppose / Neutral / No position)
  - Timeline chart (Chart.js dual-axis line): bills per year (left) +
    compensation per year (right) — data computed from lazy-loaded `edges.json`
  - Bills lobbied table (from edges.json, filtered to this employer):
    - Columns: Bill ID (link to bill detail), Title, Year, Position chip, Env?
    - Toggle: "Environmental bills only" checkbox (default off)
    - Default sort: year desc
  - "Most often on opposite sides" section:
    - Computed from `edges.json`: find all bills this employer lobbied, look up
      other employers who filed the opposite position on those same bills,
      count collisions, show top 5 as a small table with counts
    - Only shown if any opposition pairs exist

#### `lobbyists.html` — Lobbyist firm list and detail

**List view**:
- Table of lobbying firms, default sort: total_compensation desc
- Columns: Firm name (link to detail), Clients, Env clients, Total compensation, Years active
- Filters: text search, "env clients only" toggle

**Detail view** (`?name=firm-slug`):
- Firm name, summary stats: total clients, env clients, total compensation, years active
- Clients table (from `employers.json`, filtered to firms that appear in `edges.json`
  for this entity): Employer (link), Bills, Env bills, Years worked together
- Year activity chart: compensation per year (bar)

### Data loading strategy

```
Page load:         fetch bills.json    (~3MB gzipped) — needed for list + detail
                   fetch employers.json (~500KB gzipped)
                   fetch lobbyists.json (~150KB gzipped)
                   fetch clusters.json  (<5KB)

On detail view:    fetch edges.json    (~5MB gzipped) — lazy, only once, cached
```

Use a module-level promise so `edges.json` is fetched at most once per page session:
```js
let edgesPromise = null;
function getEdges() {
  if (!edgesPromise) edgesPromise = fetch('data/edges.json').then(r => r.json());
  return edgesPromise;
}
```

Show a loading spinner while `edges.json` fetches (typically <1s on broadband).

### Styling

- Font: system-ui / -apple-system (no web fonts)
- Primary color: `#1a5f3c` (dark green — for env highlights only; not the site's primary)
- Site primary: `#2563eb` (blue — for links and active states)
- Background: `#f8f9fa`, card background: `#ffffff`
- `box-shadow: 0 1px 3px rgba(0,0,0,0.10)` on cards
- Tables: `border-collapse: collapse`, alternating `#f8f9fa` / `#fff` row background,
  sticky `<thead>` with `position: sticky; top: 0; background: #fff; z-index: 1`
- Position chips: Support = green background, Oppose = red background,
  Neutral = grey, none = lighter grey
- Env 🌿 badge: green background, shown only when `is_env_llm = true`
- Mobile responsive: single-column below 640px; table columns collapse gracefully

### Non-goals (explicitly out of scope)

- Server-side rendering, Node.js, or any build toolchain
- User accounts or saved searches
- Real-time updates (data is updated by re-running `export_json.py` and committing)
- Generating one HTML file per bill or employer — everything is query-string-driven

### JSON export script (`build/export_json.py`)

This Python script runs against the AMEND project's `get_data/AMEND.db` and
`docs/data/MA_bill_embeddings.parquet`. It lives in the AMEND repo, not this repo.

Key logic:
- `bills.json`: join `MA_Lobbying_Bills_Scored` + parquet LLM columns; compute
  position counts from `MA_Lobbying_Bills`; write all ~26k lobbied bills.
- `employers.json`: aggregate per-`client_name` stats from `MA_Lobbying_Employers`
  + `MA_Lobbying_Bills` + parquet env flag; compute `client_slug`.
- `lobbyists.json`: aggregate per-`entity_name` from `MA_Lobbying_Employers` +
  `MA_Lobbying_Bills`; compute `entity_slug`.
- `edges.json`: direct export of `MA_Lobbying_Bills` with `bill_id` joined in.
- `clusters.json`: export `MA_Bill_Cluster_Labels`.
- Run from `get_data/`: `python export_json.py`
- Dependencies: pandas, sqlalchemy, gcsfs (for parquet). No new deps.

### Repository setup

New GitHub repository: `ma-lobbying-explorer` (public).
Configure GitHub Pages to serve from `main` branch, root directory.

`README.md`:
- Site description and live URL (e.g. `https://nesanders.github.io/ma-lobbying-explorer`)
- Data coverage: all MA legislature lobbying disclosures 2009–2026, ~26,000 bills,
  ~4,500 employers, ~1,200 lobbying firms
- How to update: re-run `export_json.py` in the AMEND repo, copy the 5 JSON files
  into `data/`, commit and push — no other step required
- License: data CC BY 4.0 (source: MA Secretary of State), code MIT

---

*This proposal was drafted on 2026-06-01 as part of the AMEND environmental
data project. See the source repo at `github.com/nesanders/MAenvironmentaldata`.*
