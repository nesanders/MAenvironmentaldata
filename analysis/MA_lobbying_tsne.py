"""Generate a t-SNE scatter plot of MA lobbying bill embeddings coloured by topic cluster.

Reads the bill embeddings Parquet (GCS preferred, local fallback), runs t-SNE to
reduce to 2-D, and writes an interactive Plotly HTML to docs/_includes/charts/.

The HTML is self-contained and referenced from the MA_lobbying.md dataset page.

Run from the analysis/ directory:
    /path/to/python -u MA_lobbying_tsne.py

Outputs:
    ../docs/_includes/charts/lobbying_bill_tsne.html
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.manifold import TSNE
from sklearn.preprocessing import normalize
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent))

GCS_PARQUET  = 'gs://openamend-data/MA_bill_embeddings.parquet'
LOCAL_PARQUET = Path('../docs/data/MA_bill_embeddings.parquet')
LABELS_CSV   = Path('../docs/data/MA_bill_cluster_labels.csv')
OUT_HTML     = Path('../docs/_includes/charts/lobbying_bill_tsne.html')

TSNE_PERPLEXITY = 40
TSNE_ITER       = 1000
RANDOM_STATE    = 42

# Colour palette — same 8 cycling colours used in MA_lobbying_viz.py, extended to 15
PALETTE = [
    '#366EB3', '#E68C28', '#3CAA50', '#C83C3C', '#8250C8',
    '#1EA0A0', '#DCB400', '#969696', '#4B8BBE', '#FF7043',
    '#66BB6A', '#EF5350', '#AB47BC', '#26C6DA', '#D4E157',
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

    # Keep only rows that have a cluster assignment
    parquet_df = parquet_df[parquet_df['cluster_id'].notna() &
                            (parquet_df['cluster_id'] != -1)].copy()
    parquet_df['cluster_id'] = parquet_df['cluster_id'].astype(int)
    print(f'{len(parquet_df)} bills with cluster assignments')

    labels_df = pd.read_csv(LABELS_CSV)
    label_map = dict(zip(labels_df['cluster_id'].astype(int), labels_df['label']))
    size_map  = dict(zip(labels_df['cluster_id'].astype(int), labels_df['n_bills']))

    # Build embedding matrix
    emb = np.vstack(parquet_df['embedding'].apply(
        lambda v: np.array(v, dtype=np.float32)
    ).values)
    emb_norm = normalize(emb, norm='l2')

    # t-SNE
    print(f'Running t-SNE (perplexity={TSNE_PERPLEXITY}, iter={TSNE_ITER})...')
    tsne = TSNE(
        n_components=2,
        perplexity=TSNE_PERPLEXITY,
        max_iter=TSNE_ITER,
        random_state=RANDOM_STATE,
        init='pca',
        learning_rate='auto',
    )
    coords = tsne.fit_transform(emb_norm)
    parquet_df = parquet_df.copy()
    parquet_df['x'] = coords[:, 0]
    parquet_df['y'] = coords[:, 1]

    # ── Build traces ────────────────────────────────────────────────────────────
    # Two sub-traces per cluster (non-env + env) sharing a legendgroup so the
    # legend shows one entry per cluster. Each point belongs to exactly one
    # sub-trace, so hover is unambiguous.
    #   non-env: small (5px), muted opacity, no outline
    #   env:     large (10px), full opacity, black outline

    fig = go.Figure()
    cluster_ids = sorted(parquet_df['cluster_id'].unique())

    if 'is_environmental' not in parquet_df.columns:
        parquet_df['is_environmental'] = False
    parquet_df['is_environmental'] = parquet_df['is_environmental'].fillna(False).astype(bool)

    for i, cid in enumerate(cluster_ids):
        mask  = parquet_df['cluster_id'] == cid
        sub   = parquet_df[mask].copy()
        lbl   = label_map.get(cid, f'Cluster {cid}')
        n_tot = size_map.get(cid, len(sub))
        color = PALETTE[cid % len(PALETTE)]

        def _hover(row):
            env_line = '🌿 <b>environmental</b>' if row['is_environmental'] else 'not environmental'
            return (f'<b>{row.get("bill_title", "")}</b><br>'
                    f'GC {int(row["general_court"])} · {lbl}<br>'
                    f'{env_line}')

        non_env = sub[~sub['is_environmental']]
        env     = sub[sub['is_environmental']]

        # Non-environmental sub-trace (muted)
        if not non_env.empty:
            fig.add_trace(go.Scatter(
                x=non_env['x'], y=non_env['y'],
                mode='markers',
                marker=dict(color=color, size=5, opacity=0.35),
                name=f'{lbl} ({n_tot})',
                legendgroup=str(cid),
                legendgrouptitle=dict(text='Topic clusters') if i == 0 else dict(text=''),
                hovertext=[_hover(r) for _, r in non_env.iterrows()],
                hoverinfo='text',
                showlegend=True,
            ))

        # Environmental sub-trace (vivid, outlined) — same legendgroup, no legend entry
        if not env.empty:
            fig.add_trace(go.Scatter(
                x=env['x'], y=env['y'],
                mode='markers',
                marker=dict(
                    color=color, size=10, opacity=1.0,
                    line=dict(color='black', width=1.5),
                ),
                name=f'{lbl} env',
                legendgroup=str(cid),
                hovertext=[_hover(r) for _, r in env.iterrows()],
                hoverinfo='text',
                showlegend=False,
            ))

    # Dummy trace for legend explanation of the env marker style
    fig.add_trace(go.Scatter(
        x=[None], y=[None], mode='markers',
        marker=dict(color='grey', size=10, opacity=1.0,
                    line=dict(color='black', width=1.5)),
        name='Environmental bill',
        legendgroup='env_key',
        legendgrouptitle=dict(text='Marker style'),
        showlegend=True,
    ))
    fig.add_trace(go.Scatter(
        x=[None], y=[None], mode='markers',
        marker=dict(color='grey', size=5, opacity=0.35),
        name='Non-environmental',
        legendgroup='env_key',
        showlegend=True,
    ))

    fig.update_layout(
        title=dict(
            text=(
                'MA Lobbying Bills — Topic Clusters (t-SNE of Gemini embeddings)<br>'
                '<sup>Large outlined dot = environmental · small dot = non-environmental'
                ' · colour = topic cluster · hover for details</sup>'
            ),
            font=dict(size=13),
        ),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        legend=dict(
            font=dict(size=10),
            itemsizing='constant',
            tracegroupgap=10,
        ),
        margin=dict(l=10, r=10, t=65, b=10),
        width=820,
        height=580,
        plot_bgcolor='#f5f5f5',
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
