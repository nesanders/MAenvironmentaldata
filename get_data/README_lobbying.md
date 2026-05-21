# MA Lobbying pipeline

Tracks which bills are being lobbied in the Massachusetts legislature, how much is
spent, and whether those bills are environmentally relevant. Four scripts, the first
three of which run in weekly CI:

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

All scripts must be run from `get_data/`. Use the `amend_python` conda env, and run
Python directly (not `conda run`) for live log output:

```bash
/home/nes/miniconda/envs/amend_python/bin/python -u <script>.py
```

---

## 1. `get_MA_lobbying.py` — Scrape the SoS lobbying portal

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
- If no new disclosure URLs are found, the script exits immediately without writing files.

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

## 2. `get_MA_legislature_bills.py` — Fetch bill metadata from the Legislature API

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

Raw JSON responses are cached as `MA_legislature_cache/{key}.json` (gitignored). The
merged output CSV is flushed every 50 bills, so an interrupted run loses at most 50
bills' worth of API calls.

**Output:** `MA_legislature_bills.csv` — bill_id, bill_number, general_court, title,
sponsor_name, status, passed.

The full-text bill content stored in the JSON cache is used by `score_lobbying_bills.py`
to embed bill text rather than just titles.

---

## 3. `score_lobbying_bills.py` — Gemini embeddings + environmental scoring

**Requires:** `SECRET_GOOGLE_API_KEY` file in `get_data/` (Google AI Studio key with
access to `gemini-embedding-2`; not committed to repo).

**SDK:** Uses `google-genai` (new SDK), **not** `google-generativeai`:

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

For each bill, the script reads the first 2,000 characters of full bill text from
`MA_legislature_cache/`. If no cached JSON exists (~3% of bills), it falls back to
the bill title. Full text dramatically improves discrimination — titles are often
generic legislative boilerplate.

**Incremental operation:**

The Parquet file on GCS (`gs://openamend-data/MA_bill_embeddings.parquet`) is the
authoritative store of all embeddings. Bills already in the Parquet are skipped each
run; only new bills are embedded. Weekly CI typically embeds zero or a handful.

**Environmental scoring — differential cosine similarity:**

Rather than scoring against seed phrases (which compress all scores into a narrow
range), the script uses two reference sets of 20 real MA bills each:

- `ENV_EXAMPLE_BILLS` — 20 actual environmental bills (PFAS, stormwater, clean energy, etc.)
- `NON_ENV_EXAMPLE_BILLS` — 20 actual non-environmental bills (health, labor, education, etc.)

For each bill:

```
env_score     = max cosine similarity to any ENV_EXAMPLE_BILLS embedding
non_env_score = max cosine similarity to any NON_ENV_EXAMPLE_BILLS embedding
differential  = env_score - non_env_score
is_environmental = (differential > 0.05)
```

This anchors scoring to real legislative language and discriminates between
superficially similar bills (e.g. public health vs. environmental health).

**Storage:**

| Location | Contents | Committed? |
|----------|----------|------------|
| `gs://openamend-data/MA_bill_embeddings.parquet` | 768-dim embeddings + full text + scores + cluster_ids | No (~100 MB) |
| `docs/data/MA_lobbying_bills_scored.csv` | Scores + cluster_ids only, no embeddings | Yes (~300 KB) |

**Cost:** ~$0.008/1,000 bills. The 2024 corpus of 2,648 bills cost ~$0.02.

---

## 4. `cluster_lobbying_bills.py` — K-means topic clustering (manual/one-time)

Not part of weekly CI. Re-run manually when the historical corpus changes significantly
(e.g. after the full 2005–2026 fetch completes).

**What it does:**

1. Loads all embeddings from the GCS Parquet.
2. L2-normalises the vectors (cosine-space clustering).
3. Runs k-means (`N_CLUSTERS=15`, `random_state=42`) to assign each bill a topic cluster.
4. Sends the 20 most central bill titles per cluster to **Gemini 2.5 Flash** for a
   3–5 word label.
5. Writes cluster IDs back to the Parquet and `MA_lobbying_bills_scored.csv`.
6. Writes `MA_bill_cluster_labels.csv` (cluster_id, label, n_bills, n_env_bills).

**Flags:**

```bash
python cluster_lobbying_bills.py                  # re-cluster + re-label
python cluster_lobbying_bills.py --relabel        # keep cluster IDs, only redo labels
python cluster_lobbying_bills.py --n-clusters 20  # change cluster count
```

**Important:** No cluster is purely environmental — `is_environmental` is an
individual bill property derived from scoring, not a cluster property. Cluster labels
reflect the dominant topic across all bills in the cluster, which dilutes the
environmental signal in mixed clusters.
