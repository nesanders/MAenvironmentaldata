"""Generate plain-language summaries and taxonomy tags for MA lobbying bills
using a single Gemini structured-output call per bill.

Outputs feed into score_lobbying_bills.py (replaces raw title+body embeddings):
  - summary       → embedded instead of raw bill text
  - categories    → broad policy area (1–2 from 21-category MAPLE taxonomy)
  - tags          → specific policy tags (3–5 from category vocabulary)
  - is_env_llm    → direct LLM environmental classification (bool)

Prompt caching
──────────────
The taxonomy prefix (~1,300 tokens) is identical for every bill. This script
creates a Gemini context cache on the first call and reuses it for all subsequent
bills, paying $0.01875/1M for cached reads instead of $0.075/1M — a 4× saving
on the static portion. At 26k bills this saves roughly $2 (~30% of total cost).

Modes
─────
Default (incremental):
  Processes only bills where summary IS NULL in the parquet. Safe to re-run.

Pilot (--sample N):
  Process N bills stratified across General Courts.

  python summarize_lobbying_bills.py --sample 200

Reprocess (--reprocess):
  Ignore existing summaries; reprocess everything.

Outputs
───────
  gs://openamend-data/MA_bill_embeddings.parquet   — summary, categories, tags,
                                                     is_env_llm columns added
  ../docs/data/MA_bill_embeddings.parquet          — local copy

Cost (Gemini 2.5 Flash non-thinking, as of May 2026)
─────────────────────────────────────────────────────
  Uncached input:  $0.075  / 1M tokens
  Cached input:    $0.01875 / 1M tokens  (taxonomy prefix, ~1,300 tok)
  Output:          $0.300  / 1M tokens
  Thinking is explicitly disabled (budget=0).

  Estimated full run (26k bills):  ~$5–6 with caching  (~$7 without)

Run from the get_data/ directory:
    /path/to/python -u summarize_lobbying_bills.py --sample 200
"""

import argparse
import json
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd
from pydantic import BaseModel, field_validator

DATA_DIR      = Path('../docs/data')
API_KEY_PATH  = Path('SECRET_GOOGLE_API_KEY')
GCS_PARQUET   = 'gs://openamend-data/MA_bill_embeddings.parquet'
LOCAL_PARQUET = DATA_DIR / 'MA_bill_embeddings.parquet'

DEFAULT_MODEL   = 'gemini-2.5-flash'
DEFAULT_WORKERS = 8      # concurrent LLM+embed workers
EMBED_WORKERS   = 8      # concurrent embedding workers (separate pool)

# Rate-limit: non-thinking Flash is ~1000 RPM on paid tier.
# With 8 workers each doing ~1s of work, that's ~480 RPM — safely under.
# Embedding API is also ~1000 RPM.  No explicit sleep needed at 8 workers,
# but backoff handles burst errors.

# Pricing: Gemini 2.5 Flash ($/1M tokens)
PRICE_INPUT          = 0.075   / 1_000_000
PRICE_INPUT_CACHED   = 0.01875 / 1_000_000
PRICE_OUTPUT         = 0.300   / 1_000_000
PRICE_THINK          = 3.50    / 1_000_000   # thinking tokens (should be 0 with budget=0)
PRICE_EMBED          = 0.20    / 1_000_000   # gemini-embedding-2

# Truncate bill text to ~10k tokens (legal English ≈ 4 chars/token)
MAX_TEXT_CHARS = 40_000

# Minimum tokens for Gemini context cache
CACHE_MIN_TOKENS = 1_024

# Embedding model (same as score_lobbying_bills.py)
EMBEDDING_MODEL = 'gemini-embedding-2'
EMBEDDING_DIM   = 768


# ─── MAPLE taxonomy ────────────────────────────────────────────────────────────
# Source: github.com/codeforboston/maple  llm/tag_categories.py
# 21 categories, 172 tags.

TAXONOMY: dict[str, list[str]] = {
    "Commerce": [
        "Banking and financial institutions regulation",
        "Partnerships and Limited Liability Companies",
        "Non-Profit Law and Governance",
        "Consumer Protection",
        "Corporation Law and Governance",
        "Marketing and advertising",
        "Retail and wholesale trades",
        "Securities",
    ],
    "Crime and Law Enforcement": [
        "Assault and harassment offenses",
        "Crimes against animals and natural resources",
        "Crimes against children",
        "Property Crimes",
        "Criminal investigation, prosecution, interrogation",
        "Criminal justice information and records",
        "Criminal Sentencing",
        "Firearms and explosives",
        "Fraud offenses and financial crimes",
        "Correctional Facilities",
        "Criminal Justice Reform",
    ],
    "Economics and Public Finance": [
        "Budget process",
        "Debt collection",
        "Financial literacy",
        "Financial services and investments",
        "Labor-management relations",
        "Public contracts and procurement",
        "Pension and retirement benefits",
    ],
    "Education": [
        "Academic performance and assessments",
        "Adult education and literacy",
        "Educational facilities and institutions",
        "Elementary and secondary education",
        "Higher education",
        "Curriculum and standards",
        "Special education",
        "Student aid and college costs",
        "Teachers and educators",
        "Technology assessment",
        "Vocational and technical education",
    ],
    "Emergency Management": [
        "Disaster relief and insurance",
        "Emergency communications systems",
        "Emergency medical services and trauma care",
        "Emergency planning and evacuation",
        "Hazards and emergency operations",
    ],
    "Energy": [
        "Energy assistance",
        "Energy efficiency and conservation",
        "Energy prices",
        "Energy research",
        "Energy storage, supplies, demand",
        "Renewable energy sources",
    ],
    "Environmental Protection": [
        "Air quality",
        "Environmental assessment, monitoring, research",
        "Environmental education",
        "Environmental health",
        "Environmental regulatory procedures",
        "Hazardous wastes and toxic substances",
        "Pollution control and abatement",
        "Soil pollution",
        "Solid waste and recycling",
        "Water quality",
        "Wetlands",
    ],
    "Families": [
        "Adoption and foster care",
        "Family planning and birth control",
        "Family relationships and status",
        "Family services",
        "Parenting",
    ],
    "Government Operations and Politics": [
        "Census and government statistics",
        "Election administration",
        "Municipality Oversight",
        "Government information and archives",
        "Government studies and investigations",
        "Government trust funds",
        "Lobbying and campaign finance",
        "Political advertising",
        "Public-private cooperation",
    ],
    "Healthcare": [
        "Alternative treatments",
        "Telehealth",
        "Veterinary Services and Pets",
        "Dental care",
        "Health care costs",
        "Health insurance and coverage",
        "Health facilities and institutions",
        "Health information and medical records",
        "Health technology, devices, supplies",
        "Substance use disorder",
        "Healthcare workforce",
        "Medical research",
        "Mental health",
        "Prescription drugs",
        "Sex and reproductive health",
    ],
    "Food, Drugs and Alcohol": [
        "Alcoholic beverages and licenses",
        "Drug, alcohol, tobacco use",
        "Food industry and services",
        "Food supply, safety, and labeling",
        "Nutrition and diet",
        "Food service employment",
        "Drug safety, medical device, and laboratory regulation",
    ],
    "Housing and Community Development": [
        "Community life and organization",
        "Cooperative and condominium housing",
        "Homelessness and emergency shelter",
        "Housing discrimination",
        "Housing finance and home ownership",
        "Housing for the elderly and disabled",
        "Housing industry and standards",
        "Housing supply and affordability",
        "Landlord and tenant",
        "Low- and moderate-income housing",
        "Residential rehabilitation and home repair",
    ],
    "Immigrants and Foreign Nationals": [
        "Immigrant health and welfare",
        "Translation and language services",
        "Refugees, asylum, displaced persons",
        "Right to shelter",
    ],
    "Labor and Employment": [
        "Employee benefits",
        "Employee pensions",
        "Employee leave",
        "Employee performance",
        "Employment and training programs",
        "Employment discrimination",
        "Migrant, seasonal, agricultural labor",
        "Self-employment",
        "Temporary and part-time employment",
        "Workers' compensation",
        "Worker safety and health",
        "Youth employment and child labor",
    ],
    "Law and Judiciary": [
        "Administrative remedies",
        "Civil actions and liability",
        "Civil disturbances",
        "Evidence and witnesses",
        "Judicial administration",
        "Judicial review and appeals",
        "Jurisdiction and venue",
        "Legal fees and court costs",
        "Property rights",
    ],
    "Public and Natural Resources": [
        "Forests, forestry, trees",
        "Eminent domain",
        "Marine and coastal resources, fisheries",
        "Marine pollution",
        "Monuments and memorials",
        "Water resources",
        "Wilderness",
    ],
    "Science, Technology, Communications": [
        "Advanced technology and technological innovations",
        "Atmospheric science and weather",
        "Computer security and identity theft",
        "Computers and information technology",
        "Genetics",
        "Internet, web applications, social media",
        "Photography and imaging",
        "Telecommunication rates and fees",
        "Telephone and wireless communication",
    ],
    "Social Services": [
        "Child care and development",
        "Domestic violence and child abuse",
        "Food assistance and relief",
        "Home and outpatient care",
        "Social work, volunteer service, charitable organizations",
        "Unemployment",
        "Urban and suburban affairs and development",
        "Veterans' education, employment, rehabilitation",
        "Veterans' loans, housing, homeless programs",
        "Veterans' medical care",
    ],
    "Sports and Recreation": [
        "Art and culture",
        "Hunting and fishing",
        "Outdoor recreation",
        "Public parks",
        "Gambling and lottery",
        "Professional sports, stadiums and arenas",
        "Sports and recreation facilities",
    ],
    "Taxation": [
        "Capital gains tax",
        "Corporate tax",
        "Estate tax",
        "Excise tax",
        "Gift tax",
        "Income tax",
        "Payroll and employment tax",
        "Property tax",
        "Sales tax",
        "Transfer and inheritance taxes",
        "Tax-exempt organizations",
    ],
    "Transportation and Public Works": [
        "Aviation and airports",
        "Highways and roads",
        "Maritime affairs and fisheries",
        "MBTA & Public Transportation",
        "Public utilities and utility rates",
        "Railroads",
        "Water storage",
        "Water use and supply",
    ],
}

ALL_TAGS: set[str]       = {tag for tags in TAXONOMY.values() for tag in tags}
ALL_CATEGORIES: set[str] = set(TAXONOMY.keys())


# ─── Pydantic schema ───────────────────────────────────────────────────────────

class BillAnalysis(BaseModel):
    """Structured LLM output for a single MA legislative bill."""

    summary: str
    categories: List[str]
    tags: List[str]
    is_environmental: bool

    @field_validator('categories')
    @classmethod
    def validate_categories(cls, v: List[str]) -> List[str]:
        """Keep only recognised category names; cap at 2."""
        return [c for c in v if c in ALL_CATEGORIES][:2]

    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        """Keep only recognised tag names; cap at 5."""
        return [t for t in v if t in ALL_TAGS][:5]


# ─── Prompt construction ───────────────────────────────────────────────────────

def _taxonomy_block() -> str:
    lines = []
    for cat, tags in TAXONOMY.items():
        lines.append(f"  {cat}:")
        for tag in tags:
            lines.append(f"    - {tag}")
    return '\n'.join(lines)


# Static prefix — cached across all bills (taxonomy + instructions, ~1,300 tokens)
STATIC_PROMPT_PREFIX = f"""You are a Massachusetts legislative analyst. \
For each bill you receive, return a JSON object with exactly these four fields:

"summary": 2–4 sentences in plain language explaining what this bill would do \
if passed. Write for a general audience. Describe the real-world policy intent \
and impact. Do NOT cite MGL section numbers, chapter names, or bill titles. Use \
conditional language ("would", "if passed"). Be politically neutral.

"categories": Choose 1–2 category names from the TAXONOMY below that best \
describe this bill's primary policy area(s). Use EXACT category names only.

"tags": Choose 3–5 tag names from the tags listed under your chosen categories \
ONLY. Do not use tags from other categories. Use EXACT tag names only.

"is_environmental": true if this bill primarily concerns any of the following — \
environmental protection, air/water/soil quality, wetlands, pollution, hazardous \
waste, solid waste or recycling, clean energy or renewable energy, energy \
efficiency, climate change, carbon emissions, natural resources, forests, \
fisheries, marine resources, or wildlife. Be inclusive: a bill about expanding \
bottle deposits, restricting natural gas, requiring EV charging, or regulating \
PFAS is environmental. A bill about road construction or hospital staffing is not.

TAXONOMY:
{_taxonomy_block()}
"""


def _build_dynamic_prompt(title: str, full_text: str) -> str:
    """Per-bill portion: title and truncated body text."""
    text = (full_text or '').strip()[:MAX_TEXT_CHARS]
    if not text:
        text = f'[No body text — title only: {title}]'
    return f"BILL TITLE: {title}\nBILL TEXT (boilerplate removed):\n{text}"


# ─── GCS helpers ───────────────────────────────────────────────────────────────

def _gcs_fs():
    import gcsfs
    return gcsfs.GCSFileSystem()


def _load_parquet() -> pd.DataFrame:
    """Load embeddings parquet from GCS, falling back to local copy."""
    try:
        fs = _gcs_fs()
        if fs.exists(GCS_PARQUET):
            with fs.open(GCS_PARQUET, 'rb') as f:
                df = pd.read_parquet(f)
            print(f'Loaded {len(df)} rows from {GCS_PARQUET}')
            return df
    except OSError as e:
        print(f'GCS load failed ({e}), trying local...')
    if LOCAL_PARQUET.exists():
        df = pd.read_parquet(LOCAL_PARQUET)
        print(f'Loaded {len(df)} rows from local parquet')
        return df
    raise FileNotFoundError('No parquet found. Run score_lobbying_bills.py first.')


def _save_parquet(df: pd.DataFrame) -> None:
    """Write parquet to local path and GCS."""
    df.to_parquet(LOCAL_PARQUET, index=False)
    try:
        fs = _gcs_fs()
        with fs.open(GCS_PARQUET, 'wb') as f:
            df.to_parquet(f, index=False)
        print(f'  → Saved to {GCS_PARQUET}')
    except OSError as e:
        print(f'  → GCS save failed: {e} — local copy at {LOCAL_PARQUET}')


# ─── Prompt cache management ───────────────────────────────────────────────────

def _create_cache(client, model: str):
    """Create a Gemini context cache for the static taxonomy prefix."""
    import google.genai.types as types
    try:
        cache = client.caches.create(
            model=model,
            config=types.CreateCachedContentConfig(
                contents=[
                    types.Content(
                        role='user',
                        parts=[types.Part(text=STATIC_PROMPT_PREFIX)],
                    )
                ],
                ttl='7200s',
                display_name='MA_bill_taxonomy_v1',
            ),
        )
        print(f'Created context cache: {cache.name}  (TTL 2h)')
        return cache
    except OSError as e:
        print(f'Cache creation failed ({e}) — will send full prompt each call')
        return None


# ─── LLM call ──────────────────────────────────────────────────────────────────

def _call_gemini(
    client, model: str, dynamic_prompt: str, cache
) -> tuple['BillAnalysis | None', int, int, int]:
    """Single structured-output call with exponential backoff.

    Returns (result, input_tokens, cached_tokens, output_tokens).
    Tokens are 0 on failure.  Retries up to 6 times on transient errors
    (429 rate-limit, 503 unavailable) with jitter.
    """
    import random
    import google.genai.types as types

    gen_config = types.GenerateContentConfig(
        response_mime_type='application/json',
        response_schema=BillAnalysis,
        temperature=0,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )
    if cache is not None:
        gen_config.cached_content = cache.name

    contents = dynamic_prompt if cache is not None else (
        STATIC_PROMPT_PREFIX + '\n\n' + dynamic_prompt
    )

    for attempt in range(6):
        try:
            resp = client.models.generate_content(
                model=model, contents=contents, config=gen_config,
            )
            usage        = resp.usage_metadata
            in_tok       = getattr(usage, 'prompt_token_count', 0) or 0
            cached_tok   = getattr(usage, 'cached_content_token_count', 0) or 0
            out_tok      = getattr(usage, 'candidates_token_count', 0) or 0
            think_tok    = getattr(usage, 'thoughts_token_count', 0) or 0
            if think_tok:
                print(f'    ⚠️  thinking tokens: {think_tok}')
            return resp.parsed, in_tok, cached_tok, out_tok, think_tok
        except (ValueError, AttributeError) as e:
            print(f'    Gemini parse error: {e}')
            return None, 0, 0, 0
        except Exception as e:
            msg = str(e)
            if attempt == 5:
                print(f'    Gemini failed after 6 attempts: {e}')
                return None, 0, 0, 0
            # Exponential backoff with jitter for rate limits / transient errors
            wait = (2 ** attempt) + random.uniform(0, 1)
            print(f'    Gemini error (attempt {attempt+1}/6): {msg[:80]} — retry in {wait:.1f}s')
            time.sleep(wait)
    return None, 0, 0, 0, 0


def _embed_summary(client, summary: str) -> 'np.ndarray | None':
    """Embed a single summary string; returns (768,) float32 or None on failure."""
    import random
    import google.genai.types as types
    for attempt in range(6):
        try:
            resp = client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=summary,
                config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
            )
            return np.array(resp.embeddings[0].values, dtype=np.float32)
        except Exception as e:
            if attempt == 5:
                print(f'    Embed failed after 6 attempts: {e}')
                return None
            wait = (2 ** attempt) + random.uniform(0, 1)
            print(f'    Embed error (attempt {attempt+1}/6): {str(e)[:80]} — retry in {wait:.1f}s')
            time.sleep(wait)
    return None


# ─── Sampling ──────────────────────────────────────────────────────────────────

def _stratified_sample(df: pd.DataFrame, n: int) -> pd.DataFrame:
    """Sample n bills spread uniformly across General Courts."""
    gcs    = sorted(df['general_court'].dropna().unique())
    per_gc = max(1, n // len(gcs))
    parts  = [
        df[df['general_court'] == gc].sample(
            n=min(per_gc, (df['general_court'] == gc).sum()), random_state=42
        )
        for gc in gcs
    ]
    return pd.concat(parts).sample(frac=1, random_state=42).iloc[:n]


# ─── Worker ────────────────────────────────────────────────────────────────────

def _process_one(
    client, model: str, cache,
    idx, title: str, full_text: str, gc: int, bill_no: str,
    embed_summaries: bool,
) -> dict:
    """Process a single bill: LLM call + optional summary embedding.

    Returns a result dict with keys: idx, ok, result, in_tok, cached_tok,
    out_tok, summ_emb, gc, bill_no, title.
    """
    dynamic = _build_dynamic_prompt(title, full_text)
    result, in_tok, cached_tok, out_tok, think_tok = _call_gemini(client, model, dynamic, cache)

    summ_emb = None
    if result is not None and embed_summaries and result.summary:
        summ_emb = _embed_summary(client, result.summary)

    return dict(
        idx=idx, ok=(result is not None), result=result,
        in_tok=in_tok, cached_tok=cached_tok, out_tok=out_tok, think_tok=think_tok,
        summ_emb=summ_emb, gc=gc, bill_no=bill_no, title=title,
    )


# ─── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sample', type=int, default=None,
                        help='Process N bills stratified across General Courts')
    parser.add_argument('--model', default=DEFAULT_MODEL)
    parser.add_argument('--reprocess', action='store_true',
                        help='Re-run bills that already have summaries')
    parser.add_argument('--workers', type=int, default=DEFAULT_WORKERS,
                        help=f'Parallel worker threads (default {DEFAULT_WORKERS})')
    parser.add_argument('--embed-summaries', action='store_true', default=True,
                        help='Embed each summary inline and store as summary_embedding')
    parser.add_argument('--no-embed-summaries', dest='embed_summaries',
                        action='store_false',
                        help='Skip summary embedding (faster, cheaper)')
    args = parser.parse_args()

    api_key = API_KEY_PATH.read_text(encoding='utf-8').strip()
    import google.genai as genai
    client = genai.Client(api_key=api_key)

    df = _load_parquet()

    for col in ('summary', 'categories', 'tags', 'is_env_llm', 'summary_embedding'):
        if col not in df.columns:
            df[col] = None

    if args.reprocess:
        todo = df[df['bill_title'].notna()].copy()
    else:
        todo = df[df['summary'].isna() & df['bill_title'].notna()].copy()

    if args.sample:
        todo = _stratified_sample(todo, args.sample)

    print(f'Model:            {args.model}')
    print(f'Bills to process: {len(todo)}')
    print(f'Already done:     {df["summary"].notna().sum()}')
    print(f'Workers:          {args.workers}')
    print(f'Embed summaries:  {args.embed_summaries}')
    print(f'Taxonomy:         {len(TAXONOMY)} categories, {len(ALL_TAGS)} tags')

    cache = _create_cache(client, args.model)
    print()

    # Thread-safe counters and lock for df writes + console output
    lock              = threading.Lock()
    total_in          = 0
    total_cached      = 0
    total_out         = 0
    total_think       = 0
    total_embed_tok   = 0
    n_ok              = 0
    n_fail            = 0
    completed         = 0

    rows = list(todo.iterrows())
    n_total = len(rows)

    def _running_cost() -> float:
        return (
            (total_in - total_cached) * PRICE_INPUT
            + total_cached * PRICE_INPUT_CACHED
            + total_out * PRICE_OUTPUT
            + total_think * PRICE_THINK
            + total_embed_tok * PRICE_EMBED
        )

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                _process_one,
                client, args.model, cache,
                idx,
                str(row.get('bill_title', '') or ''),
                str(row.get('full_text', '') or ''),
                int(row['general_court']) if pd.notna(row.get('general_court')) else 0,
                str(row.get('bill_number', '?')),
                args.embed_summaries,
            ): idx
            for idx, row in rows
        }

        for future in as_completed(futures):
            r = future.result()
            with lock:
                completed += 1
                total_in     += r['in_tok']
                total_cached += r['cached_tok']
                total_out    += r['out_tok']
                total_think  += r['think_tok']
                if r['summ_emb'] is not None:
                    total_embed_tok += len(r['result'].summary.split()) * 4 // 3 if r['result'] else 0

                if not r['ok']:
                    n_fail += 1
                    print(f'  [{completed:>4}/{n_total}] FAIL  '
                          f'GC{r["gc"]} {r["bill_no"]} — {r["title"][:55]}')
                else:
                    n_ok += 1
                    result   = r['result']
                    df.at[r['idx'], 'summary']    = result.summary
                    df.at[r['idx'], 'categories'] = json.dumps(result.categories)
                    df.at[r['idx'], 'tags']       = json.dumps(result.tags)
                    df.at[r['idx'], 'is_env_llm'] = result.is_environmental
                    if r['summ_emb'] is not None:
                        df.at[r['idx'], 'summary_embedding'] = r['summ_emb'].tolist()

                    env_flag = '🌿' if result.is_environmental else '  '
                    cats_str = ', '.join(result.categories)
                    tags_str = ', '.join(result.tags[:3]) + ('…' if len(result.tags) > 3 else '')
                    print(
                        f'  [{completed:>4}/{n_total}] {env_flag} GC{r["gc"]} {r["bill_no"]} '
                        f'[{r["in_tok"]}in/{r["cached_tok"]}cached/{r["out_tok"]}out] '
                        f'${_running_cost():.4f} | {cats_str}'
                    )
                    print(f'          tags: {tags_str}')
                    print(f'          "{r["title"][:70]}"')

                if completed % 50 == 0:
                    _print_checkpoint(completed, n_ok, n_fail,
                                      total_in, total_cached, total_out)
                    _save_parquet(df)

    _save_parquet(df)
    _print_final_summary(df, todo, n_ok, n_fail,
                         total_in, total_cached, total_out, total_think, total_embed_tok)


def _print_checkpoint(i: int, n_ok: int, n_fail: int,
                      total_in: int, total_cached: int, total_out: int,
                      total_think: int = 0, total_embed_tok: int = 0) -> None:
    """Print a mid-run progress line."""
    cost = (
        (total_in - total_cached) * PRICE_INPUT
        + total_cached * PRICE_INPUT_CACHED
        + total_out * PRICE_OUTPUT
        + total_think * PRICE_THINK
        + total_embed_tok * PRICE_EMBED
    )
    think_note = f' | think={total_think:,}' if total_think else ''
    print(
        f'\n  ── checkpoint {i}: {n_ok} ok / {n_fail} fail | '
        f'{total_in:,} in ({total_cached:,} cached) / {total_out:,} out{think_note} | '
        f'${cost:.4f} ──\n'
    )


def _print_final_summary(df: pd.DataFrame, todo: pd.DataFrame,
                         n_ok: int, n_fail: int,
                         total_in: int, total_cached: int, total_out: int,
                         total_think: int = 0, total_embed_tok: int = 0) -> None:
    """Print token counts, cost breakdown, and env classification comparison."""
    uncached      = total_in - total_cached
    llm_cost      = (uncached * PRICE_INPUT + total_cached * PRICE_INPUT_CACHED
                     + total_out * PRICE_OUTPUT)
    think_cost    = total_think * PRICE_THINK
    embed_cost    = total_embed_tok * PRICE_EMBED
    cost          = llm_cost + think_cost + embed_cost
    cost_no_cache = total_in * PRICE_INPUT + total_out * PRICE_OUTPUT + think_cost + embed_cost
    avg_in        = total_in  / max(n_ok, 1)
    avg_out       = total_out / max(n_ok, 1)

    print(f'\n{"─"*65}')
    print(f'Done: {n_ok} processed, {n_fail} failed')
    print(f'Tokens:  {total_in:,} input  ({total_cached:,} cached, {uncached:,} uncached)')
    print(f'         {avg_in:.0f} avg input / bill  |  {avg_out:.0f} avg output / bill')
    if total_think:
        print(f'         {total_think:,} thinking tokens  ← ⚠️  budget=0 not respected!')
    print(f'Cost:    ${llm_cost:.4f} LLM  +  ${think_cost:.4f} thinking  '
          f'+  ${embed_cost:.4f} embed  =  ${cost:.4f} total')
    print(f'         (vs ${cost_no_cache:.4f} without caching, saved ${cost_no_cache - cost:.4f})')
    print(f'         ${cost / max(n_ok, 1) * 1000:.4f} per 1,000 bills')
    print(f'         ${cost / max(n_ok, 1) * 26_000:.2f} projected for 26k full corpus')
    print(f'{"─"*65}')

    if n_ok == 0:
        return

    done_mask = df.loc[todo.index, 'summary'].notna()
    done      = df.loc[todo.index[done_mask]]
    n_env_llm = int(done['is_env_llm'].sum())
    n_env_emb = int(done['is_environmental'].fillna(0).astype(int).sum()) \
        if 'is_environmental' in df.columns else -1

    print(f'\nEnv classification ({len(done)} bills):')
    print(f'  LLM (is_env_llm):          {n_env_llm} ({100*n_env_llm/len(done):.1f}%)')
    if n_env_emb >= 0:
        print(f'  Embedding (is_environmental): {n_env_emb} ({100*n_env_emb/len(done):.1f}%)')

    cat_counts: Counter = Counter()
    for v in done['categories'].dropna():
        try:
            cat_counts.update(json.loads(v))
        except (json.JSONDecodeError, TypeError):
            pass
    print('\nTop categories in sample:')
    for cat, cnt in cat_counts.most_common(8):
        print(f'  {cnt:>4}  {cat}')


if __name__ == '__main__':
    main()
