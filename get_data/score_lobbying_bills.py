"""Score and embed MA lobbying bills for environmental relevance and topic clustering.

Model: gemini-embedding-2 (free tier: 1,500 req/min, 1M req/month).
API key: read from get_data/SECRET_GOOGLE_API_KEY.

Two outputs, both incremental (only new bills processed per run):

1. MA_lobbying_bills_scored.csv — one row per unique (bill_number, general_court):
     bill_title, env_relevance_score (0–1), is_environmental (bool),
     cluster_id (int, -1 until cluster_lobbying_bills.py is run)

2. MA_bill_embeddings.npy  — (N, 768) float32 array; row order matches
   MA_lobbying_bills_scored.csv sorted by (bill_number, general_court).
   Used by cluster_lobbying_bills.py for k-means clustering.

Environmental relevance: cosine similarity of each bill's title embedding
against 20 seed phrases covering environmental regulation topics.
Threshold: 0.60 (tune against a hand-labeled set as data grows).

Run from the get_data/ directory after get_MA_lobbying.py:
    /path/to/python -u score_lobbying_bills.py

Outputs:
  ../docs/data/MA_lobbying_bills_scored.csv
  ../docs/data/MA_bill_embeddings.npy
"""

import time
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path('../docs/data')
API_KEY_PATH = Path('SECRET_GOOGLE_API_KEY')

ENV_THRESHOLD = 0.60
EMBEDDING_DIM = 768
REQUEST_DELAY = 0.05  # well within 1,500 req/min free tier

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


def _make_client(api_key: str):
    import google.genai as genai
    return genai.Client(api_key=api_key)


def _embed_texts(client, texts: list[str]) -> np.ndarray:
    """Embed a list of texts. Returns (N, EMBEDDING_DIM) float32 array."""
    from google.genai import types
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


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """(N, M) cosine similarity between rows of a and rows of b."""
    a_norm = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-10)
    b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-10)
    return a_norm @ b_norm.T


def main():
    lobby_path = DATA_DIR / 'MA_lobbying_bills.csv'
    if not lobby_path.exists():
        print(f'ERROR: {lobby_path} not found. Run get_MA_lobbying.py first.')
        return

    # Unique bills from lobbying data — bill_title comes from the SoS portal
    lobby = pd.read_csv(lobby_path, index_col=0)
    unique = (
        lobby[['bill_number', 'general_court', 'bill_title']]
        .dropna(subset=['bill_number', 'general_court'])
        .drop_duplicates(subset=['bill_number', 'general_court'])
        .sort_values(['general_court', 'bill_number'])
        .reset_index(drop=True)
    )
    print(f'Unique bills in lobbying data: {len(unique)}')

    # Load existing scored CSV
    scored_path = DATA_DIR / 'MA_lobbying_bills_scored.csv'
    emb_path = DATA_DIR / 'MA_bill_embeddings.npy'

    existing_scored: pd.DataFrame | None = None
    existing_emb: np.ndarray | None = None
    already_scored: set = set()

    if scored_path.exists():
        existing_scored = pd.read_csv(scored_path, index_col=0)
        already_scored = set(
            zip(existing_scored['bill_number'].astype(str),
                existing_scored['general_court'].astype(str))
        )
        print(f'  {len(existing_scored)} bills already scored')

    if emb_path.exists():
        existing_emb = np.load(emb_path)

    # Find unscored bills
    unscored = unique[
        ~unique.apply(
            lambda r: (str(r['bill_number']), str(r['general_court'])) in already_scored,
            axis=1
        )
    ]
    print(f'Scoring {len(unscored)} new bills...')

    if unscored.empty:
        print('Nothing to do.')
        return

    api_key = _read_api_key()
    client = _make_client(api_key)

    # Embed seed phrases once
    print('Embedding seed phrases...')
    seed_emb = _embed_texts(client, ENV_SEED_PHRASES)

    # Embed bill titles
    bill_texts = (
        unscored['bill_number'].astype(str) + ': ' +
        unscored['bill_title'].fillna('').astype(str)
    ).tolist()
    print(f'Embedding {len(bill_texts)} bill titles...')
    bill_emb = _embed_texts(client, bill_texts)

    # Score
    sims = _cosine_sim(bill_emb, seed_emb)
    max_sims = sims.max(axis=1)

    new_scored = unscored[['bill_number', 'general_court', 'bill_title']].copy()
    new_scored['env_relevance_score'] = max_sims
    new_scored['is_environmental'] = max_sims >= ENV_THRESHOLD
    new_scored['cluster_id'] = -1  # populated by cluster_lobbying_bills.py

    n_env = int((max_sims >= ENV_THRESHOLD).sum())
    print(f'  {n_env}/{len(unscored)} new bills flagged is_environmental')

    # Merge with existing
    if existing_scored is not None and not existing_scored.empty:
        combined_scored = pd.concat([existing_scored, new_scored], ignore_index=True)
        combined_emb = np.vstack([existing_emb, bill_emb])
    else:
        combined_scored = new_scored
        combined_emb = bill_emb

    combined_scored.to_csv(scored_path)
    np.save(emb_path, combined_emb)

    n_total_env = int(combined_scored['is_environmental'].sum())
    print(f'Wrote {len(combined_scored)} scored bills '
          f'({n_total_env} environmental) to {scored_path}')
    print(f'Wrote embeddings ({combined_emb.shape}) to {emb_path}')


if __name__ == '__main__':
    main()
