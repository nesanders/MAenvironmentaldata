"""K-means on summary embeddings for the 495-bill pilot, then recolour UMAP.

Run from get_data/:
    /path/to/python -u cluster_pilot_summaries.py [--k N]
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import normalize

DATA_DIR      = Path('../docs/data')
LOCAL_PARQUET = DATA_DIR / 'MA_bill_embeddings.parquet'
GCS_PARQUET   = 'gs://openamend-data/MA_bill_embeddings.parquet'
LABELS_CSV    = DATA_DIR / 'MA_bill_cluster_labels.csv'
OUT_HTML      = Path('../docs/_includes/charts/lobbying_bill_umap_summary.html')
API_KEY_PATH  = Path('SECRET_GOOGLE_API_KEY')

EMBEDDING_MODEL = 'gemini-embedding-2'
EMBEDDING_DIM   = 768
REQUEST_DELAY   = 0.05

PALETTE_20 = [
    '#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd',
    '#8c564b','#e377c2','#7f7f7f','#bcbd22','#17becf',
    '#aec7e8','#ffbb78','#98df8a','#ff9896','#c5b0d5',
    '#c49c94','#f7b6d2','#c7c7c7','#dbdb8d','#9edae5',
]


def _load_parquet() -> pd.DataFrame:
    try:
        import gcsfs
        fs = gcsfs.GCSFileSystem()
        if fs.exists(GCS_PARQUET):
            with fs.open(GCS_PARQUET, 'rb') as f:
                df = pd.read_parquet(f)
            print(f'Loaded {len(df)} rows from GCS')
            return df
    except Exception as e:
        print(f'GCS failed ({e}), using local')
    df = pd.read_parquet(LOCAL_PARQUET)
    print(f'Loaded {len(df)} rows from local')
    return df


def _embed_one(client, text: str) -> np.ndarray:
    """Embed a single text with exponential backoff; returns zero vector on failure."""
    import random
    import google.genai.types as types
    for attempt in range(6):
        try:
            resp = client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=text,
                config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
            )
            return np.array(resp.embeddings[0].values, dtype=np.float32)
        except Exception as e:
            if attempt == 5:
                print(f'  embed failed: {e}')
                return np.zeros(EMBEDDING_DIM, dtype=np.float32)
            wait = (2 ** attempt) + random.uniform(0, 1)
            time.sleep(wait)
    return np.zeros(EMBEDDING_DIM, dtype=np.float32)


def _embed_texts(client, texts: list[str], workers: int = 8) -> np.ndarray:
    """Embed texts in parallel with a thread pool."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    results = [None] * len(texts)
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_embed_one, client, t): i for i, t in enumerate(texts)}
        for fut in as_completed(futures):
            i = futures[fut]
            results[i] = fut.result()
            done += 1
            if done % 100 == 0:
                print(f'  {done}/{len(texts)} embeddings...', flush=True)
    return np.array(results, dtype=np.float32)


def _label_cluster(client, titles: list[str], k: int) -> str:
    """Ask Gemini for a short topic label given up to 20 central bill titles."""
    import google.genai.types as types
    bullet_list = '\n'.join(f'- {t}' for t in titles[:20])
    prompt = (
        f'These are Massachusetts legislative bill titles from a topic cluster:\n'
        f'{bullet_list}\n\n'
        'Give a concise 3–6 word topic label that describes what these bills have in common. '
        'Reply with just the label, no punctuation or quotes.'
    )
    try:
        resp = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        time.sleep(0.3)
        return resp.text.strip()
    except Exception as e:
        print(f'  label error: {e}')
        return f'Cluster {k}'


def kmeans_sweep(emb_norm: np.ndarray, ks: list[int]) -> dict:
    """Run k-means for each k, return silhouette scores."""
    results = {}
    for k in ks:
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(emb_norm)
        sil = silhouette_score(emb_norm, labels, metric='cosine')
        results[k] = {'sil': sil, 'model': km, 'labels': labels}
        print(f'  k={k:2d}  silhouette={sil:.4f}')
    return results


def make_umap(df_pilot: pd.DataFrame, emb_norm: np.ndarray,
              cluster_labels_arr: np.ndarray, label_map: dict) -> None:
    import umap as umap_lib
    import plotly.graph_objects as go

    is_env = df_pilot['is_env_llm'].fillna(False).astype(bool).values
    n_clusters = len(label_map)

    print(f'Running UMAP (n={len(emb_norm)}, cosine, n_neighbors=15, min_dist=0.1)...')
    reducer = umap_lib.UMAP(
        n_components=2, n_neighbors=15, min_dist=0.1,
        metric='cosine', random_state=42,
    )
    coords = reducer.fit_transform(emb_norm)

    fig = go.Figure()

    # One trace per cluster — non-env (small, semi-transparent) then env (large,
    # outlined) so env dots render on top.  Both use the same cluster colour.
    for cid in sorted(label_map.keys()):
        lbl       = label_map[cid]
        colour    = PALETTE_20[cid % 20]
        clust_mask = cluster_labels_arr == cid

        # Non-env slice
        ne_mask = clust_mask & ~is_env
        if ne_mask.sum():
            ne_df = df_pilot[ne_mask]
            sc    = coords[ne_mask]
            fig.add_trace(go.Scatter(
                x=sc[:, 0], y=sc[:, 1], mode='markers',
                marker=dict(color=colour, size=7, opacity=0.45),
                legendgroup=str(cid),
                showlegend=False,
                name=lbl,
                hovertext=[
                    f'<b>{t}</b><br>{s}<br>cluster: {lbl}'
                    for t, s in zip(
                        ne_df['bill_title'].fillna(''),
                        ne_df['summary'].fillna('').str[:120],
                    )
                ],
                hoverinfo='text',
            ))

        # Env slice — larger, black outline, shown in legend
        e_mask = clust_mask & is_env
        n_env_in_cluster = e_mask.sum()
        e_df = df_pilot[e_mask]
        sc   = coords[e_mask]
        # Always add a trace for the legend entry (even if 0 env bills in cluster)
        legend_label = f'{lbl} ({ne_mask.sum()} / 🌿{n_env_in_cluster})'
        if e_mask.sum():
            fig.add_trace(go.Scatter(
                x=sc[:, 0], y=sc[:, 1], mode='markers',
                marker=dict(color=colour, size=13, opacity=0.95,
                            line=dict(color='black', width=1.2)),
                legendgroup=str(cid),
                showlegend=True,
                name=legend_label,
                hovertext=[
                    f'<b>{row["bill_title"]}</b><br>🌿 env · cluster: {lbl}'
                    f'<br>{str(row.get("summary",""))[:150]}'
                    for _, row in e_df.iterrows()
                ],
                hoverinfo='text',
            ))
        else:
            # Cluster has non-env members but no env — still show in legend
            fig.add_trace(go.Scatter(
                x=[None], y=[None], mode='markers',
                marker=dict(color=colour, size=10),
                legendgroup=str(cid),
                showlegend=True,
                name=legend_label,
            ))

    n_env  = int(is_env.sum())
    n_nenv = int((~is_env).sum())
    fig.update_layout(
        title=dict(text=(
            f'MA Lobbying Bills — Summary Embeddings UMAP (pilot, k={n_clusters})'
            f'<br><sup>{n_env} env (🌿 large, outlined) · {n_nenv} non-env (small) · '
            'coloured by summary-embed cluster · hover for details</sup>'
        ), font=dict(size=13)),
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        legend=dict(font=dict(size=9), itemsizing='constant'),
        margin=dict(l=10, r=10, t=70, b=10),
        width=940, height=660,
        plot_bgcolor='#f4f4f4', paper_bgcolor='white',
        hovermode='closest',
    )
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    html = fig.to_html(full_html=False, include_plotlyjs='cdn', config={'responsive': True})
    OUT_HTML.write_text('{% raw  %}\n' + html + '\n{% endraw %}\n', encoding='utf-8')
    print(f'Wrote {OUT_HTML}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--k', type=int, default=None,
                        help='Fixed k for k-means (default: sweep 4–15 and pick best)')
    parser.add_argument('--skip-embed', action='store_true',
                        help='Load cached summary embeddings from /tmp/pilot_summ_emb.npy')
    args = parser.parse_args()

    api_key = API_KEY_PATH.read_text().strip()
    import google.genai as genai
    client = genai.Client(api_key=api_key)

    df = _load_parquet()
    df_pilot = df[df['summary'].notna()].copy().reset_index(drop=True)
    print(f'{len(df_pilot)} pilot bills with summaries')

    # ── 1. Embed summaries ─────────────────────────────────────────────────────
    # Use stored summary_embedding where available; re-embed only the gaps.
    cache_path = Path('/tmp/pilot_summ_emb.npy')
    n_pilot = len(df_pilot)
    summ_emb = np.zeros((n_pilot, EMBEDDING_DIM), dtype=np.float32)
    needs_embed = np.ones(n_pilot, dtype=bool)

    if 'summary_embedding' in df_pilot.columns:
        for i, v in enumerate(df_pilot['summary_embedding']):
            if v is not None:
                try:
                    arr = np.array(v, dtype=np.float32)
                    if arr.shape == (EMBEDDING_DIM,):
                        summ_emb[i] = arr
                        needs_embed[i] = False
                except Exception:
                    pass
        n_cached = (~needs_embed).sum()
        print(f'  {n_cached}/{n_pilot} summary_embeddings loaded from parquet')

    if args.skip_embed and cache_path.exists() and needs_embed.any():
        cached = np.load(cache_path)
        if cached.shape == (n_pilot, EMBEDDING_DIM):
            summ_emb[needs_embed] = cached[needs_embed]
            needs_embed[:] = False
            print(f'Loaded remaining embeddings from {cache_path}')

    if needs_embed.any():
        n_todo = needs_embed.sum()
        print(f'\nEmbedding {n_todo} summaries (parallel)...')
        todo_texts = df_pilot['summary'].iloc[np.where(needs_embed)[0]].tolist()
        new_embs = _embed_texts(client, todo_texts)
        summ_emb[needs_embed] = new_embs
        np.save(cache_path, summ_emb)
        print(f'Saved embeddings to {cache_path}')
    else:
        print('All embeddings ready from parquet/cache.')

    emb_norm = normalize(summ_emb - summ_emb.mean(axis=0), norm='l2')

    # ── 2. K-means sweep or fixed k ───────────────────────────────────────────
    if args.k:
        chosen_k = args.k
        km = KMeans(n_clusters=chosen_k, random_state=42, n_init=10)
        cluster_ids = km.fit_predict(emb_norm)
        sil = silhouette_score(emb_norm, cluster_ids, metric='cosine')
        print(f'\nk={chosen_k}  silhouette={sil:.4f}')
    else:
        print('\nK-means silhouette sweep...')
        sweep = kmeans_sweep(emb_norm, ks=list(range(4, 16)))
        best_k, best = max(sweep.items(), key=lambda x: x[1]['sil'])
        print(f'\nBest k={best_k}  silhouette={best["sil"]:.4f}')
        chosen_k   = best_k
        km         = best['model']
        cluster_ids = best['labels']

    # ── 3. Label clusters with Gemini ─────────────────────────────────────────
    print(f'\nLabelling {chosen_k} clusters...')
    label_map = {}
    for cid in range(chosen_k):
        mask   = cluster_ids == cid
        titles = df_pilot[mask]['bill_title'].dropna().tolist()
        # Sort by distance to centroid — pick the 20 closest
        dists  = np.linalg.norm(emb_norm[mask] - km.cluster_centers_[cid], axis=1)
        order  = np.argsort(dists)
        central_titles = [titles[i] for i in order[:20] if i < len(titles)]
        label  = _label_cluster(client, central_titles, cid)
        label_map[cid] = label
        print(f'  [{cid:2d}] n={mask.sum():3d}  "{label}"')

    # ── 4. Regenerate UMAP ────────────────────────────────────────────────────
    print('\nGenerating UMAP...')
    make_umap(df_pilot, emb_norm, cluster_ids, label_map)


if __name__ == '__main__':
    main()
