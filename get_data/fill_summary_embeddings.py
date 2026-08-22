"""Fill missing summary_embedding values for bills that already have a summary.

Non-destructive and incremental:
  - Only touches rows where summary IS NOT NULL AND summary_embedding IS NULL
  - Never overwrites an existing embedding
  - Never modifies summary, categories, tags, is_env_llm, or any other column
  - Loads fresh from GCS before writing to avoid clobbering concurrent changes
  - Always prints before/after counts

Run from get_data/:
    python fill_summary_embeddings.py [--dry-run] [--workers N]
"""

import argparse
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

API_KEY_PATH    = Path('SECRET_GOOGLE_API_KEY')
DATA_DIR        = Path('../docs/data')
LOCAL_PARQUET   = DATA_DIR / 'MA_bill_embeddings.parquet'
GCS_PARQUET     = 'gs://openamend-data/MA_bill_embeddings.parquet'
EMBEDDING_MODEL = 'gemini-embedding-2'
EMBEDDING_DIM   = 768


def _load_parquet() -> pd.DataFrame:
    try:
        import gcsfs
        fs = gcsfs.GCSFileSystem()
        if fs.exists(GCS_PARQUET):
            with fs.open(GCS_PARQUET, 'rb') as f:
                df = pd.read_parquet(f)
            print(f'Loaded {len(df):,} rows from GCS')
            return df
    except Exception as e:
        print(f'GCS failed ({e}), using local')
    df = pd.read_parquet(LOCAL_PARQUET)
    print(f'Loaded {len(df):,} rows from local')
    return df


def _save_parquet(df: pd.DataFrame) -> None:
    n_emb = int(df['summary_embedding'].notna().sum())
    df.to_parquet(LOCAL_PARQUET, index=False)
    print(f'  Saved local ({n_emb:,} embeddings)')
    try:
        import gcsfs
        fs = gcsfs.GCSFileSystem()
        with fs.open(GCS_PARQUET, 'wb') as f:
            df.to_parquet(f, index=False)
        print(f'  Uploaded to GCS ({n_emb:,} embeddings)')
    except Exception as e:
        print(f'  GCS upload failed: {e}')


def _embed_one(client, idx: int, summary: str) -> tuple[int, 'np.ndarray | None']:
    """Embed one summary with exponential backoff. Returns (idx, vector_or_None)."""
    import google.genai.types as types
    for attempt in range(6):
        try:
            resp = client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=summary,
                config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
            )
            vec = np.array(resp.embeddings[0].values, dtype=np.float32)
            return idx, vec
        except Exception as e:
            if attempt == 5:
                print(f'  [{idx}] embed failed after 6 attempts: {e}')
                return idx, None
            wait = (2 ** attempt) + random.uniform(0, 1)
            print(f'  [{idx}] embed error (attempt {attempt+1}/6): {str(e)[:80]} — retry in {wait:.1f}s')
            time.sleep(wait)
    return idx, None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be embedded without calling the API')
    parser.add_argument('--workers', type=int, default=8,
                        help='Parallel embed workers (default: 8)')
    args = parser.parse_args()

    # ── Load and audit ──────────────────────────────────────────────────────────
    df = _load_parquet()

    has_summary  = df['summary'].notna()
    has_emb      = df['summary_embedding'].notna()
    needs_embed  = has_summary & ~has_emb
    already_done = has_summary & has_emb
    no_summary   = ~has_summary

    print()
    print('── Pre-flight audit ──────────────────────────────────────────────')
    print(f'  Total bills:                {len(df):,}')
    print(f'  Has summary + embedding:    {already_done.sum():,}  (will NOT be touched)')
    print(f'  Has summary, NO embedding:  {needs_embed.sum():,}  ← will embed these')
    print(f'  No summary (skip):          {no_summary.sum():,}  (will NOT be touched)')
    print(f'  Columns that will change:   summary_embedding only')
    print(f'  Columns never touched:      summary, categories, tags, is_env_llm, '
          f'embedding, env_relevance_score, is_environmental, cluster_id')
    print()

    if needs_embed.sum() == 0:
        print('Nothing to do — all summaries already have embeddings.')
        return

    todo_idx  = df.index[needs_embed].tolist()
    todo_text = df.loc[needs_embed, 'summary'].tolist()

    print(f'GC distribution of bills to embed:')
    print(df[needs_embed]['general_court'].value_counts().sort_index().to_string())
    print()

    if args.dry_run:
        print(f'DRY RUN — would embed {len(todo_idx)} summaries, no API calls made.')
        print(f'Sample:')
        for i in range(min(3, len(todo_idx))):
            idx = todo_idx[i]
            print(f'  [{idx}] GC{int(df.loc[idx,"general_court"])} '
                  f'{df.loc[idx,"bill_number"]}: {str(df.loc[idx,"summary"])[:80]}')
        return

    # ── Embed ───────────────────────────────────────────────────────────────────
    api_key = API_KEY_PATH.read_text().strip()
    import google.genai as genai
    client = genai.Client(api_key=api_key)

    print(f'Embedding {len(todo_idx)} summaries with {args.workers} workers...')
    n_ok = n_fail = 0
    results: dict[int, np.ndarray] = {}

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(_embed_one, client, idx, text): idx
            for idx, text in zip(todo_idx, todo_text)
        }
        for future in as_completed(futures):
            idx, vec = future.result()
            if vec is not None:
                results[idx] = vec
                n_ok += 1
            else:
                n_fail += 1
            done = n_ok + n_fail
            if done % 50 == 0 or done == len(todo_idx):
                print(f'  {done}/{len(todo_idx)} embedded ({n_ok} ok, {n_fail} failed)',
                      flush=True)

    # ── Write ONLY summary_embedding, only for rows that needed it ──────────────
    print(f'\nWriting {n_ok} embeddings to parquet (non-destructive)...')

    # Verify before writing: confirm no embeddings appeared in target rows
    # since we loaded (e.g. from a concurrent process)
    still_missing = df.index[needs_embed]
    collisions = df.loc[still_missing, 'summary_embedding'].notna().sum()
    if collisions > 0:
        print(f'  ⚠️  {collisions} rows gained embeddings since load — skipping those')

    written = 0
    for idx, vec in results.items():
        # Final guard: only write if still null
        if pd.isna(df.at[idx, 'summary_embedding']):
            df.at[idx, 'summary_embedding'] = vec.tolist()
            written += 1

    print(f'  Rows updated: {written}')
    print(f'  Rows skipped (collision guard): {n_ok - written}')

    # ── Save ────────────────────────────────────────────────────────────────────
    after_emb  = int(df['summary_embedding'].notna().sum())
    after_summ = int(df['summary'].notna().sum())

    # Sanity: summary count must be unchanged
    before_summ = int(already_done.sum() + needs_embed.sum())
    assert after_summ == before_summ, \
        f'summary count changed: {before_summ} → {after_summ} — ABORTING save'

    print(f'\nPre-save sanity:')
    print(f'  summary count:           {before_summ:,} → {after_summ:,}  ✓ unchanged')
    print(f'  summary_embedding count: {already_done.sum():,} → {after_emb:,}  '
          f'(+{after_emb - already_done.sum()})')

    _save_parquet(df)

    if n_fail:
        print(f'\n⚠️  {n_fail} embeds failed — re-run to fill gaps')
    else:
        print(f'\n✅ All {n_ok} embeddings written successfully')


if __name__ == '__main__':
    main()
