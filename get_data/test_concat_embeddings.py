"""Test whether concatenated title+body embeddings give better cluster separation.

Approach
────────
For a random sample of N bills with non-empty full text:
  A. Original:    embed(title + "\n\n" + cleaned_body[:3000])   — current method
  B. Concatenated: [L2(embed(title)), L2(embed(cleaned_body[:3000]))]  → 1536-dim
                    then L2-normalise the 1536-dim vector

Both are then mean-centred + L2-normalised before k-means (k=25) and evaluated
with silhouette + Davies-Bouldin on the sample.

The "original" embeddings are pulled directly from the parquet (no API calls);
only the title-only and body-only embeddings require API calls (2N calls total).

Run from get_data/:
    /path/to/python -u test_concat_embeddings.py [--sample N]
"""

import argparse
import re
import sys
import time
from pathlib import Path

import gcsfs
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import davies_bouldin_score, silhouette_score
from sklearn.preprocessing import normalize

GCS_PARQUET   = 'gs://openamend-data/MA_bill_embeddings.parquet'
API_KEY_PATH  = Path('SECRET_GOOGLE_API_KEY')
EMBEDDING_DIM = 768
REQUEST_DELAY = 0.05

# ── Boilerplate stripper (same regex as score_lobbying_bills.py) ──────────────
_SCAFFOLD_RE = re.compile(
    r'(?:'
    r'(?:chapter|section|paragraph|clause|subsection|item)\s+[\w\-]+\s+of\s+(?:the\s+)?'
    r'(?:general laws|acts of \d{4}|chapter \d+)[^.]{0,120}(?:hereby\s+amended|is\s+amended)'
    r'|the\s+(?:general laws|acts of \d{4})[^.]{0,120}(?:hereby\s+amended|is\s+amended)'
    r'|by\s+inserting\s+after[^.]{0,200}'
    r'|by\s+striking\s+out[^.]{0,200}'
    r'|as\s+appearing\s+in\s+the\s+\d{4}\s+official\s+edition[^.]{0,100}'
    r'|in\s+the\s+following\s+new\s+(?:section|chapter|paragraph)[^:]{0,80}:'
    r')',
    re.IGNORECASE,
)
_WS_RE = re.compile(r'\s{2,}')


def _clean_body(raw: str, max_chars: int = 3000) -> str:
    cleaned = _SCAFFOLD_RE.sub(' ', raw)
    return _WS_RE.sub(' ', cleaned).strip()[:max_chars]


def _embed_texts(client, texts: list[str], label: str) -> np.ndarray:
    from google.genai import types
    vectors = []
    for i, text in enumerate(texts):
        if (i + 1) % 100 == 0:
            print(f'    {label}: {i+1}/{len(texts)}...')
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
                print(f'    Error (attempt {attempt+1}/5): {e} — retrying in {wait}s')
                time.sleep(wait)
        else:
            print(f'    Failed: "{text[:60]}" — zero vector')
            vectors.append([0.0] * EMBEDDING_DIM)
    return np.array(vectors, dtype=np.float32)


def _eval(emb: np.ndarray, k: int = 25, seed: int = 42) -> tuple[float, float]:
    """Mean-centre, L2-normalise, k-means, return (silhouette, DB)."""
    e = normalize(emb - emb.mean(axis=0), 'l2')
    lbl = KMeans(n_clusters=k, random_state=seed, n_init=10, max_iter=300).fit_predict(e)
    sil = silhouette_score(e, lbl, metric='euclidean')
    db  = davies_bouldin_score(e, lbl)
    return sil, db


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sample', type=int, default=2000,
                        help='Number of bills to sample (default: 2000)')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--k', type=int, default=25, help='k for k-means (default: 25)')
    args = parser.parse_args()

    # ── Load parquet ──────────────────────────────────────────────────────────
    print('Loading parquet from GCS...')
    fs = gcsfs.GCSFileSystem()
    with fs.open(GCS_PARQUET, 'rb') as f:
        df = pd.read_parquet(f)

    # Keep bills with valid embeddings and non-empty full text
    emb_all = np.vstack(df['embedding'].apply(lambda v: np.array(v, dtype=np.float32)).values)
    valid = (np.linalg.norm(emb_all, axis=1) > 0.01) & (df['full_text'].str.len() > 100)
    df = df[valid].copy()
    emb_all = emb_all[valid]
    print(f'{len(df)} bills with valid embeddings and non-empty full text')

    # Sample
    rng = np.random.default_rng(args.seed)
    idx = rng.choice(len(df), min(args.sample, len(df)), replace=False)
    sample = df.iloc[idx].reset_index(drop=True)
    emb_orig = emb_all[idx]
    print(f'Sampled {len(sample)} bills')

    # ── Prepare texts ─────────────────────────────────────────────────────────
    titles = sample['bill_title'].fillna('').tolist()
    bodies = sample['full_text'].fillna('').apply(_clean_body).tolist()

    # ── Evaluate original embeddings (no API calls) ───────────────────────────
    print(f'\nA. Original (title+body combined, from parquet), k={args.k}:')
    sil_a, db_a = _eval(emb_orig, k=args.k, seed=args.seed)
    print(f'   Silhouette: {sil_a:.4f}  |  Davies-Bouldin: {db_a:.4f}')

    # ── Embed title-only and body-only ────────────────────────────────────────
    print(f'\nEmbedding {len(sample)} title-only texts...')
    import google.genai as genai
    api_key = API_KEY_PATH.read_text().strip()
    client = genai.Client(api_key=api_key)

    emb_title = _embed_texts(client, titles, 'titles')
    print(f'Embedding {len(sample)} body-only texts...')
    emb_body  = _embed_texts(client, bodies, 'bodies')

    # ── Build concatenated embeddings ─────────────────────────────────────────
    # Normalise each 768-dim half independently, then concatenate → 1536-dim
    # (gives equal weight to title and body signal before final normalisation)
    t_norm = normalize(emb_title, 'l2')
    b_norm = normalize(emb_body,  'l2')
    emb_concat = np.hstack([t_norm, b_norm])  # (N, 1536)

    print(f'\nB. Title-only, k={args.k}:')
    sil_t, db_t = _eval(emb_title, k=args.k, seed=args.seed)
    print(f'   Silhouette: {sil_t:.4f}  |  Davies-Bouldin: {db_t:.4f}')

    print(f'\nC. Body-only, k={args.k}:')
    sil_b, db_b = _eval(emb_body, k=args.k, seed=args.seed)
    print(f'   Silhouette: {sil_b:.4f}  |  Davies-Bouldin: {db_b:.4f}')

    print(f'\nD. Concatenated [L2(title) | L2(body)], k={args.k}:')
    sil_c, db_c = _eval(emb_concat, k=args.k, seed=args.seed)
    print(f'   Silhouette: {sil_c:.4f}  |  Davies-Bouldin: {db_c:.4f}')

    print('\n── Summary ──')
    print(f'{"Method":<35} {"Silhouette":>10} {"DB":>8}')
    print(f'{"A. Original (title+body combined)":<35} {sil_a:>10.4f} {db_a:>8.4f}')
    print(f'{"B. Title only":<35} {sil_t:>10.4f} {db_t:>8.4f}')
    print(f'{"C. Body only":<35} {sil_b:>10.4f} {db_b:>8.4f}')
    print(f'{"D. Concat [L2(title)|L2(body)]":<35} {sil_c:>10.4f} {db_c:>8.4f}')

    print('\nDone.')


if __name__ == '__main__':
    main()
