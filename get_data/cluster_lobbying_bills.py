"""Cluster MA lobbying bills by topic using k-means on Gemini embeddings,
then label each cluster with Gemini Flash.

This is a ONE-TIME script (or re-run manually when you want to re-cluster,
e.g. after the full historical fetch adds many new bills). It is NOT part of
weekly CI.

Steps:
  1. Load embeddings from MA_bill_embeddings.npy
  2. K-means into N_CLUSTERS clusters (default 15)
  3. For each cluster, send the 20 most central bill titles to Gemini Flash
     and ask for a short topic label (3–5 words)
  4. Write cluster assignments back to MA_lobbying_bills_scored.csv
  5. Write cluster label lookup to MA_bill_cluster_labels.csv

Run from the get_data/ directory after score_lobbying_bills.py:
    /path/to/python cluster_lobbying_bills.py [--n-clusters N]

Outputs:
  ../docs/data/MA_lobbying_bills_scored.csv   — cluster_id column updated
  ../docs/data/MA_bill_cluster_labels.csv     — cluster_id, label, n_bills, n_env_bills
"""

import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import normalize

DATA_DIR = Path('../docs/data')
API_KEY_PATH = Path('SECRET_GOOGLE_API_KEY')

N_CLUSTERS_DEFAULT = 15
N_LABEL_EXAMPLES = 20   # bill titles sent to Gemini per cluster for labeling
GEMINI_DELAY = 1.0      # seconds between Gemini calls


def _read_api_key() -> str:
    if not API_KEY_PATH.exists():
        raise FileNotFoundError(f'API key not found at {API_KEY_PATH}')
    return API_KEY_PATH.read_text().strip()


def _label_cluster(client, titles: list[str], cluster_id: int) -> str:
    """Ask Gemini Flash to produce a 3–5 word topic label for a cluster."""
    import google.genai as genai
    time.sleep(GEMINI_DELAY)
    bullet_list = '\n'.join(f'- {t}' for t in titles)
    prompt = (
        f'The following are bill titles from the Massachusetts legislature '
        f'that share a common policy topic (cluster {cluster_id}):\n\n'
        f'{bullet_list}\n\n'
        f'Give a concise topic label for this cluster in 3–5 words. '
        f'Reply with ONLY the label, no explanation.'
    )
    response = client.models.generate_content(
        model='gemini-2.0-flash',
        contents=prompt,
    )
    return response.text.strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--n-clusters', type=int, default=N_CLUSTERS_DEFAULT)
    parser.add_argument('--no-label', action='store_true',
                        help='Skip Gemini labeling (use cluster IDs only)')
    args = parser.parse_args()

    scored_path = DATA_DIR / 'MA_lobbying_bills_scored.csv'
    emb_path = DATA_DIR / 'MA_bill_embeddings.npy'

    if not scored_path.exists() or not emb_path.exists():
        print('ERROR: Run score_lobbying_bills.py first.')
        return

    scored = pd.read_csv(scored_path, index_col=0)
    emb = np.load(emb_path)

    if len(scored) != len(emb):
        print(f'ERROR: scored CSV has {len(scored)} rows but embeddings have {len(emb)} — '
              're-run score_lobbying_bills.py to sync.')
        return

    print(f'Clustering {len(scored)} bills into {args.n_clusters} clusters...')

    # Normalize embeddings for cosine-space clustering
    emb_norm = normalize(emb, norm='l2')
    km = KMeans(n_clusters=args.n_clusters, random_state=42, n_init=10)
    labels = km.fit_predict(emb_norm)
    scored['cluster_id'] = labels

    # Build label lookup
    api_key = _read_api_key()
    import google.genai as genai
    client = genai.Client(api_key=api_key)

    cluster_rows = []
    for cid in range(args.n_clusters):
        mask = labels == cid
        cluster_bills = scored[mask]
        n_bills = int(mask.sum())
        n_env = int(cluster_bills['is_environmental'].sum())

        # Most central bills: smallest distance to centroid
        centroid = km.cluster_centers_[cid]
        dists = np.linalg.norm(emb_norm[mask] - centroid, axis=1)
        top_idx = np.argsort(dists)[:N_LABEL_EXAMPLES]
        top_titles = cluster_bills.iloc[top_idx]['bill_title'].fillna('').tolist()

        if args.no_label:
            label = f'Cluster {cid}'
        else:
            print(f'  Labeling cluster {cid} ({n_bills} bills, {n_env} env)...')
            try:
                label = _label_cluster(client, top_titles, cid)
            except Exception as e:
                print(f'    Gemini error: {e} — using fallback label')
                label = f'Cluster {cid}'

        print(f'  Cluster {cid}: "{label}" — {n_bills} bills, {n_env} environmental')
        cluster_rows.append({
            'cluster_id': cid,
            'label': label,
            'n_bills': n_bills,
            'n_env_bills': n_env,
            'example_titles': ' | '.join(top_titles[:5]),
        })

    labels_df = pd.DataFrame(cluster_rows)
    labels_path = DATA_DIR / 'MA_bill_cluster_labels.csv'
    labels_df.to_csv(labels_path, index=False)
    scored.to_csv(scored_path)

    print(f'\nWrote cluster assignments to {scored_path}')
    print(f'Wrote cluster labels to {labels_path}')
    print('\nCluster summary:')
    print(labels_df[['cluster_id', 'label', 'n_bills', 'n_env_bills']].to_string(index=False))


if __name__ == '__main__':
    main()
