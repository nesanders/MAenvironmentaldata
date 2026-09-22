"""
TESTING SCRIPT — iterating on bill embedding / clustering quality.
NOT part of the production pipeline. DO NOT run in CI.

Purpose:
  Rapid iteration on text preprocessing and clustering parameters using a
  stratified sample of ~1,000 bills. Produces a standalone t-SNE HTML you
  can open in a browser to visually assess cluster quality.

  Key hypotheses being tested:
    1. Strip repeated legislative scaffolding ("is hereby amended by inserting
       after...") before embedding — these trigrams dominate the 2000-char window
       and pull unrelated bills toward the same region of embedding space.
    2. Prepend the bill title to the cleaned text — titles are high-signal and
       currently dropped when full text is available.
    3. Expand the text window from 2,000 to 3,000 chars (more signal after stripping).
    4. Increase k from 15 to 25 clusters — coarse k merges topic-coherent sub-groups.

Usage (from get_data/):
    /path/to/python -u test_embedding_pipeline.py [--sample N] [--k K]
                                                   [--no-strip] [--no-title-prefix]
                                                   [--max-chars N] [--out PATH]

Outputs:
    /tmp/test_tsne_<tag>.html   — interactive Plotly t-SNE (open in browser)
    /tmp/test_embeddings.parquet — cached embeddings for fast re-runs with same sample

Imports from production scripts where possible; does NOT write to any
production data files (docs/data/, GCS, MA_bill_embeddings.parquet).
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from sklearn.cluster import KMeans
from sklearn.manifold import TSNE
from sklearn.preprocessing import normalize

# ── Import from production scripts ─────────────────────────────────────────────
# Add get_data/ to path so we can import helpers directly
sys.path.insert(0, str(Path(__file__).parent))
from score_lobbying_bills import (   # noqa: E402
    _embed_texts,
    _make_client,
    _read_api_key,
    _cosine_sim,
    ENV_EXAMPLE_BILLS,
    NON_ENV_EXAMPLE_BILLS,
    ENV_THRESHOLD,
)
from cluster_lobbying_bills import _label_cluster  # noqa: E402

# ── Paths ───────────────────────────────────────────────────────────────────────
DATA_DIR   = Path('../docs/data')
CACHE_DIR  = Path('MA_legislature_cache')
API_KEY    = Path('SECRET_GOOGLE_API_KEY')

# ── Boilerplate patterns to strip before embedding ──────────────────────────────
# Ordered from most specific to most general so broader patterns don't shadow
# narrower ones. Each is stripped globally from the text.
_SCAFFOLD_PATTERNS = [
    # "Chapter 21E of the General Laws, as appearing in the 2020 Official Edition,"
    r'(?:Chapter|Section|Part)\s+\w+(?:\s+of\s+(?:chapter\s+\w+\s+of\s+)?the\s+General\s+Laws)?'
    r'(?:,\s+as\s+(?:appearing|so\s+appearing|amended)[^,\n]{0,80})?'
    r',?\s+is\s+hereby\s+amended\s+by\s+(?:inserting|striking|adding|deleting)[^\n]{0,120}',
    # "as appearing in the 20XX Official Edition"
    r'as\s+(?:so\s+)?appearing\s+in\s+the\s+\d{4}\s+Official\s+Edition',
    # bare "is hereby amended by"
    r'is\s+hereby\s+amended\s+by\s+(?:inserting|striking|adding|deleting)\s+\w+\s+\w+',
    # "in place thereof the following words:-" / "the following section:-"
    r'(?:in\s+place\s+thereof|thereof)\s+the\s+following\s+(?:words|section|clause|paragraph)[:\-\s]{0,5}',
    # "SECTION N." header lines (keep the number but not the structural label)
    r'\bSECTION\s+\d+\.\s+',
    # "of the General Laws" alone
    r'\bof\s+the\s+General\s+Laws\b',
    # "in line N, the words" amendment locators
    r'in\s+line\s+\d+(?:\s+through\s+\d+)?,?\s+the\s+words?\s+"[^"]{0,60}"',
]
_SCAFFOLD_RE = re.compile(
    '|'.join(_SCAFFOLD_PATTERNS),
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r'\s{2,}')


def clean_bill_text(raw: str, max_chars: int = 3000) -> str:
    """Strip legislative scaffolding and normalise whitespace."""
    cleaned = _SCAFFOLD_RE.sub(' ', raw)
    cleaned = _WHITESPACE_RE.sub(' ', cleaned).strip()
    return cleaned[:max_chars]


def build_embed_text(title: str, raw_text: str,
                     strip: bool = True,
                     title_prefix: bool = True,
                     max_chars: int = 3000) -> str:
    """
    Construct the string to feed to the embedding model.

    Parameters
    ----------
    title        : bill title from the portal (always present)
    raw_text     : DocumentText from the legislature cache (may be empty)
    strip        : whether to apply clean_bill_text()
    title_prefix : whether to prepend the title to the cleaned body
    max_chars    : character budget for the body text (after stripping)
    """
    if raw_text and raw_text.strip():
        body = clean_bill_text(raw_text, max_chars) if strip else raw_text[:max_chars]
        if title_prefix and title:
            return f'{title.strip()}\n\n{body}'
        return body
    # No full text — fall back to title only
    return title or ''


# ── Data loading ────────────────────────────────────────────────────────────────

def load_sample(n: int = 1000, seed: int = 42) -> pd.DataFrame:
    """
    Return a stratified sample of n bills from MA_lobbying_bills_scored.csv.
    Stratifies on is_environmental to guarantee env bills are represented.
    """
    scored = pd.read_csv(DATA_DIR / 'MA_lobbying_bills_scored.csv', index_col=0)
    scored = scored.dropna(subset=['bill_number', 'general_court'])
    scored['bill_number'] = scored['bill_number'].astype(int)
    scored['general_court'] = scored['general_court'].astype(int)

    env   = scored[scored['is_environmental'] == True]
    other = scored[scored['is_environmental'] != True]

    rng = np.random.default_rng(seed)
    n_env   = min(len(env),   max(50, int(n * len(env) / len(scored))))
    n_other = min(len(other), n - n_env)

    sample = pd.concat([
        env.iloc[rng.choice(len(env),   n_env,   replace=False)],
        other.iloc[rng.choice(len(other), n_other, replace=False)],
    ]).reset_index(drop=True)
    print(f'Sample: {len(sample)} bills ({n_env} env, {n_other} non-env)')
    return sample


def get_raw_text(bill_id, general_court: int) -> str:
    """Read DocumentText from legislature cache; empty string if unavailable."""
    if not bill_id or str(bill_id) == 'nan':
        return ''
    cache = CACHE_DIR / f'bill_{int(general_court)}_{bill_id}.json'
    if not cache.exists():
        return ''
    try:
        return json.loads(cache.read_text(encoding='utf-8')).get('DocumentText') or ''
    except Exception:
        return ''


# ── Main ────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--sample',         type=int,  default=1000,
                    help='Number of bills to sample (default: 1000)')
    ap.add_argument('--k',              type=int,  default=25,
                    help='Number of k-means clusters (default: 25)')
    ap.add_argument('--no-strip',       action='store_true',
                    help='Disable boilerplate stripping (baseline comparison)')
    ap.add_argument('--no-title-prefix', action='store_true',
                    help='Do not prepend title to body text')
    ap.add_argument('--max-chars',      type=int,  default=3000,
                    help='Character budget for body text after stripping (default: 3000)')
    ap.add_argument('--cache',          type=Path,
                    default=Path('/tmp/test_embeddings.parquet'),
                    help='Parquet cache for embeddings (reused if sample/settings match)')
    ap.add_argument('--no-cache',       action='store_true',
                    help='Ignore cached embeddings and re-embed from scratch')
    ap.add_argument('--out',            type=Path, default=None,
                    help='Output HTML path (default: /tmp/test_tsne_<tag>.html)')
    ap.add_argument('--no-label',       action='store_true',
                    help='Skip Gemini cluster labeling (use cluster IDs only, faster)')
    args = ap.parse_args()

    strip   = not args.no_strip
    prefix  = not args.no_title_prefix
    tag_parts = [
        f'n{args.sample}',
        f'k{args.k}',
        f'chars{args.max_chars}',
        'strip' if strip else 'nostrip',
        'title' if prefix else 'notitle',
    ]
    tag = '_'.join(tag_parts)
    out_html = args.out or Path(f'/tmp/test_tsne_{tag}.html')

    print(f'=== Embedding test: {tag} ===')
    print(f'  strip={strip}  title_prefix={prefix}  max_chars={args.max_chars}')
    print(f'  k={args.k}  sample={args.sample}')
    print(f'  output → {out_html}')
    print()

    # ── Sample ────────────────────────────────────────────────────────────────
    sample = load_sample(args.sample)

    # ── Try to reuse cached embeddings ────────────────────────────────────────
    cached_emb: np.ndarray | None = None
    cache_meta: dict = {}
    if not args.no_cache and args.cache.exists():
        try:
            cdf = pd.read_parquet(args.cache)
            cache_meta = json.loads(cdf.attrs.get('meta', '{}'))
            if (cache_meta.get('tag') == tag and
                    len(cdf) == len(sample) and
                    set(cdf['bill_number'].astype(int)) == set(sample['bill_number'].astype(int))):
                cached_emb = np.vstack(cdf['embedding'].apply(
                    lambda v: np.array(v, dtype=np.float32)).values)
                print(f'Reusing cached embeddings from {args.cache}  ({len(cdf)} rows)')
            else:
                print(f'Cache mismatch (tag or sample changed) — re-embedding')
        except Exception as e:
            print(f'Cache load failed ({e}) — re-embedding')

    # ── Embed ─────────────────────────────────────────────────────────────────
    if cached_emb is None:
        api_key = _read_api_key()
        client  = _make_client(api_key)

        texts = []
        n_with_text = 0
        for _, row in sample.iterrows():
            raw = get_raw_text(row.get('bill_id'), row['general_court'])
            if raw:
                n_with_text += 1
            texts.append(build_embed_text(
                title=str(row.get('bill_title') or ''),
                raw_text=raw,
                strip=strip,
                title_prefix=prefix,
                max_chars=args.max_chars,
            ))

        print(f'{n_with_text}/{len(sample)} bills have cached full text')

        # Show a before/after strip example
        if strip:
            raw_ex = get_raw_text(sample.iloc[0].get('bill_id'),
                                  sample.iloc[0]['general_court'])
            if raw_ex:
                cleaned_ex = clean_bill_text(raw_ex, args.max_chars)
                print(f'\n-- Strip example (bill {sample.iloc[0]["bill_id"]}) --')
                print(f'  RAW    first 300: {repr(raw_ex[:300])}')
                print(f'  CLEAN  first 300: {repr(cleaned_ex[:300])}')
                print()

        print(f'Embedding {len(texts)} bills...')
        cached_emb = _embed_texts(client, texts)

        # Save to parquet cache
        cdf = sample[['bill_number', 'general_court', 'bill_title',
                       'bill_id', 'is_environmental']].copy()
        cdf['embedding'] = [cached_emb[i].tolist() for i in range(len(cached_emb))]
        cdf.attrs['meta'] = json.dumps({'tag': tag})
        cdf.to_parquet(args.cache, index=False)
        print(f'Saved embeddings to {args.cache}')

    # ── Drop zero-vector rows before clustering ───────────────────────────────
    # Bills with no title and no cached text embed as all-zeros; they cluster
    # together arbitrarily and hover as "nan". Assign cluster_id=-1 and exclude.
    norms = np.linalg.norm(cached_emb, axis=1)
    valid = norms > 0.01
    n_zero = int((~valid).sum())
    if n_zero:
        print(f'  Excluding {n_zero} zero-vector bills (no title/text) from clustering')
    sample['cluster_id'] = -1
    sample_valid  = sample[valid].reset_index(drop=True)
    emb_valid     = cached_emb[valid]
    emb_norm      = normalize(emb_valid, norm='l2')

    # ── Score env relevance with current example sets ─────────────────────────
    print('Scoring env relevance...')
    api_key = _read_api_key()
    client  = _make_client(api_key)
    env_emb     = _embed_texts(client, ENV_EXAMPLE_BILLS)
    non_env_emb = _embed_texts(client, NON_ENV_EXAMPLE_BILLS)
    diff = _cosine_sim(emb_valid, env_emb).max(axis=1) - \
           _cosine_sim(emb_valid, non_env_emb).max(axis=1)
    sample_valid = sample_valid.copy()
    sample_valid['env_score_new'] = diff
    sample_valid['is_env_new']    = diff >= ENV_THRESHOLD
    n_env_new = sample_valid['is_env_new'].sum()
    print(f'  {n_env_new}/{len(sample_valid)} bills flagged env '
          f'(threshold={ENV_THRESHOLD})')

    # ── Cluster ───────────────────────────────────────────────────────────────
    print(f'Clustering into {args.k} clusters (k-means)...')
    km     = KMeans(n_clusters=args.k, random_state=42, n_init=10)
    labels = km.fit_predict(emb_norm)
    sample_valid['cluster_id'] = labels

    # ── Label clusters ────────────────────────────────────────────────────────
    cluster_labels: dict[int, str] = {}
    if not args.no_label:
        print('Labeling clusters with Gemini...')
        for cid in range(args.k):
            mask       = labels == cid
            sub        = sample_valid[mask]
            n_bills    = mask.sum()
            n_env      = int(sub['is_env_new'].sum())
            centroid   = km.cluster_centers_[cid]
            dists      = np.linalg.norm(emb_norm[mask] - centroid, axis=1)
            top_idx    = np.argsort(dists)[:20]
            top_titles = sub.iloc[top_idx]['bill_title'].fillna('').tolist()
            try:
                label = _label_cluster(client, top_titles, cid)
            except Exception as e:
                label = f'Cluster {cid}'
                print(f'  Gemini error on cluster {cid}: {e}')
            cluster_labels[cid] = label
            print(f'  Cluster {cid:2d}: "{label}" ({n_bills} bills, {n_env} env)')
    else:
        for cid in range(args.k):
            sub   = sample_valid[labels == cid]
            n_env = int(sub['is_env_new'].sum())
            cluster_labels[cid] = f'C{cid} ({n_env} env)'
        print('Skipped Gemini labeling (--no-label)')

    # ── t-SNE ─────────────────────────────────────────────────────────────────
    print('Running t-SNE...')
    tsne   = TSNE(n_components=2, perplexity=min(40, len(sample_valid) // 10),
                  max_iter=1000, random_state=42, init='pca', learning_rate='auto')
    coords = tsne.fit_transform(emb_norm)
    sample_valid['x'] = coords[:, 0]
    sample_valid['y'] = coords[:, 1]

    # ── Plot ──────────────────────────────────────────────────────────────────
    PALETTE = [
        '#366EB3', '#E68C28', '#3CAA50', '#C83C3C', '#8250C8',
        '#1EA0A0', '#DCB400', '#969696', '#4B8BBE', '#FF7043',
        '#66BB6A', '#EF5350', '#AB47BC', '#26C6DA', '#D4E157',
        '#FF8A65', '#A5D6A7', '#CE93D8', '#80DEEA', '#FFCC80',
        '#BCAAA4', '#90CAF9', '#F48FB1', '#C5E1A5', '#B39DDB',
    ]

    fig = go.Figure()
    for cid in range(args.k):
        mask    = sample_valid['cluster_id'] == cid
        sub     = sample_valid[mask]
        lbl     = cluster_labels.get(cid, f'Cluster {cid}')
        color   = PALETTE[cid % len(PALETTE)]
        non_env = sub[~sub['is_env_new']]
        env     = sub[sub['is_env_new']]

        def _hover(row, lbl=lbl):
            title   = row.get('bill_title', '') or f'Bill {row["bill_number"]}'
            env_str = '🌿 env' if row['is_env_new'] else ''
            return (f'<b>{title}</b><br>'
                    f'{lbl} · GC {int(row["general_court"])}<br>'
                    f'env_score={row["env_score_new"]:.3f} {env_str}')

        if not non_env.empty:
            fig.add_trace(go.Scatter(
                x=non_env['x'], y=non_env['y'], mode='markers',
                marker=dict(color=color, size=5, opacity=0.4),
                name=f'{lbl} ({mask.sum()})',
                legendgroup=str(cid),
                hovertext=[_hover(r) for _, r in non_env.iterrows()],
                hoverinfo='text', showlegend=True,
            ))
        if not env.empty:
            fig.add_trace(go.Scatter(
                x=env['x'], y=env['y'], mode='markers',
                marker=dict(color=color, size=11, opacity=1.0,
                            line=dict(color='black', width=1.5)),
                name=f'{lbl} env',
                legendgroup=str(cid),
                hovertext=[_hover(r) for _, r in env.iterrows()],
                hoverinfo='text', showlegend=False,
            ))

    title_str = (
        f'EMBEDDING TEST — n={args.sample} · k={args.k} · '
        f'strip={strip} · title_prefix={prefix} · max_chars={args.max_chars}<br>'
        f'<sup>Large outlined = environmental · small = non-env · hover for details</sup>'
    )
    fig.update_layout(
        title=dict(text=title_str, font=dict(size=12)),
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        legend=dict(font=dict(size=9), itemsizing='constant'),
        margin=dict(l=10, r=10, t=75, b=10),
        width=1000, height=650,
        plot_bgcolor='#f5f5f5', paper_bgcolor='white',
        hovermode='closest',
    )

    out_html.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(out_html), include_plotlyjs='cdn')
    print(f'\nWrote → {out_html}')
    print(f'Open in browser:  xdg-open {out_html}')


if __name__ == '__main__':
    main()
