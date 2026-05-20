"""Score lobbying bills for environmental relevance using Google Gemini embeddings.

Model: gemini-embedding-2 (current production model; 8192-token input, 768–3072-dim output).
API key: read from get_data/SECRET_GOOGLE_API_KEY (same file used by other scripts).

For each bill in MA_legislature_bills.csv that lacks a score, embeds
"<bill_number>: <title>" and computes cosine similarity against a set of seed phrases
covering environmental regulation topics. The maximum similarity across seed phrases is
stored as `env_relevance_score` (0–1 float). A convenience boolean `is_environmental`
is derived at a threshold of 0.60 (tune against a hand-labeled validation set).

Only new/unscored bills are embedded on each run — cost stays low (one API call per
new bill). The embedding dimension used is 768 (smallest available, sufficient for
cosine similarity classification).

Run from the get_data/ directory after get_MA_legislature_bills.py:
    conda run -n amend_python python score_lobbying_bills.py

Outputs (updates in-place):
  ../docs/data/MA_legislature_bills.csv   — adds env_relevance_score, is_environmental columns
"""

import time
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path('../docs/data')
API_KEY_PATH = Path('SECRET_GOOGLE_API_KEY')

# Threshold for is_environmental flag. A bill is considered environmentally relevant
# if its max cosine similarity to any seed phrase exceeds this value.
# Calibrate against a hand-labeled validation set before relying on this.
ENV_THRESHOLD = 0.60

# Output embedding dimension. gemini-embedding-2 supports 128–3072; 768 is sufficient
# for cosine similarity and minimises API cost/latency.
EMBEDDING_DIM = 768

# Rate limiting: max requests per minute for the Gemini Embeddings API (free tier: 1500/min).
# We sleep briefly between calls to avoid bursting.
REQUEST_DELAY = 0.05  # seconds

# Seed phrases representing the environmental-regulation domain.
# Cosine similarity is computed between each bill and all seeds; max is the score.
ENV_SEED_PHRASES = [
    'environmental regulation and protection',
    'water quality and clean water',
    'wetlands protection and conservation',
    'air pollution and emissions control',
    'DEP MassDEP environmental enforcement',
    'stormwater management and runoff',
    'combined sewer overflow CSO discharge',
    'hazardous waste cleanup and remediation',
    'climate change and greenhouse gas emissions',
    'clean energy and renewable power',
    'pesticide and herbicide regulation',
    'drinking water safety and contamination',
    'ocean and coastal resource management',
    'endangered species and wildlife habitat',
    'environmental justice and equity',
    'solid waste recycling and disposal',
    'toxic substances and chemical regulation',
    'land use conservation and open space',
    'oil spill and petroleum contamination',
    'fish and wildlife department',
]


def _read_api_key() -> str:
    if not API_KEY_PATH.exists():
        raise FileNotFoundError(
            f'Google API key not found at {API_KEY_PATH}. '
            'In CI this is written from the GOOGLE_API_KEY secret.'
        )
    return API_KEY_PATH.read_text().strip()


def _embed_texts(texts: list[str], api_key: str) -> np.ndarray:
    """Embed a list of texts using the Gemini Embeddings API.

    Returns an (N, EMBEDDING_DIM) float32 array.
    Uses the `google-genai` SDK (google.genai package).
    """
    import google.genai as genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    vectors = []
    for text in texts:
        time.sleep(REQUEST_DELAY)
        result = client.models.embed_content(
            model='gemini-embedding-2',
            contents=text,
            config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
        )
        vectors.append(result.embeddings[0].values)

    return np.array(vectors, dtype=np.float32)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Compute cosine similarity between each row of a and each row of b.

    Returns an (len(a), len(b)) matrix.
    """
    a_norm = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-10)
    b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-10)
    return a_norm @ b_norm.T


def score_bills(bills_df: pd.DataFrame, api_key: str) -> pd.DataFrame:
    """Add env_relevance_score and is_environmental columns to bills_df.

    Only scores rows that don't already have a score (incremental).
    """
    if 'env_relevance_score' not in bills_df.columns:
        bills_df['env_relevance_score'] = float('nan')
    if 'is_environmental' not in bills_df.columns:
        bills_df['is_environmental'] = False

    unscored_mask = bills_df['env_relevance_score'].isna()
    unscored = bills_df[unscored_mask].copy()
    if unscored.empty:
        print('All bills already scored — nothing to do.')
        return bills_df

    print(f'Scoring {len(unscored)} unscored bills...')

    # Embed seed phrases once
    print('Embedding seed phrases...')
    seed_embeddings = _embed_texts(ENV_SEED_PHRASES, api_key)

    # Build text to embed for each bill: "BILL_NUMBER: title"
    bill_texts = (
        unscored['bill_number'].fillna('').astype(str)
        + ': '
        + unscored['title'].fillna('').astype(str)
    ).tolist()

    print(f'Embedding {len(bill_texts)} bills (this may take a moment)...')
    bill_embeddings = _embed_texts(bill_texts, api_key)

    # Compute cosine similarity: (n_bills, n_seeds); take max across seeds
    sims = _cosine_similarity(bill_embeddings, seed_embeddings)  # (n_bills, n_seeds)
    max_sims = sims.max(axis=1)  # (n_bills,)

    bills_df.loc[unscored_mask, 'env_relevance_score'] = max_sims
    bills_df.loc[unscored_mask, 'is_environmental'] = max_sims >= ENV_THRESHOLD

    n_env = bills_df['is_environmental'].sum()
    print(f'Scored {len(unscored)} bills; {n_env}/{len(bills_df)} total marked is_environmental '
          f'(threshold={ENV_THRESHOLD})')
    return bills_df


def main():
    bills_path = DATA_DIR / 'MA_legislature_bills.csv'
    if not bills_path.exists():
        print(f'ERROR: {bills_path} not found. Run get_MA_legislature_bills.py first.')
        return

    bills_df = pd.read_csv(bills_path, index_col=0)
    api_key = _read_api_key()
    bills_df = score_bills(bills_df, api_key)
    bills_df.to_csv(bills_path)
    print(f'Updated {bills_path}')


if __name__ == '__main__':
    main()
