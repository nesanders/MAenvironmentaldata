"""Score MA lobbying bills for environmental relevance using Gemini embeddings.

Storage model
─────────────
All bill text + embeddings are stored in a single Parquet file on GCS:
  gs://openamend-data/MA_bill_embeddings.parquet

Schema:
  bill_id          str   — chamber-prefixed ID (e.g. H4999); None for bills
                           without a legislature entry
  bill_number      int
  general_court    int
  bill_title       str   — from SoS portal (always available)
  full_text        str   — from MA Legislature API (empty if not available)
  embedding        list[float32]  — 768-dim Gemini embedding
  env_relevance_score  float  — differential cosine score (env - non_env)
  is_environmental bool
  cluster_id       int   — -1 until cluster_lobbying_bills.py is run

Incremental: only bills not already in the Parquet file are embedded each run.
Full text is read from the MA_legislature_cache/ JSON files written by
get_MA_legislature_bills.py (no extra API calls needed).

Scoring method
──────────────
Differential cosine similarity: for each bill, compute
  max cosine similarity to ENV_EXAMPLE_BILLS
  minus
  max cosine similarity to NON_ENV_EXAMPLE_BILLS
Positive scores indicate the bill looks more like environmental legislation
than non-environmental legislation. Threshold: 0.05.

Run from the get_data/ directory after get_MA_legislature_bills.py:
    /path/to/python -u score_lobbying_bills.py

Outputs:
  gs://openamend-data/MA_bill_embeddings.parquet  (uploaded)
  ../docs/data/MA_lobbying_bills_scored.csv       (local, committed to repo;
      lightweight: bill_id, bill_number, general_court, bill_title,
      env_relevance_score, is_environmental, cluster_id only — no embeddings)
"""

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path('../docs/data')
CACHE_DIR = Path('MA_legislature_cache')
API_KEY_PATH = Path('SECRET_GOOGLE_API_KEY')
GCS_PARQUET = 'gs://openamend-data/MA_bill_embeddings.parquet'
LOCAL_PARQUET = DATA_DIR / 'MA_bill_embeddings.parquet'  # local fallback/cache

ENV_THRESHOLD = 0.06
EMBEDDING_DIM = 768
REQUEST_DELAY = 0.05

# Full-text truncation: first N chars of bill text (avoids 8192-token limit on
# very long bills; ~2000 chars ≈ 500 tokens, well within model limit)
MAX_TEXT_CHARS = 2000

ENV_EXAMPLE_BILLS = [
    'An Act to protect Massachusetts public health from PFAS',
    'An Act relative to solid waste disposal facilities in environmental justice communities',
    'An Act relative to the remediation of home heating oil releases',
    'An Act relative to the cleanup of accidental home heating oil spills',
    'An Act relative to proper disposal of products containing PFAS',
    'An Act relative to certain manufactured chemicals known as PFAS',
    'An Act relative to chemical recycling',
    'An Act ensuring a healthy future for environmental justice communities',
    'An Act relative to protecting our waterways',
    'An Act protecting our soil and farms from PFAS contamination',
    'An Act relative to liability for release of hazardous materials',
    'An Act relative to landfills and areas of critical environmental concern',
    'An Act relative to maintaining adequate water supplies through effective drought management',
    'Monitor the adoption and implementation of the Low Emission Vehicle Program',
    'An Act relative to stormwater management',
    'An Act relative to clean energy and climate resilience',
    'An Act relative to reducing greenhouse gas emissions',
    'An Act relative to wetlands protection',
    'An Act relative to air quality standards',
    'An Act relative to ocean and coastal resource management',
]

NON_ENV_EXAMPLE_BILLS = [
    # Labor / wages
    'An Act requiring one fair wage',
    'An Act clarifying the process for paying the wages of dismissed employees',
    'An Act to establish a hospital and community health center worker minimum wage',
    'An Act relative to equitable pay in the public sector',
    # Criminal justice / public safety
    'An Act to prohibit carrying firearms in sensitive places',
    'An Act further defining a hate crime',
    'An Act limiting autonomous driving capabilities to zero emission and electric vehicles',
    'An Act relative to disability pensions for violent crimes',
    # Healthcare / insurance / medical
    'An Act to improve sickle cell care',
    'An Act to promote the recruitment and retention of hospital workers',
    'An Act to ensure consumer cost protection under the dental medical loss ratio',
    'An Act alleviating the burden of medical debt for patients and families',
    'An Act relative to improving the outcomes for sudden cardiac arrest in the Commonwealth',
    'An Act requiring full health insurance coverage for individuals with vitiligo',
    'An Act to modernize the Massachusetts insurer insolvency fund',
    # Education
    'An Act establishing a college tuition tax deduction',
    'An Act to support educational opportunity for all',
    'An Act protecting against attempts to ban remove or restrict library access to materials',
    'An Act relative to charter schools',
    # Housing / finance / tax
    'An Act to lift kids out of deep poverty',
    'An Act establishing a tax credit for families caring for elderly relatives',
    'An Act to require equitable payment from the Commonwealth',
    'An Act relative to the Affordable Homes Act',
    'An Act making appropriations for the fiscal year for the maintenance of the departments of the commonwealth',
    # Liquor / municipal licensing
    'An Act relative to liquor licenses in the city of Westfield',
    'An Act authorizing the town of Wrentham to grant additional licenses for the sale of alcoholic beverages',
    'Supporting Local Services',
    # Digital / media / tech
    'An Act providing incentives to the digital interactive media and entertainment industries',
    'An Act to establish a digital advertising revenue commission',
    'An Act relative to legal advertisements in online-only newspapers',
    'An Act relative to access to a decedent electronic mail accounts',
    # Legal / civil procedure
    'An Act to modify the rules for taking depositions outside the Commonwealth',
    'An Act to prohibit the sale of energy drinks to persons under the age of 18',
    # LGBTQ / social services
    'An Act relative to LGBTQ family building',
    'An Act to preserve the eternal bonds between people and their animals',
    'An Act protecting the right to time off for voting',
    # Tourism / entertainment / other economy
    'An Act to aid economic recovery of the tourism industry',
    'An Act further regulating the rental of motor vehicles',
    'An Act relative to carriers of property by motor vehicle',
]


# ─── GCS helpers ──────────────────────────────────────────────────────────────

def _load_parquet() -> pd.DataFrame | None:
    """Load existing Parquet from GCS, falling back to local cache."""
    # Try GCS first
    try:
        import gcsfs
        fs = gcsfs.GCSFileSystem()
        if fs.exists(GCS_PARQUET):
            with fs.open(GCS_PARQUET, 'rb') as f:
                df = pd.read_parquet(f)
            print(f'  Loaded {len(df)} rows from {GCS_PARQUET}')
            return df
    except Exception as e:
        print(f'  GCS load failed ({e}), trying local...')
    # Fall back to local
    if LOCAL_PARQUET.exists():
        df = pd.read_parquet(LOCAL_PARQUET)
        print(f'  Loaded {len(df)} rows from local cache')
        return df
    return None


def _save_parquet(df: pd.DataFrame) -> None:
    """Save Parquet to both local and GCS."""
    # Convert embedding column to list of Python floats for Parquet
    df = df.copy()
    if 'embedding' in df.columns and len(df) > 0:
        if isinstance(df['embedding'].iloc[0], np.ndarray):
            df['embedding'] = df['embedding'].apply(lambda x: x.tolist())

    df.to_parquet(LOCAL_PARQUET, index=False)
    print(f'  Saved {len(df)} rows to {LOCAL_PARQUET}')

    try:
        import gcsfs
        fs = gcsfs.GCSFileSystem()
        with fs.open(GCS_PARQUET, 'wb') as f:
            df.to_parquet(f, index=False)
        print(f'  Uploaded to {GCS_PARQUET}')
    except Exception as e:
        print(f'  GCS upload failed: {e} (local copy saved)')


# ─── Text helpers ──────────────────────────────────────────────────────────────

def _get_full_text(bill_id: str | None, general_court: int) -> str:
    """Read full bill text from legislature cache JSON, truncated to MAX_TEXT_CHARS."""
    if not bill_id:
        return ''
    cache_file = CACHE_DIR / f'bill_{general_court}_{bill_id}.json'
    if not cache_file.exists():
        return ''
    try:
        data = json.loads(cache_file.read_text(encoding='utf-8'))
        return (data.get('DocumentText') or '')[:MAX_TEXT_CHARS]
    except Exception:
        return ''


# ─── Embedding helpers ─────────────────────────────────────────────────────────

def _read_api_key() -> str:
    if not API_KEY_PATH.exists():
        raise FileNotFoundError(f'API key not found at {API_KEY_PATH}')
    return API_KEY_PATH.read_text().strip()


def _make_client(api_key: str):
    import google.genai as genai
    return genai.Client(api_key=api_key)


def _embed_texts(client, texts: list[str]) -> np.ndarray:
    """Embed texts with retry. Returns (N, EMBEDDING_DIM) float32 array."""
    from google.genai import types
    vectors = []
    for i, text in enumerate(texts):
        if (i + 1) % 200 == 0:
            print(f'    {i + 1}/{len(texts)}...')
        if not text or not text.strip():
            vectors.append([0.0] * EMBEDDING_DIM)
            continue
        time.sleep(REQUEST_DELAY)
        for attempt in range(5):
            try:
                result = client.models.embed_content(
                    model='gemini-embedding-2',
                    contents=text,
                    config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
                )
                vectors.append(result.embeddings[0].values)
                break
            except Exception as e:
                wait = 2 ** attempt
                print(f'    Embed error (attempt {attempt+1}/5): {e} — retrying in {wait}s')
                time.sleep(wait)
        else:
            print(f'    Failed to embed "{text[:60]}" — using zero vector')
            vectors.append([0.0] * EMBEDDING_DIM)
    return np.array(vectors, dtype=np.float32)


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a_norm = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-10)
    b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-10)
    return a_norm @ b_norm.T


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--rescore', action='store_true',
                        help='Re-score all existing embeddings with current example sets '
                             '(no new API embedding calls for already-embedded bills)')
    args = parser.parse_args()

    lobby_path = DATA_DIR / 'MA_lobbying_bills.csv'
    if not lobby_path.exists():
        print(f'ERROR: {lobby_path} not found. Run get_MA_lobbying.py first.')
        return

    # Build bill_id lookup from legislature bills CSV (bill_id = H/S + number)
    leg_path = DATA_DIR / 'MA_legislature_bills.csv'
    bill_id_map: dict[tuple, str] = {}
    leg_title_map: dict[tuple, str] = {}
    if leg_path.exists():
        try:
            leg = pd.read_csv(leg_path, index_col=0)
            needed = {'bill_id', 'bill_number', 'general_court'}
            if needed.issubset(leg.columns):
                for _, row in leg.dropna(subset=list(needed)).iterrows():
                    key = (int(row['bill_number']), int(row['general_court']))
                    bill_id_map[key] = str(row['bill_id'])
                    if row.get('title'):
                        leg_title_map[key] = str(row['title'])
        except Exception as e:
            print(f'  Warning: could not read {leg_path} ({e}) — skipping bill_id lookup')

    # Unique bills from lobbying data
    lobby = pd.read_csv(lobby_path, index_col=0)
    unique = (
        lobby[['bill_number', 'general_court', 'bill_title']]
        .dropna(subset=['bill_number', 'general_court'])
        .drop_duplicates(subset=['bill_number', 'general_court'])
        .sort_values(['general_court', 'bill_number'])
        .reset_index(drop=True)
    )
    unique['bill_number'] = pd.to_numeric(unique['bill_number'], errors='coerce').dropna().astype(int)
    unique = unique.dropna(subset=['bill_number', 'general_court'])
    unique['bill_number'] = unique['bill_number'].astype(int)
    unique['general_court'] = unique['general_court'].astype(int)
    unique['bill_id'] = unique.apply(
        lambda r: bill_id_map.get((r['bill_number'], r['general_court'])), axis=1
    )
    # Fill missing portal titles from Legislature API titles
    missing_title = unique['bill_title'].isna() | (unique['bill_title'].str.strip() == '')
    unique.loc[missing_title, 'bill_title'] = unique[missing_title].apply(
        lambda r: leg_title_map.get((r['bill_number'], r['general_court'])), axis=1
    )
    n_filled = missing_title.sum() - (unique['bill_title'].isna() | (unique['bill_title'].str.strip() == '')).sum()
    if n_filled:
        print(f'  Filled {n_filled} missing titles from Legislature API')
    print(f'Unique bills in lobbying data: {len(unique)}')
    print(f'  {unique["bill_id"].notna().sum()} have legislature bill_id')

    # Load existing Parquet
    existing = _load_parquet()
    already_done: set = set()
    if existing is not None:
        already_done = set(
            zip(existing['bill_number'].astype(int),
                existing['general_court'].astype(int))
        )
        print(f'  {len(already_done)} already embedded')

    unscored = unique[
        ~unique.apply(lambda r: (r['bill_number'], r['general_court']) in already_done, axis=1)
    ]
    print(f'Embedding {len(unscored)} new bills...')

    api_key = _read_api_key()
    client = _make_client(api_key)

    # Embed example bills once (always needed — for new bills and for --rescore)
    print('Embedding reference examples...')
    env_emb = _embed_texts(client, ENV_EXAMPLE_BILLS)
    non_env_emb = _embed_texts(client, NON_ENV_EXAMPLE_BILLS)

    if not unscored.empty:
        # Build text to embed: full_text if available, else title
        full_texts = unscored.apply(
            lambda r: _get_full_text(r['bill_id'], r['general_court']), axis=1
        )
        n_with_text = (full_texts.str.len() > 0).sum()
        print(f'  {n_with_text}/{len(unscored)} bills have full text from legislature cache')

        embed_texts = (full_texts.where(full_texts.str.len() > 0, other=None)
                       .fillna(unscored['bill_title'].fillna(''))).tolist()

        # Embed in chunks
        CHECKPOINT = 500
        bill_emb_parts = []
        for start in range(0, len(embed_texts), CHECKPOINT):
            chunk = embed_texts[start:start + CHECKPOINT]
            print(f'  Chunk {start}–{start + len(chunk)}...')
            bill_emb_parts.append(_embed_texts(client, chunk))
        bill_emb = np.vstack(bill_emb_parts)

        # Score new bills
        env_sims = _cosine_sim(bill_emb, env_emb).max(axis=1)
        non_env_sims = _cosine_sim(bill_emb, non_env_emb).max(axis=1)
        diff_scores = env_sims - non_env_sims

        n_env = int((diff_scores >= ENV_THRESHOLD).sum())
        print(f'  {n_env}/{len(unscored)} new bills flagged is_environmental')

        # Build new rows
        new_rows = unscored[['bill_number', 'general_court', 'bill_title', 'bill_id']].copy()
        new_rows['full_text'] = full_texts.values
        new_rows['embedding'] = [bill_emb[i] for i in range(len(bill_emb))]
        new_rows['env_relevance_score'] = diff_scores
        new_rows['is_environmental'] = diff_scores >= ENV_THRESHOLD
        new_rows['cluster_id'] = -1

        # Merge
        if existing is not None and not existing.empty:
            combined = pd.concat([existing, new_rows], ignore_index=True)
        else:
            combined = new_rows
    else:
        print('No new bills to embed.')
        if existing is None:
            print('Nothing to do.')
            return
        combined = existing

    # --rescore: re-score ALL rows in combined using current example embeddings.
    # This is fast (pure numpy) — no API calls for bill embeddings.
    if args.rescore or not unscored.empty:
        print(f'Scoring all {len(combined)} bills with current example sets...')
        emb_matrix = np.array(combined['embedding'].tolist(), dtype=np.float32)
        env_sims_all = _cosine_sim(emb_matrix, env_emb).max(axis=1)
        non_env_sims_all = _cosine_sim(emb_matrix, non_env_emb).max(axis=1)
        combined['env_relevance_score'] = env_sims_all - non_env_sims_all
        combined['is_environmental'] = combined['env_relevance_score'] >= ENV_THRESHOLD
        n_env_total = int(combined['is_environmental'].sum())
        print(f'  {n_env_total}/{len(combined)} bills flagged is_environmental '
              f'(threshold={ENV_THRESHOLD})')

    _save_parquet(combined)

    # Write lightweight scored CSV (no embeddings — committed to repo)
    scored_cols = ['bill_number', 'general_court', 'bill_title', 'bill_id',
                   'env_relevance_score', 'is_environmental', 'cluster_id']
    scored_path = DATA_DIR / 'MA_lobbying_bills_scored.csv'
    combined[scored_cols].to_csv(scored_path)
    n_total_env = int(combined['is_environmental'].sum())
    print(f'Wrote {len(combined)} rows to scored CSV ({n_total_env} environmental)')


if __name__ == '__main__':
    main()
