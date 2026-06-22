# MA Lobbying pipeline

Tracks which bills are being lobbied in the Massachusetts legislature, how much is
spent, and whether those bills are environmentally relevant. Five scripts; the first
four run in weekly CI:

```
get_MA_lobbying.py
    ↓ MA_lobbying_employers.csv, MA_lobbying_bills.csv, MA_lobbying_summary_links.csv
get_MA_legislature_bills.py
    ↓ MA_legislature_bills.csv  +  MA_legislature_cache/<bill>.json
score_lobbying_bills.py
    ↓ MA_lobbying_bills_scored.csv  +  gs://openamend-data/MA_bill_embeddings.parquet
cluster_lobbying_bills.py --incremental   ← weekly CI (incremental mode only)
    ↓ cluster_id column written back to scored CSV
summarize_lobbying_bills.py               ← manual only (too slow/expensive for CI)
    ↓ summary, category, tags, llm_is_environmental columns in parquet
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

**Incremental strategy (filing-window aware):**

MA lobbying has two semi-annual disclosure periods per year — H1 (Jan–Jun, due
~Jul 15) and H2 (Jul–Dec, due **~Jan 15 of the following year**) — and amendments
cluster within ~60 days of those deadlines (~11% of registrant-years have more
than 2 disclosure URLs).

State is persisted in `MA_lobbying_summary_links.csv` (gitignored; the script
syncs it to/from `gs://openamend-data` at startup and during the run):
- Every visited summary page is stamped with a `last_checked` date. Pages with
  no disclosures yet get a marker row with a null `disc_url`.
- A page is re-checked only while a filing window for its year is open
  (`deadline − 14d` → `deadline + 60d`), plus exactly one closing sweep after
  the window ends. Once both windows have closed and been swept, the page is
  never fetched again.
- A year is skipped entirely before Jul 1 of that year — the H1 period has not
  closed, so no disclosures can exist.
- Already-fetched `disc_url`s are never re-downloaded; appends are deduplicated.

Expected CI runtimes: ~1–2 min steady-state; ~40 min during the Jul 15 and
Jan 15 filing windows (full ~1,700-page scans, weekly until the window closes).

State is uploaded to GCS every 200 pages and at the end of the run — data files
first, the links index last — so a timed-out run still makes durable progress
and can never mark a disclosure "fetched" whose data didn't make it to GCS.

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

For each bill, the script constructs an embed string:
1. Strip legislative scaffolding (`_SCAFFOLD_RE`) from the body — the "Chapter X of
   the General Laws is hereby amended by inserting after…" boilerplate present in
   thousands of bills.
2. Prepend the SoS portal bill title (always available and topic-specific).
3. Truncate to 3,000 characters (~750 tokens).
4. Fall back to title alone when no cached body text exists (~3% of bills).

**Incremental operation:**

The Parquet file on GCS (`gs://openamend-data/MA_bill_embeddings.parquet`) is the
authoritative store of all embeddings. Bills already in the Parquet (matched by
`bill_id` + `general_court`, or by `bill_number` + `general_court` for legacy bills
without a chamber prefix) are skipped. Weekly CI typically embeds zero or a handful
of new bills.

**H/S deduplication (critical):**

H1234 and S1234 in the same General Court are **completely different bills** — House
and Senate bill numbers are assigned independently. The script derives a
chamber-prefixed `bill_id` (e.g. `H1234`, `S1234`) from the `chamber` column before
deduplicating, so both bills are embedded separately. Using `bill_number` alone to
deduplicate silently discards one of every H/S pair — a bug that was present in earlier
versions and caused ~23% of bills to be missing embeddings.

**Environmental scoring — differential cosine similarity:**

Rather than scoring against seed phrases (which compress all scores into a narrow
range), the script uses two reference sets of real MA bills:

- `ENV_EXAMPLE_BILLS` — known environmental bills (PFAS, stormwater, clean energy, etc.)
- `NON_ENV_EXAMPLE_BILLS` — known non-environmental bills (health, labor, education, etc.)

For each bill:

```
env_score     = max cosine similarity to any ENV_EXAMPLE_BILLS embedding
non_env_score = max cosine similarity to any NON_ENV_EXAMPLE_BILLS embedding
differential  = env_score - non_env_score
is_environmental = (differential > 0.05)
```

This anchors scoring to real legislative language and discriminates between
superficially similar bills (e.g. public health vs. environmental health).

**Current corpus (June 2026):** 33,159 bills embedded; 924 flagged `is_environmental`
(2.8% of corpus).

**Storage:**

| Location | Contents | Committed? |
|----------|----------|------------|
| `gs://openamend-data/MA_bill_embeddings.parquet` | 768-dim embeddings + full text + scores + cluster_ids + summaries/tags | No (~200 MB) |
| `docs/data/MA_lobbying_bills_scored.csv` | Scores + cluster_ids only, no embeddings | Yes (~4 MB) |

**Cost:** ~$0.00015/bill ($0.15/1k bills) for `gemini-embedding-2` at $0.20/1M tokens
with ~750 tokens/bill. Typical weekly CI run embeds 0–50 new bills; cost < $0.01/week.
See `NOTES_bill_embeddings.md` for full cost history.

---

## 4. `cluster_lobbying_bills.py` — K-means topic clustering

**Two modes:**

**Incremental (weekly CI):** Loads the saved k-means model from GCS and assigns
cluster IDs to any bill with `cluster_id == -1` (newly embedded). No Gemini calls,
no re-fitting — nearest-centroid lookup only.

```bash
python cluster_lobbying_bills.py --incremental
```

**Full re-cluster (manual):** Re-fits k-means on all valid embeddings, generates new
Gemini 2.5 Flash topic labels from the 20 most central bill titles per cluster, and
saves the updated model to GCS. Run manually when the corpus has grown substantially
(e.g. after adding a new General Court's worth of bills).

```bash
python cluster_lobbying_bills.py [--n-clusters N] [--no-label] [--relabel]
```

**Configuration:** k=25 clusters, chosen on domain grounds (produces ~1,000
bills/cluster, yields coherent topic labels). The silhouette curve is completely flat
across k=4..40 with no elbow — see `NOTES_bill_embeddings.md` for the sweep data.
Mean-centering before L2 normalisation gives a small consistent improvement.

**Important:** No cluster is purely environmental — `is_environmental` is an individual
bill property derived from embedding-based scoring and LLM classification (see §5),
not a cluster property. Cluster labels reflect the dominant topic across all bills in
the cluster.

---

## 5. `summarize_lobbying_bills.py` — LLM summary + taxonomy tagging

**Manual only — not in weekly CI.** Run after major corpus additions (new General Court,
backfill of historical sessions).

**Requires:** `SECRET_GOOGLE_API_KEY` with access to `gemini-2.5-flash`.

**What it does:**

For each bill not yet summarized in the Parquet, calls Gemini 2.5 Flash with:
- A static taxonomy prompt (~1,300 tokens, cached across all bills)
- The bill title + up to 40,000 characters of body text

Returns structured JSON:
- `summary` — 2–3 sentence plain-English description of what the bill would do
- `category` — top-level policy domain (e.g. "Healthcare", "Environmental Protection")
- `tags` — 2–5 specific policy tags from a fixed 200-tag taxonomy
- `llm_is_environmental` — boolean, LLM's direct environmental relevance judgment
- `llm_env_reason` — one-sentence justification

**LLM classification performance (reference set check):**

| Metric | Value |
|--------|-------|
| Recall on 20 known-env titles | 100% (20/20) |
| Specificity on 36 known-non-env | 97% (35/36) |

The LLM catches many embedding false negatives (bills like "An Act to expand the
bottle bill" that score below the 0.05 threshold but are clearly environmental).

**Context caching:** The static taxonomy prefix is cached via the Gemini context cache
API (~1,602 cached tokens/bill at $0.075/1M vs $0.30/1M uncached). Cache hit rate ~81%.

**Parallelism:** 8 concurrent workers. Checkpoints every 200 bills.

**Cost (verified June 2026):**

| Metric | Value |
|--------|-------|
| Actual rate | **$0.627 / 1k bills** |
| 7,211-bill backfill (June 2026) | $4.62 actual |
| Weekly incremental (20–50 bills) | ~$0.01–$0.03 |

Output tokens ($2.50/1M) account for ~60% of cost even at ~151 tokens/bill. See
`NOTES_bill_embeddings.md` for full cost history and the detailed breakdown of why
prior estimates were off by ~6×.

**Crash recovery:** If interrupted, re-run the same command. The Parquet is updated
incrementally; already-summarized bills are skipped. `recover_from_log.py` can
reconstruct partial results from a log file if the Parquet write was not flushed.
