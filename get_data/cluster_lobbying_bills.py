"""Cluster MA lobbying bills by topic using k-means on Gemini embeddings,
then label each cluster with Gemini Flash.

Modes
─────
Full re-cluster (default):
  Fits a new k-means model on all valid embeddings, generates Gemini labels,
  saves the model + training mean to GCS so incremental mode can reuse it.
  Run manually when the bill corpus has grown substantially.

    python cluster_lobbying_bills.py [--n-clusters N] [--no-label]

Incremental (--incremental):
  Loads the saved k-means model from GCS and assigns cluster labels to any
  bill that currently has cluster_id == -1 (newly embedded bills). No Gemini
  call, no re-fitting — just nearest-centroid lookup. Safe to run in CI after
  score_lobbying_bills.py completes.

    python cluster_lobbying_bills.py --incremental

Relabel only (--relabel):
  Skips re-clustering; regenerates Gemini topic labels for existing cluster
  assignments. Useful when you want better labels without disturbing the
  cluster topology.

    python cluster_lobbying_bills.py --relabel

Outputs
───────
  ../docs/data/MA_lobbying_bills_scored.csv   — cluster_id column updated
  ../docs/data/MA_bill_cluster_labels.csv     — cluster_id, label, n_bills, n_env_bills
  gs://openamend-data/MA_bill_kmeans.joblib   — fitted KMeans model (full run only)
  gs://openamend-data/MA_bill_emb_mean.npy    — training-set mean vector (full run only)

Run from the get_data/ directory after score_lobbying_bills.py:
    /path/to/python cluster_lobbying_bills.py
"""

import argparse
import io
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import normalize

DATA_DIR = Path('../docs/data')
API_KEY_PATH = Path('SECRET_GOOGLE_API_KEY')
GCS_PARQUET  = 'gs://openamend-data/MA_bill_embeddings.parquet'
GCS_MODEL    = 'gs://openamend-data/MA_bill_kmeans.joblib'
GCS_MEAN     = 'gs://openamend-data/MA_bill_emb_mean.npy'
LOCAL_PARQUET = DATA_DIR / 'MA_bill_embeddings.parquet'
LOCAL_MODEL   = DATA_DIR / 'MA_bill_kmeans.joblib'
LOCAL_MEAN    = DATA_DIR / 'MA_bill_emb_mean.npy'

N_CLUSTERS_DEFAULT = 25
N_LABEL_EXAMPLES = 20   # bill titles sent to Gemini per cluster for labeling
GEMINI_DELAY = 1.0      # seconds between Gemini calls


# ─── GCS helpers ───────────────────────────────────────────────────────────────

def _gcs_fs():
    import gcsfs
    return gcsfs.GCSFileSystem()


def _load_parquet():
    try:
        fs = _gcs_fs()
        if fs.exists(GCS_PARQUET):
            with fs.open(GCS_PARQUET, 'rb') as f:
                df = pd.read_parquet(f)
            print(f'Loaded {len(df)} rows from {GCS_PARQUET}')
            return df
    except Exception as e:
        print(f'GCS load failed ({e}), trying local...')
    if LOCAL_PARQUET.exists():
        df = pd.read_parquet(LOCAL_PARQUET)
        print(f'Loaded {len(df)} rows from local Parquet')
        return df
    raise FileNotFoundError('No Parquet file found. Run score_lobbying_bills.py first.')


def _save_model(km: KMeans, mean_vec: np.ndarray) -> None:
    """Persist fitted KMeans model and training mean to GCS and local."""
    # Local
    joblib.dump(km, LOCAL_MODEL)
    np.save(LOCAL_MEAN, mean_vec)
    # GCS
    try:
        fs = _gcs_fs()
        buf = io.BytesIO()
        joblib.dump(km, buf)
        buf.seek(0)
        with fs.open(GCS_MODEL, 'wb') as f:
            f.write(buf.read())
        mean_buf = io.BytesIO()
        np.save(mean_buf, mean_vec)
        mean_buf.seek(0)
        with fs.open(GCS_MEAN, 'wb') as f:
            f.write(mean_buf.read())
        print(f'Saved model to {GCS_MODEL} and {GCS_MEAN}')
    except Exception as e:
        print(f'GCS model upload failed: {e} — local copy saved at {LOCAL_MODEL}')


def _load_model() -> tuple[KMeans, np.ndarray]:
    """Load fitted KMeans model and training mean from GCS (fallback: local)."""
    try:
        fs = _gcs_fs()
        with fs.open(GCS_MODEL, 'rb') as f:
            km = joblib.load(f)
        with fs.open(GCS_MEAN, 'rb') as f:
            mean_vec = np.load(io.BytesIO(f.read()))
        print(f'Loaded model from {GCS_MODEL}')
        return km, mean_vec
    except Exception as e:
        print(f'GCS model load failed ({e}), trying local...')
    if LOCAL_MODEL.exists() and LOCAL_MEAN.exists():
        km = joblib.load(LOCAL_MODEL)
        mean_vec = np.load(LOCAL_MEAN)
        print(f'Loaded model from {LOCAL_MODEL}')
        return km, mean_vec
    raise FileNotFoundError(
        'No saved k-means model found. Run a full cluster first: '
        'python cluster_lobbying_bills.py'
    )


def _save_parquet(parquet_df: pd.DataFrame) -> None:
    try:
        fs = _gcs_fs()
        with fs.open(GCS_PARQUET, 'wb') as f:
            parquet_df.to_parquet(f, index=False)
        print(f'Updated cluster_ids in {GCS_PARQUET}')
    except Exception as e:
        print(f'GCS parquet upload failed: {e}')
    parquet_df.to_parquet(LOCAL_PARQUET, index=False)


# ─── Preprocessing ─────────────────────────────────────────────────────────────

def _preprocess(emb: np.ndarray, mean_vec: np.ndarray) -> np.ndarray:
    """Mean-centre then L2-normalise. Apply the training mean to new data."""
    return normalize(emb - mean_vec, norm='l2')


# ─── Gemini labeling ───────────────────────────────────────────────────────────

def _read_api_key() -> str:
    if not API_KEY_PATH.exists():
        raise FileNotFoundError(f'API key not found at {API_KEY_PATH}')
    return API_KEY_PATH.read_text().strip()


def _label_cluster(client, titles: list[str], cluster_id: int) -> str:
    """Ask Gemini Flash to produce a 3–5 word topic label for a cluster."""
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
        model='gemini-2.5-flash',
        contents=prompt,
    )
    return response.text.strip()


# ─── Build helpers ─────────────────────────────────────────────────────────────

def _build_emb_matrix(parquet_df, scored):
    """Return (emb array, aligned scored DataFrame, valid mask)."""
    parquet_df['_key'] = list(zip(parquet_df['bill_number'].astype(int),
                                   parquet_df['general_court'].astype(int)))
    emb_map = {row['_key']: np.array(row['embedding'], dtype=np.float32)
               for _, row in parquet_df.iterrows()}
    scored = scored.copy()
    scored['_key'] = list(zip(scored['bill_number'].astype(int),
                               scored['general_court'].astype(int)))
    in_map = scored['_key'].isin(emb_map)
    scored = scored[in_map].reset_index(drop=True)
    emb = np.vstack([emb_map[k] for k in scored['_key']])
    scored = scored.drop(columns=['_key'])
    norms = np.linalg.norm(emb, axis=1)
    valid = norms > 0.01
    return emb, scored, valid


# ─── Modes ─────────────────────────────────────────────────────────────────────

def run_full(args, parquet_df, scored, scored_path):
    emb, scored, valid = _build_emb_matrix(parquet_df, scored)

    n_zero = int((~valid).sum())
    if n_zero:
        print(f'  Skipping {n_zero} zero-vector bills — assigned cluster_id=-1')
        scored.loc[~valid, 'cluster_id'] = -1
    emb_v = emb[valid]
    scored_v = scored[valid].reset_index(drop=True)

    # Mean-centre + L2-normalise
    mean_vec = emb_v.mean(axis=0)
    emb_norm = _preprocess(emb_v, mean_vec)

    print(f'Clustering {len(scored_v)} bills into {args.n_clusters} clusters...')
    km = KMeans(n_clusters=args.n_clusters, random_state=42, n_init=10)
    labels = km.fit_predict(emb_norm)
    scored_v['cluster_id'] = labels

    # Persist model and training mean
    _save_model(km, mean_vec)

    _write_labels_and_csv(args, km.cluster_centers_, labels, scored_v,
                          emb_norm, scored, parquet_df, scored_path)


def run_incremental(parquet_df, scored, scored_path):
    """Assign cluster labels to unassigned bills using the saved model.
    Only processes rows where cluster_id == -1.
    """
    km, mean_vec = _load_model()

    unassigned_mask = scored['cluster_id'] == -1
    n_new = int(unassigned_mask.sum())
    if n_new == 0:
        print('No unassigned bills (cluster_id == -1) — nothing to do.')
        return

    print(f'Assigning cluster labels to {n_new} unassigned bills...')

    # Build embedding matrix for unassigned bills only
    parquet_df['_key'] = list(zip(parquet_df['bill_number'].astype(int),
                                   parquet_df['general_court'].astype(int)))
    emb_map = {row['_key']: np.array(row['embedding'], dtype=np.float32)
               for _, row in parquet_df.iterrows()}
    scored_new = scored[unassigned_mask].copy()
    scored_new['_key'] = list(zip(scored_new['bill_number'].astype(int),
                                   scored_new['general_court'].astype(int)))
    in_map = scored_new['_key'].isin(emb_map)
    scored_new = scored_new[in_map]
    emb_new = np.vstack([emb_map[k] for k in scored_new['_key']])
    scored_new = scored_new.drop(columns=['_key'])

    # Filter zero-vectors
    norms = np.linalg.norm(emb_new, axis=1)
    valid = norms > 0.01
    n_zero = int((~valid).sum())
    if n_zero:
        print(f'  {n_zero} zero-vector bills remain unassigned (cluster_id=-1)')

    emb_v = emb_new[valid]
    scored_vv = scored_new[valid]

    # Apply same preprocessing as training
    emb_norm = _preprocess(emb_v, mean_vec)
    new_labels = km.predict(emb_norm)

    # Write back into scored
    scored.loc[scored_vv.index, 'cluster_id'] = new_labels
    scored.drop(columns=['_key'], errors='ignore').to_csv(scored_path)
    print(f'Assigned {int(valid.sum())} bills; updated {scored_path}')

    # Update parquet cluster_ids
    key_to_cluster = dict(zip(
        scored['bill_number'].astype(int).map(str) + '_' +
        scored['general_court'].astype(int).map(str),
        scored['cluster_id']
    ))
    parquet_df['cluster_id'] = parquet_df.apply(
        lambda r: key_to_cluster.get(f"{int(r['bill_number'])}_{int(r['general_court'])}", -1),
        axis=1,
    )
    _save_parquet(parquet_df)
    print(f'Done. {int(valid.sum())} new bills assigned to existing clusters.')


def run_relabel(args, parquet_df, scored, scored_path):
    emb, scored, valid = _build_emb_matrix(parquet_df, scored)
    mean_vec = emb[valid].mean(axis=0)
    emb_norm = _preprocess(emb[valid], mean_vec)
    scored_v = scored[valid].reset_index(drop=True)

    labels = scored_v['cluster_id'].values
    n_clusters = int(labels.max()) + 1
    km_centers = np.array([
        emb_norm[labels == c].mean(axis=0) for c in range(n_clusters)
    ])
    _write_labels_and_csv(args, km_centers, labels, scored_v,
                          emb_norm, scored, parquet_df, scored_path)


def _write_labels_and_csv(args, km_centers, labels, scored_v,
                          emb_norm, scored_full, parquet_df, scored_path):
    n_clusters = len(km_centers)
    api_key = _read_api_key() if not args.no_label else None
    client = None
    if not args.no_label:
        import google.genai as genai
        client = genai.Client(api_key=api_key)

    cluster_rows = []
    for cid in range(n_clusters):
        mask = labels == cid
        cluster_bills = scored_v[mask]
        n_bills = int(mask.sum())
        n_env = int(cluster_bills['is_environmental'].sum())

        centroid = km_centers[cid]
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
            'label':      label,
            'n_bills':    n_bills,
            'n_env_bills': n_env,
            'example_titles': ' | '.join(top_titles[:5]),
        })

    labels_df = pd.DataFrame(cluster_rows)
    labels_path = DATA_DIR / 'MA_bill_cluster_labels.csv'
    labels_df.to_csv(labels_path, index=False)

    scored_full.update(scored_v[['cluster_id']])
    scored_full.drop(columns=['_key'], errors='ignore').to_csv(scored_path)

    key_to_cluster = dict(zip(
        scored_full['bill_number'].astype(int).map(str) + '_' +
        scored_full['general_court'].astype(int).map(str),
        scored_full['cluster_id']
    ))
    parquet_df['cluster_id'] = parquet_df.apply(
        lambda r: key_to_cluster.get(f"{int(r['bill_number'])}_{int(r['general_court'])}", -1),
        axis=1,
    )
    _save_parquet(parquet_df)

    print(f'\nWrote cluster assignments to {scored_path}')
    print(f'Wrote cluster labels to {labels_path}')
    print('\nCluster summary:')
    print(labels_df[['cluster_id', 'label', 'n_bills', 'n_env_bills']].to_string(index=False))


# ─── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--n-clusters', type=int, default=N_CLUSTERS_DEFAULT)
    parser.add_argument('--no-label', action='store_true',
                        help='Skip Gemini labeling (use cluster IDs only)')
    parser.add_argument('--relabel', action='store_true',
                        help='Skip re-clustering; only redo Gemini labeling')
    parser.add_argument('--incremental', action='store_true',
                        help='Apply saved model to unassigned bills only (CI-safe, no Gemini)')
    args = parser.parse_args()

    scored_path = DATA_DIR / 'MA_lobbying_bills_scored.csv'
    if not scored_path.exists():
        print('ERROR: Run score_lobbying_bills.py first.')
        return

    parquet_df = _load_parquet()
    scored = pd.read_csv(scored_path, index_col=0)

    if args.incremental:
        run_incremental(parquet_df, scored, scored_path)
    elif args.relabel:
        run_relabel(args, parquet_df, scored, scored_path)
    else:
        run_full(args, parquet_df, scored, scored_path)


if __name__ == '__main__':
    main()
