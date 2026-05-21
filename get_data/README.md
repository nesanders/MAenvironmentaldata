# get_data — Data fetch scripts

All scripts must be run from this directory (`get_data/`) because they use relative
paths to `../docs/data/` for outputs and `../docs/assets/` for generated files.

Run every script with the `amend_python` conda environment:

```bash
conda run -n amend_python python <script>.py
# or directly (required for live log output — conda run buffers stdout):
/home/nes/miniconda/envs/amend_python/bin/python -u <script>.py
```

---

## Weekly CI pipeline

These scripts run automatically every Monday via `.github/workflows/update-data.yml`:

| Order | Script | Data source |
|-------|--------|-------------|
| 1 | `get_EPARegion1_NPDES_permits.py` | EPA NPDES permit listings |
| 2 | `get_budget_CTHRU.py` | MA Comptroller CTHRU (FY2005–present) |
| 3 | `get_DEP_staff_SODA.py` | MA Comptroller payroll SODA API |
| 4 | `get_EEA_data_portal.py` | EEA portal (permits, facilities, inspections, enforcement, drinking water) |
| 5 | `get_eea_dp_cso.py` | EEA CSO discharge incidents |
| 6 | `get_ATTAINS_303d.py` | EPA 303(d) impaired waters (biennial; exits early if unchanged) |
| 7 | `get_MA_lobbying.py` | MA SoS lobbying disclosures (incremental) |
| 8 | `get_MA_legislature_bills.py` | MA Legislature bill metadata (incremental) |
| 9 | `score_lobbying_bills.py` | Gemini embeddings + environmental scoring (incremental) |
| 10 | `validate_data.py` | Schema + row-count checks |
| 11 | `assemble_db.py` | Build SQLite DB, upload to GCS, regenerate semantic context |

---

## MA Lobbying pipeline (scripts 7–9 + cluster)

### Overview

The MA lobbying pipeline tracks which bills are being lobbied in the Massachusetts
legislature, how much is spent, and whether those bills are environmentally relevant.
It spans four scripts, the first three of which run in weekly CI:

```
get_MA_lobbying.py
    ↓ MA_lobbying_employers.csv, MA_lobbying_bills.csv, MA_lobbying_summary_links.csv
get_MA_legislature_bills.py
    ↓ MA_legislature_bills.csv  +  MA_legislature_cache/<bill>.json
score_lobbying_bills.py
    ↓ MA_lobbying_bills_scored.csv  +  gs://openamend-data/MA_bill_embeddings.parquet
cluster_lobbying_bills.py   ← manual / one-time
    ↓ MA_bill_cluster_labels.csv  (cluster_id column also written back to scored CSV)
```

---

### 1. `get_MA_lobbying.py` — Scrape the SoS lobbying portal

**Source:** MA Secretary of State [LobbyistPublicSearch](https://www.sec.state.ma.us/LobbyistPublicSearch/)

**How it works:**

The portal is an ASP.NET site protected by Incapsula WAF. A plain Chrome user-agent
gets a JS challenge redirect, but an **iPad user-agent bypasses it entirely** with
plain `requests` — no Selenium needed:

```
Mozilla/5.0 (iPad; CPU OS 12_2 like Mac OS X) AppleWebKit/605.1.15 ...
```

Each run follows three page hops per registrant:

1. **Search POST** to `Default.aspx` with `drpType=L` (Lobbyist/Entity), `drpPageSize=20000`,
   `ddlYear=<year>` → returns a table of ~1,700 registrants with Summary links.
2. **Summary page** (`Summary.aspx`) → registrant name, year, type, and up to 2
   `CompleteDisclosure.aspx` links (one per semi-annual reporting period).
3. **CompleteDisclosure page** → compensation paid by each client + list of bills
   lobbied per client.

**Incremental strategy:**

The set of already-fetched `CompleteDisclosure` URLs is persisted in
`MA_lobbying_summary_links.csv`. On each run:
- All years with no cached links are fetched in full.
- The current year and prior year are always re-searched (new filers arrive
  semi-annually); only new disclosure URLs trigger a detail fetch.
- If no new disclosure URLs are found, the script exits immediately without
  writing any files.

**Resumability:**

All three output CSVs are flushed to disk after every completed disclosure URL.
An interrupted run loses at most one disclosure's work. On restart, already-fetched
URLs are skipped automatically.

**Historical fetch:**

The portal has data back to 2005 (~22 years, ~1,700 registrants/year). At 1 s/request
with ~2 requests per registrant, each year takes roughly 1–2 hours. Run without
`--year` to fetch all missing years. Monitor progress with:

```bash
tail -f lobbying_historical_fetch.log
```

**Two HTML formats:**

Old filings (roughly pre-2013) use a different page structure:
- *Modern*: per-client compensation in `grdvClientPaidToEntity`; per-client bill
  activity in `grdvActivitiesNew{year}_{n}` (one table per client per period).
- *Legacy*: total salary paid across all clients in `grdvSalaryPaid` (no per-client
  breakdown); all bill activity in a single `grdvActivities` table with a "Client
  represented" column. Legacy compensation rows use the placeholder client name
  `_total_salary_`.

**Outputs:**

| File | Rows | Description |
|------|------|-------------|
| `MA_lobbying_employers.csv` | ~1,650/year | One row per (entity, client, year): compensation |
| `MA_lobbying_bills.csv` | ~14,800/year | One row per (entity, client, bill, year): chamber, bill number, title, position |
| `MA_lobbying_summary_links.csv` | ~3,300/year | Persistent link registry (incremental state) |

---

### 2. `get_MA_legislature_bills.py` — Fetch bill metadata from the Legislature API

**Source:** [MA Legislature OpenAPI](https://malegislature.gov/api/swagger)

**How it works:**

Reads all unique `(bill_number, chamber, general_court)` tuples from
`MA_lobbying_bills.csv`, constructs a chamber-prefixed bill ID (e.g. `H4999` for
House Bill 4999), and calls:

```
GET /GeneralCourts/{general_court}/Documents/{bill_id}
```

Note: the correct endpoint is `/Documents/`, **not** `/Bills/` (which returns 404).

Bill IDs require a chamber prefix:

| Portal chamber value | API prefix | Example |
|----------------------|------------|---------|
| House Bill | H | H4999 |
| House Docket | HD | HD123 |
| Senate Bill | S | S607 |
| Senate Docket | SD | SD45 |

Bill history (used to derive the `passed` boolean) is fetched from the `BillHistory`
URL embedded in the document response. A bill is marked `passed = True` if the last
history action contains keywords like "Signed by the Governor" or "Chaptered".

**Caching:**

Raw JSON responses are cached as `MA_legislature_cache/{key}.json`. This directory
is gitignored. The merged output CSV is flushed every 50 bills, so an interrupted run
loses at most 50 bills' API calls (which are cheap and fast at 0.5 s/request).

**Output:** `MA_legislature_bills.csv` — bill_id, bill_number, general_court, title,
sponsor_name, status, passed.

The full-text bill content stored in the JSON cache is also used by
`score_lobbying_bills.py` to embed bill text rather than just titles.

---

### 3. `score_lobbying_bills.py` — Gemini embeddings + environmental scoring

**Requires:** `SECRET_GOOGLE_API_KEY` file in `get_data/` containing a Google AI
Studio API key with access to `gemini-embedding-2`.

**SDK:** Uses `google-genai` (new SDK), **not** the old `google-generativeai` package:

```python
from google import genai
client = genai.Client(api_key=...)
client.models.embed_content(
    model='gemini-embedding-2',
    contents=text,
    config=types.EmbedContentConfig(output_dimensionality=768),
)
```

**What gets embedded:**

For each bill, the script looks up the cached JSON from `MA_legislature_cache/` and
uses the first 2,000 characters of the full bill text. If no cached JSON exists (about
3% of bills), it falls back to the bill title from the lobbying CSV. Embedding full
text rather than titles dramatically improves discrimination — titles are often generic
legislative boilerplate.

**Incremental operation:**

The Parquet file on GCS (`gs://openamend-data/MA_bill_embeddings.parquet`) is the
authoritative store of all embeddings. On each run, bills already in the Parquet are
skipped. Only new bills (from new lobbying data or new legislative sessions) are
embedded. This means weekly CI typically embeds zero or a handful of bills.

**Environmental scoring — differential cosine similarity:**

Rather than scoring against seed phrases (which compress all scores into a narrow
range), the script uses two reference sets of 20 real MA bills each:

- `ENV_EXAMPLE_BILLS` — 20 actual environmental bills (PFAS, stormwater, clean energy, etc.)
- `NON_ENV_EXAMPLE_BILLS` — 20 actual non-environmental bills (health, labor, education, etc.)

For each bill:

```
env_score = max cosine similarity to any ENV_EXAMPLE_BILLS embedding
non_env_score = max cosine similarity to any NON_ENV_EXAMPLE_BILLS embedding
differential = env_score - non_env_score
is_environmental = (differential > 0.05)
```

This approach anchors scoring to real legislative language, avoids compressed ranges,
and discriminates between superficially similar bills (e.g., public health vs.
environmental health).

**Storage:**

| Location | Contents | Updated |
|----------|----------|---------|
| `gs://openamend-data/MA_bill_embeddings.parquet` | Full embeddings (768-dim) + bill text + scores + cluster_ids | Every CI run |
| `docs/data/MA_lobbying_bills_scored.csv` | Lightweight: scores + cluster_ids, no embeddings | Every CI run, committed to repo |

The Parquet is ~100 MB for the full historical corpus and is **not** committed to the
repo. The scored CSV is ~300 KB and is committed.

**Cost:** Approximately $0.008/1,000 bills at current Gemini embedding pricing.
The full 2024 corpus of 2,648 unique bills cost roughly $0.02 to embed.

---

### 4. `cluster_lobbying_bills.py` — K-means topic clustering (manual/one-time)

This script is **not part of weekly CI**. Re-run it manually when the historical
corpus changes significantly (e.g., after the full 2005–2026 fetch completes).

**What it does:**

1. Loads all embeddings from the GCS Parquet.
2. L2-normalises the vectors (puts clustering in cosine space).
3. Runs k-means (`N_CLUSTERS=15`, `random_state=42`) to assign each bill to a topic cluster.
4. For each cluster, sends the 20 most central bill titles to **Gemini 2.5 Flash**
   and asks for a 3–5 word label.
5. Writes cluster IDs back to the Parquet and to `MA_lobbying_bills_scored.csv`.
6. Writes `MA_bill_cluster_labels.csv` with cluster ID, label, bill count, and
   environmental bill count.

**Flags:**

```bash
python cluster_lobbying_bills.py               # re-cluster + re-label
python cluster_lobbying_bills.py --relabel     # keep existing cluster IDs, only redo Gemini labels
python cluster_lobbying_bills.py --n-clusters 20  # change number of clusters
```

**Current clusters (2024 data, 15 clusters):**

The two most environment-dense clusters are:
- Cluster 11 "Health, Climate, and Community" (155/172 = 90% environmental)
- Cluster 13 "Legislative Modernization and Reform" (166/248 = 67% environmental)

No cluster is purely environmental — `is_environmental` is an individual bill
property (from scoring), not a cluster property. Cluster labels reflect the dominant
topic across all bills in the cluster, which dilutes the environmental signal in
mixed clusters.

---

## Other scripts (manual / not in CI)

| Script | Purpose | When to run |
|--------|---------|-------------|
| `get_DEP_staff.py` | Older DEP staffing data | One-time; superseded by SODA |
| `get_Census_ACS.py` | ACS demographic data | Manually as needed |
| `get_Census_statepop.py` | State population | Manually as needed |
| `get_ECOS_data.py` | ECOS per-capita budget survey | When ECOS publishes a new report (~every 3–5 years) |
| `get_SSAWages.py` | SSA Average Wage Index | Currently blocked (ssa.gov 403); fallback CSV is used |
| `transform_*.py` | One-time data transforms | Already applied; do not re-run |
| `generate_semantic_context.py` | Regenerate AI Analysis context | Run after any DB schema change; auto-called by `assemble_db.py` |

---

## Credentials

| Secret | File | Used by |
|--------|------|---------|
| Google AI Studio API key | `SECRET_GOOGLE_API_KEY` | `score_lobbying_bills.py`, `cluster_lobbying_bills.py` |
| SODA app + secret token | `SECRET_SODA_token` (two lines) | `get_DEP_staff_SODA.py` |

Neither file is committed to the repo. In CI both are written from GitHub Secrets.
