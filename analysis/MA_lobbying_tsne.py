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
    env_map   = dict(zip(labels_df['cluster_id'].astype(int), labels_df['n_env_bills']))
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

    # One Plotly trace per cluster
    fig = go.Figure()
    cluster_ids = sorted(parquet_df['cluster_id'].unique())

    for cid in cluster_ids:
        mask = parquet_df['cluster_id'] == cid
        sub  = parquet_df[mask]
        lbl  = label_map.get(cid, f'Cluster {cid}')
        n_env = env_map.get(cid, 0)
        n_tot = size_map.get(cid, len(sub))
        color = PALETTE[cid % len(PALETTE)]

        # Mark environmental bills with a ring (open circle marker)
        is_env = sub.get('is_environmental', pd.Series(False, index=sub.index)).fillna(False).astype(bool)

        # Non-environmental points
        if (~is_env).any():
            hover = [
                f'<b>{row.get("bill_title", "")}</b><br>'
                f'GC {int(row["general_court"])} · {lbl}'
                for _, row in sub[~is_env].iterrows()
            ]
            fig.add_trace(go.Scatter(
                x=sub[~is_env]['x'], y=sub[~is_env]['y'],
                mode='markers',
                marker=dict(color=color, size=5, opacity=0.55),
                name=f'{lbl} ({n_tot} bills, {n_env} env)',
                legendgroup=str(cid),
                hovertext=hover,
                hoverinfo='text',
                showlegend=True,
            ))

        # Environmental points — same colour, larger + outlined
        if is_env.any():
            hover_env = [
                f'<b>{row.get("bill_title", "")}</b><br>'
                f'GC {int(row["general_court"])} · {lbl}<br>'
                f'<i>environmental</i>'
                for _, row in sub[is_env].iterrows()
            ]
            fig.add_trace(go.Scatter(
                x=sub[is_env]['x'], y=sub[is_env]['y'],
                mode='markers',
                marker=dict(
                    color=color, size=8, opacity=0.9,
                    line=dict(color='white', width=1),
                ),
                name=f'  ↳ environmental',
                legendgroup=str(cid),
                hovertext=hover_env,
                hoverinfo='text',
                showlegend=False,
            ))

    fig.update_layout(
        title=dict(
            text='MA Lobbying Bills — Topic Clusters (t-SNE projection of Gemini embeddings)',
            font=dict(size=14),
        ),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        legend=dict(
            title='Cluster',
            font=dict(size=11),
            itemsizing='constant',
        ),
        margin=dict(l=10, r=10, t=50, b=10),
        width=800,
        height=550,
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
