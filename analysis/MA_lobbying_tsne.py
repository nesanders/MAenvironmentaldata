"""Generate a UMAP scatter plot of MA lobbying bill embeddings.

Visual design philosophy
─────────────────────────
MA legislative bill embeddings are semantically dense — all bills share heavy
regulatory language, so inter-cluster cosine distances are ~0.006 vs.
intra-cluster spread of ~0.53. Running t-SNE on all 25k bills produces a
featureless blob regardless of perplexity, because the structure simply doesn't
separate in 2-D.

UMAP is used instead of t-SNE because it better preserves global structure,
pulling weakly-separated clusters apart more effectively than t-SNE's purely
local optimisation. Parameters: n_neighbors=30, min_dist=0.1, metric='cosine'.

The chart shows TWO layers:

  Background (grey)  — stratified sample of ~120 non-environmental bills per
                        cluster, rendered as tiny translucent grey dots. Provides
                        geographic context for the policy landscape.

  Signal (coloured)  — all env-relevant bills (~654), one colour per cluster,
                        large outlined dots. These are what the visitor cares about.

UMAP is computed on the combined ~3,650 point sample (all env + background),
which runs in ~30s and produces cleaner structure than t-SNE on this corpus.

Run from the analysis/ directory:
    /path/to/python -u MA_lobbying_tsne.py

Outputs:
    ../docs/_includes/charts/lobbying_bill_tsne.html
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import umap
from sklearn.preprocessing import normalize
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent))

GCS_PARQUET   = 'gs://openamend-data/MA_bill_embeddings.parquet'
LOCAL_PARQUET = Path('../docs/data/MA_bill_embeddings.parquet')
LABELS_CSV    = Path('../docs/data/MA_bill_cluster_labels.csv')
OUT_HTML      = Path('../docs/_includes/charts/lobbying_bill_tsne.html')

# Non-env bills sampled per cluster for background context.
# 120 × 25 clusters ≈ 3 000 background points + ~329 env = ~3 300 total.
BG_PER_CLUSTER  = 120
RANDOM_STATE    = 42

# UMAP hyperparameters
UMAP_N_NEIGHBORS = 30   # larger → more global structure
UMAP_MIN_DIST    = 0.1  # smaller → tighter clusters
UMAP_METRIC      = 'cosine'

# 25-colour palette — qualitative, perceptually distinct, no cycling
PALETTE_25 = [
    '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
    '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
    '#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5',
    '#c49c94', '#f7b6d2', '#c7c7c7', '#dbdb8d', '#9edae5',
    '#393b79', '#637939', '#8c6d31', '#843c39', '#7b4173',
]


def _load_parquet() -> pd.DataFrame:
    try:
        import gcsfs
        fs = gcsfs.GCSFileSystem()
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


def main():
    parquet_df = _load_parquet()

    # Restrict to clustered bills
    parquet_df = parquet_df[
        parquet_df['cluster_id'].notna() & (parquet_df['cluster_id'] != -1)
    ].copy()
    parquet_df['cluster_id'] = parquet_df['cluster_id'].astype(int)

    if 'is_environmental' not in parquet_df.columns:
        parquet_df['is_environmental'] = False
    parquet_df['is_environmental'] = parquet_df['is_environmental'].fillna(False).astype(bool)

    labels_df = pd.read_csv(LABELS_CSV, engine='python', on_bad_lines='skip')
    # example_titles may contain unquoted commas that corrupt row parsing;
    # keep only rows with a valid integer cluster_id.
    labels_df = labels_df[
        pd.to_numeric(labels_df['cluster_id'], errors='coerce').notna()
    ].copy()
    labels_df['cluster_id'] = labels_df['cluster_id'].astype(int)
    label_map = dict(zip(labels_df['cluster_id'].astype(int), labels_df['label']))
    nenv_map  = dict(zip(labels_df['cluster_id'].astype(int), labels_df['n_env_bills']))

    # ── Build subsample ──────────────────────────────────────────────────────
    # Keep ALL env bills; sample BG_PER_CLUSTER non-env bills per cluster.
    env_df  = parquet_df[parquet_df['is_environmental']].copy()
    non_env = parquet_df[~parquet_df['is_environmental']]

    rng = np.random.default_rng(RANDOM_STATE)
    bg_parts = []
    for cid in sorted(non_env['cluster_id'].unique()):
        sub = non_env[non_env['cluster_id'] == cid]
        n   = min(BG_PER_CLUSTER, len(sub))
        bg_parts.append(sub.sample(n=n, random_state=int(rng.integers(0, 2**31))))

    bg_df  = pd.concat(bg_parts, ignore_index=True)
    sample = pd.concat([env_df, bg_df], ignore_index=True)
    print(f'Subsample: {len(env_df)} env + {len(bg_df)} background = {len(sample)} total')

    # ── Embeddings ───────────────────────────────────────────────────────────
    emb      = np.vstack(sample['embedding'].apply(
        lambda v: np.array(v, dtype=np.float32)
    ).values)
    emb_norm = normalize(emb, norm='l2')

    # ── UMAP ─────────────────────────────────────────────────────────────────
    print(f'Running UMAP (n={len(sample)}, n_neighbors={UMAP_N_NEIGHBORS}, '
          f'min_dist={UMAP_MIN_DIST}, metric={UMAP_METRIC})...')
    reducer = umap.UMAP(
        n_components=2,
        n_neighbors=UMAP_N_NEIGHBORS,
        min_dist=UMAP_MIN_DIST,
        metric=UMAP_METRIC,
        random_state=RANDOM_STATE,
        low_memory=False,
    )
    coords  = reducer.fit_transform(emb_norm)
    sample  = sample.copy()
    sample['x'] = coords[:, 0]
    sample['y'] = coords[:, 1]

    # ── Build Plotly figure ──────────────────────────────────────────────────
    fig = go.Figure()

    bg   = sample[~sample['is_environmental']]
    envs = sample[sample['is_environmental']]

    # Layer 1 — grey background (all non-env, single trace for performance)
    fig.add_trace(go.Scatter(
        x=bg['x'], y=bg['y'],
        mode='markers',
        marker=dict(color='#aaaaaa', size=4, opacity=0.20),
        name='Non-environmental bills',
        hovertext=[
            f'<b>{row.get("bill_title", "")}</b><br>'
            f'GC {int(row["general_court"])} · {label_map.get(int(row["cluster_id"]), "")}'
            for _, row in bg.iterrows()
        ],
        hoverinfo='text',
        showlegend=True,
        legendgroup='bg',
        legendgrouptitle=dict(text='Background'),
    ))

    # Layer 2 — env bills, one trace per cluster that has any env bills
    env_cluster_ids = sorted(envs['cluster_id'].unique())
    for i, cid in enumerate(env_cluster_ids):
        sub  = envs[envs['cluster_id'] == cid]
        lbl  = label_map.get(cid, f'Cluster {cid}')
        nenv = nenv_map.get(cid, len(sub))
        color = PALETTE_25[cid % len(PALETTE_25)]

        fig.add_trace(go.Scatter(
            x=sub['x'], y=sub['y'],
            mode='markers',
            marker=dict(
                color=color, size=11, opacity=0.92,
                line=dict(color='black', width=1.2),
            ),
            name=f'{lbl} ({nenv} env)',
            hovertext=[
                f'<b>{row.get("bill_title", "")}</b><br>'
                f'GC {int(row["general_court"])} · 🌿 environmental<br>'
                f'Cluster: {lbl}<br>'
                f'Score: {row.get("env_relevance_score", ""):.3f}'
                for _, row in sub.iterrows()
            ],
            hoverinfo='text',
            showlegend=True,
            legendgroup='env',
            legendgrouptitle=dict(text='Environmental bills by cluster') if i == 0 else dict(text=''),
        ))

    fig.update_layout(
        title=dict(
            text=(
                'MA Lobbying Bills — Environmental Bills in the Policy Landscape'
                f'<br><sup>Coloured = {len(envs)} environmentally-relevant bills · '
                f'grey = background sample ({len(bg):,} non-env) · '
                'colour = topic cluster · hover for details · UMAP projection</sup>'
            ),
            font=dict(size=13),
        ),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        legend=dict(
            font=dict(size=10),
            itemsizing='constant',
            tracegroupgap=8,
        ),
        margin=dict(l=10, r=10, t=70, b=10),
        width=880,
        height=600,
        plot_bgcolor='#f8f8f8',
        paper_bgcolor='white',
        hovermode='closest',
    )

    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    html = fig.to_html(full_html=False, include_plotlyjs='cdn', config={'responsive': True})
    OUT_HTML.write_text(
        '{% raw  %}\n' + html + '\n{% endraw %}\n',
        encoding='utf-8',
    )
    print(f'Wrote {OUT_HTML}')


if __name__ == '__main__':
    main()
