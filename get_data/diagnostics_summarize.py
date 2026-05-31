"""Diagnostics for summarize_lobbying_bills.py pilot output.

Runs after summarize_lobbying_bills.py --sample N and produces:

  1. Env precision/recall on the known reference sets
  2. LLM vs embedding disagreement analysis
  3. Summary quality stats (thin-text bills, tag validity)
  4. Token/cost breakdown by GC and body-text length
  5. Silhouette comparison: original embedding vs summary embedding
  6. UMAP visualisation using summary embeddings (env + borderline)
  7. Written report appended to NOTES_bill_embeddings.md

Run from get_data/:
    /path/to/python -u diagnostics_summarize.py [--sample-size 500]
"""

import argparse
import io
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import normalize

DATA_DIR      = Path('../docs/data')
API_KEY_PATH  = Path('SECRET_GOOGLE_API_KEY')
GCS_PARQUET   = 'gs://openamend-data/MA_bill_embeddings.parquet'
LOCAL_PARQUET = DATA_DIR / 'MA_bill_embeddings.parquet'
LABELS_CSV    = DATA_DIR / 'MA_bill_cluster_labels.csv'
NOTES_MD      = Path('NOTES_bill_embeddings.md')
OUT_HTML      = Path('../docs/_includes/charts/lobbying_bill_umap_summary.html')

EMBEDDING_MODEL = 'gemini-embedding-2'
EMBEDDING_DIM   = 768
REQUEST_DELAY   = 0.05
EMBED_BATCH     = 50

# Pricing (Gemini 2.5 Flash non-thinking)
PRICE_INPUT        = 0.075   / 1_000_000
PRICE_INPUT_CACHED = 0.01875 / 1_000_000
PRICE_OUTPUT       = 0.300   / 1_000_000

# Reference sets from score_lobbying_bills.py
ENV_REFERENCE = [
    'An Act to protect Massachusetts public health from PFAS',
    'An Act relative to solid waste disposal facilities in environmental justice communities',
    'An Act relative to the remediation of home heating oil releases',
    'An Act relative to the cleanup of accidental home heating oil spills',
    'An Act relative to proper disposal of products containing PFAS',
    'An Act relative to certain manufactured chemicals known as PFAS',
    'An Act relative to chemical recycling',
    'An Act ensuring a healthy future for environmental justice communities',
    'An Act relative to protecting our waterways',
    'An Act protecting our soil and farms from PFAS contamination',
    'An Act relative to liability for release of hazardous materials',
    'An Act relative to landfills and areas of critical environmental concern',
    'An Act relative to maintaining adequate water supplies through effective drought management',
    'Monitor the adoption and implementation of the Low Emission Vehicle Program',
    'An Act relative to stormwater management',
    'An Act relative to clean energy and climate resilience',
    'An Act relative to reducing greenhouse gas emissions',
    'An Act relative to wetlands protection',
    'An Act relative to air quality standards',
    'An Act relative to ocean and coastal resource management',
]

NON_ENV_REFERENCE = [
    'An Act requiring one fair wage',
    'An Act clarifying the process for paying the wages of dismissed employees',
    'An Act to establish a hospital and community health center worker minimum wage',
    'An Act relative to equitable pay in the public sector',
    'An Act to prohibit carrying firearms in sensitive places',
    'An Act further defining a hate crime',
    'An Act limiting autonomous driving capabilities to zero emission and electric vehicles',
    'An Act relative to disability pensions for violent crimes',
    'An Act to improve sickle cell care',
    'An Act to promote the recruitment and retention of hospital workers',
    'An Act to ensure consumer cost protection under the dental medical loss ratio',
    'An Act alleviating the burden of medical debt for patients and families',
    'An Act relative to improving the outcomes for sudden cardiac arrest in the Commonwealth',
    'An Act requiring full health insurance coverage for individuals with vitiligo',
    'An Act to modernize the Massachusetts insurer insolvency fund',
    'An Act establishing a college tuition tax deduction',
    'An Act to support educational opportunity for all',
    'An Act protecting against attempts to ban remove or restrict library access to materials',
    'An Act relative to charter schools',
    'An Act to lift kids out of deep poverty',
    'An Act establishing a tax credit for families caring for elderly relatives',
    'An Act to require equitable payment from the Commonwealth',
    'An Act relative to the Affordable Homes Act',
    'An Act making appropriations for the fiscal year for the maintenance of the departments of the commonwealth',
    'An Act relative to liquor licenses in the city of Westfield',
    'An Act authorizing the town of Wrentham to grant additional licenses for the sale of alcoholic beverages',
    'Supporting Local Services',
    'An Act providing incentives to the digital interactive media and entertainment industries',
    'An Act to establish a digital advertising revenue commission',
    'An Act relative to legal advertisements in online-only newspapers',
    'An Act relative to access to a decedent electronic mail accounts',
    'An Act to modify the rules for taking depositions outside the Commonwealth',
    'An Act to prohibit the sale of energy drinks to persons under the age of 18',
    'An Act relative to LGBTQ family building',
    'An Act to preserve the eternal bonds between people and their animals',
    'An Act protecting the right to time off for voting',
]

PALETTE_25 = [
    '#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd',
    '#8c564b','#e377c2','#7f7f7f','#bcbd22','#17becf',
    '#aec7e8','#ffbb78','#98df8a','#ff9896','#c5b0d5',
    '#c49c94','#f7b6d2','#c7c7c7','#dbdb8d','#9edae5',
    '#393b79','#637939','#8c6d31','#843c39','#7b4173',
]


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _gcs_fs():
    import gcsfs
    return gcsfs.GCSFileSystem()


def _load_parquet() -> pd.DataFrame:
    try:
        fs = _gcs_fs()
        if fs.exists(GCS_PARQUET):
            with fs.open(GCS_PARQUET, 'rb') as f:
                df = pd.read_parquet(f)
            print(f'Loaded {len(df)} rows from GCS')
            return df
    except OSError as e:
        print(f'GCS failed ({e}), using local')
    df = pd.read_parquet(LOCAL_PARQUET)
    print(f'Loaded {len(df)} rows from local parquet')
    return df


def _embed_texts(client, texts: list[str]) -> np.ndarray:
    """Embed a list of strings one at a time; return (N, 768) float32 array."""
    import google.genai.types as types
    vecs = []
    for text in texts:
        for attempt in range(5):
            try:
                resp = client.models.embed_content(
                    model=EMBEDDING_MODEL,
                    contents=text,
                    config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
                )
                vecs.append(resp.embeddings[0].values)
                time.sleep(REQUEST_DELAY)
                break
            except Exception as e:
                wait = 2 ** attempt
                print(f'    embed error ({e}), retry in {wait}s...')
                time.sleep(wait)
        else:
            print(f'    embed failed after 5 attempts, using zero vector')
            vecs.append([0.0] * EMBEDDING_DIM)
        if len(vecs) % 50 == 0:
            print(f'    {len(vecs)}/{len(texts)} embeddings...', flush=True)
    return np.array(vecs, dtype=np.float32)


def _call_env_classify(client, title: str) -> bool:
    """Ask the LLM whether a given bill title is environmental. Returns True/False."""
    import google.genai.types as types
    from pydantic import BaseModel as PB

    class EnvResult(PB):
        is_environmental: bool

    prompt = (
        f'Bill title: "{title}"\n\n'
        'Is this Massachusetts bill primarily about environmental protection, '
        'clean energy, renewable energy, climate change, pollution, solid waste, '
        'recycling, water quality, wetlands, natural resources, forests, fisheries, '
        'or wildlife? Reply with a JSON object: {"is_environmental": true/false}'
    )
    try:
        resp = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type='application/json',
                response_schema=EnvResult,
                temperature=0,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        time.sleep(0.3)
        return resp.parsed.is_environmental
    except OSError:
        return None


# ─── Diagnostic sections ───────────────────────────────────────────────────────

def diag_reference_set(client) -> dict:
    """Run the env/non-env reference titles through the LLM classifier."""
    print('\n── 1. Reference set precision/recall ─────────────────────────')
    env_results, non_env_results = [], []

    print(f'Classifying {len(ENV_REFERENCE)} env reference titles...')
    for title in ENV_REFERENCE:
        result = _call_env_classify(client, title)
        env_results.append((title, result))
        print(f'  {"✓" if result else "✗"} {title[:70]}')

    print(f'\nClassifying {len(NON_ENV_REFERENCE)} non-env reference titles...')
    for title in NON_ENV_REFERENCE:
        result = _call_env_classify(client, title)
        non_env_results.append((title, result))
        print(f'  {"✗ FP!" if result else "✓"} {title[:70]}')

    recall    = sum(1 for _, r in env_results if r) / len(env_results)
    precision_denom = len(NON_ENV_REFERENCE)
    fp        = sum(1 for _, r in non_env_results if r)
    specificity = 1 - fp / precision_denom

    fn_titles = [t for t, r in env_results if not r]
    fp_titles = [t for t, r in non_env_results if r]

    print(f'\nRecall:      {recall:.0%}  ({sum(1 for _,r in env_results if r)}/{len(env_results)} env correctly flagged)')
    print(f'Specificity: {specificity:.0%}  ({fp} false positives out of {precision_denom} non-env)')
    if fn_titles:
        print(f'False negatives (missed env): {fn_titles}')
    if fp_titles:
        print(f'False positives (wrong non-env): {fp_titles}')

    return {
        'recall': recall,
        'specificity': specificity,
        'false_negatives': fn_titles,
        'false_positives': fp_titles,
    }


def diag_disagreements(df_pilot: pd.DataFrame) -> dict:
    """Compare LLM vs embedding env classification on the pilot sample."""
    print('\n── 2. LLM vs embedding disagreement analysis ──────────────────')
    has_both = df_pilot[df_pilot['is_env_llm'].notna() & df_pilot['is_environmental'].notna()].copy()
    has_both['emb_env'] = has_both['is_environmental'].astype(bool)
    has_both['llm_env'] = has_both['is_env_llm'].astype(bool)

    agree     = has_both[has_both['llm_env'] == has_both['emb_env']]
    llm_only  = has_both[has_both['llm_env'] & ~has_both['emb_env']]   # LLM env, emb not
    emb_only  = has_both[~has_both['llm_env'] & has_both['emb_env']]   # emb env, LLM not
    both_env  = has_both[has_both['llm_env'] & has_both['emb_env']]

    print(f'Sample size: {len(has_both)} bills')
    print(f'  Agreement:      {len(agree)} ({100*len(agree)/len(has_both):.0f}%)')
    print(f'  Both env:       {len(both_env)}')
    print(f'  LLM env only:   {len(llm_only)}  ← likely embedding false negatives')
    print(f'  Emb env only:   {len(emb_only)}  ← likely embedding false positives')

    print(f'\nLLM-only env bills ({len(llm_only)}) — probable false negatives in embedding:')
    for _, row in llm_only.iterrows():
        cats = row.get('categories', '[]')
        try:
            cats = ', '.join(json.loads(cats))
        except (json.JSONDecodeError, TypeError):
            pass
        print(f'  score={row.get("env_relevance_score", "?"):.3f}  [{cats}]  {row.get("bill_title","")[:70]}')

    print(f'\nEmb-only env bills ({len(emb_only)}) — probable false positives in embedding:')
    for _, row in emb_only.iterrows():
        cats = row.get('categories', '[]')
        try:
            cats = ', '.join(json.loads(cats))
        except (json.JSONDecodeError, TypeError):
            pass
        print(f'  score={row.get("env_relevance_score", "?"):.3f}  [{cats}]  {row.get("bill_title","")[:70]}')

    return {
        'n_agree': len(agree), 'n_llm_only': len(llm_only),
        'n_emb_only': len(emb_only), 'n_both': len(both_env),
        'llm_only_titles': llm_only['bill_title'].tolist(),
        'emb_only_titles': emb_only['bill_title'].tolist(),
    }


def diag_tag_validity(df_pilot: pd.DataFrame) -> dict:
    """Check structured output quality: tag count, category count, thin-text bills."""
    print('\n── 3. Structured output quality ───────────────────────────────')
    done = df_pilot[df_pilot['summary'].notna()].copy()

    tag_counts, cat_counts = [], []
    zero_tags = zero_cats = 0
    for _, row in done.iterrows():
        try:
            tags = json.loads(row.get('tags') or '[]')
            cats = json.loads(row.get('categories') or '[]')
        except (json.JSONDecodeError, TypeError):
            tags, cats = [], []
        tag_counts.append(len(tags))
        cat_counts.append(len(cats))
        if len(tags) == 0:
            zero_tags += 1
        if len(cats) == 0:
            zero_cats += 1

    print(f'Bills with summaries: {len(done)}')
    print(f'Avg tags per bill:    {np.mean(tag_counts):.2f}  (0 tags: {zero_tags} bills)')
    print(f'Avg categories/bill:  {np.mean(cat_counts):.2f}  (0 cats: {zero_cats} bills)')

    # Body text coverage
    if 'full_text' in done.columns:
        char_counts = done['full_text'].fillna('').str.len()
        thin = (char_counts < 200).sum()
        print(f'\nBody text coverage:')
        print(f'  <200 chars (title-only effectively): {thin} ({100*thin/len(done):.0f}%)')
        print(f'  200–2k chars:   {((char_counts >= 200) & (char_counts < 2000)).sum()}')
        print(f'  2k–10k chars:   {((char_counts >= 2000) & (char_counts < 10000)).sum()}')
        print(f'  >10k chars:     {(char_counts >= 10000).sum()}')

    # Spot-print 10 summaries for qualitative read
    print('\nSample summaries (random 10):')
    for _, row in done.sample(min(10, len(done)), random_state=7).iterrows():
        title = str(row.get('bill_title', ''))[:60]
        summ  = str(row.get('summary', ''))[:200]
        cats  = row.get('categories', '[]')
        try:
            cats = ', '.join(json.loads(cats))
        except (json.JSONDecodeError, TypeError):
            pass
        print(f'\n  "{title}"')
        print(f'  [{cats}]')
        print(f'  → {summ}')

    return {
        'avg_tags': float(np.mean(tag_counts)),
        'zero_tags': zero_tags,
        'zero_cats': zero_cats,
    }


def diag_cost_by_gc(df_pilot: pd.DataFrame) -> None:
    """Print cost breakdown by General Court."""
    print('\n── 4. Cost breakdown by General Court ─────────────────────────')
    done = df_pilot[df_pilot['summary'].notna() & df_pilot['general_court'].notna()]
    if done.empty:
        return
    gc_counts = done.groupby('general_court').size()
    text_lens = done.groupby('general_court')['full_text'].apply(
        lambda s: s.fillna('').str.len().mean()
    )
    print(f'{"GC":>5}  {"Bills":>6}  {"Avg text chars":>15}')
    for gc in sorted(gc_counts.index):
        print(f'  {int(gc):>3}  {gc_counts[gc]:>6}  {text_lens.get(gc, 0):>15.0f}')


def diag_silhouette(df_pilot: pd.DataFrame, client) -> dict:
    """Embed summaries and compare silhouette with original embeddings."""
    print('\n── 5. Silhouette comparison: original vs summary embeddings ───')
    done = df_pilot[
        df_pilot['summary'].notna() &
        df_pilot['cluster_id'].notna() &
        (df_pilot['cluster_id'] >= 0) &
        df_pilot['embedding'].notna()
    ].copy()
    done['cluster_id'] = done['cluster_id'].astype(int)

    # Need at least 2 clusters with 2+ members
    valid_clusters = done['cluster_id'].value_counts()
    valid_clusters = valid_clusters[valid_clusters >= 2].index
    done = done[done['cluster_id'].isin(valid_clusters)]
    if len(done) < 50:
        print(f'  Only {len(done)} valid bills — skipping silhouette')
        return {}

    labels = done['cluster_id'].values

    # Original embeddings
    orig_emb = np.vstack(done['embedding'].apply(
        lambda v: np.array(v, dtype=np.float32)
    ).values)
    orig_norm = normalize(orig_emb - orig_emb.mean(axis=0), norm='l2')

    # Embed summaries
    print(f'  Embedding {len(done)} summaries...')
    summ_emb  = _embed_texts(client, done['summary'].tolist())
    summ_norm = normalize(summ_emb - summ_emb.mean(axis=0), norm='l2')

    sil_orig = silhouette_score(orig_norm, labels, metric='cosine')
    sil_summ = silhouette_score(summ_norm, labels, metric='cosine')
    pct_gain = (sil_summ - sil_orig) / abs(sil_orig) * 100

    print(f'  Original title+body embedding silhouette: {sil_orig:.4f}')
    print(f'  Summary embedding silhouette:             {sil_summ:.4f}')
    print(f'  Change: {pct_gain:+.1f}%')

    return {
        'sil_orig': sil_orig,
        'sil_summ': sil_summ,
        'pct_gain': pct_gain,
        'n_bills': len(done),
        'summ_emb': summ_emb,
        'done': done,
    }


def make_umap(df_pilot: pd.DataFrame, summ_emb: np.ndarray,
              done_df: pd.DataFrame) -> None:
    """UMAP plot using summary embeddings only — all 495 pilot bills in one space.

    done_df rows correspond 1:1 to rows of summ_emb.  Env bills (is_env_llm)
    are coloured by cluster; non-env pilot bills are grey.  No mixing with
    original embeddings from the background corpus.
    """
    print('\n── 6. UMAP with summary embeddings (pilot only) ────────────────')
    import umap as umap_lib
    import plotly.graph_objects as go

    labels_df = pd.read_csv(LABELS_CSV, engine='python', on_bad_lines='skip')
    labels_df = labels_df[
        pd.to_numeric(labels_df['cluster_id'], errors='coerce').notna()
    ].copy()
    labels_df['cluster_id'] = labels_df['cluster_id'].astype(int)
    label_map = dict(zip(labels_df['cluster_id'], labels_df['label']))

    # All pilot bills share the same embedding space — summary embeddings only
    summ_norm = normalize(summ_emb - summ_emb.mean(axis=0), norm='l2')

    # Use LLM env label (is_env_llm) as ground truth for colouring
    is_env = done_df['is_env_llm'].fillna(False).astype(bool).values

    print(f'  UMAP input: {len(done_df)} pilot bills (all summary-embedded)')
    print(f'  Running UMAP (n={len(summ_norm)}, cosine, n_neighbors=15, min_dist=0.1)...')
    reducer = umap_lib.UMAP(
        n_components=2, n_neighbors=15, min_dist=0.1,
        metric='cosine', random_state=42,
    )
    coords = reducer.fit_transform(summ_norm)

    fig = go.Figure()

    # Non-env pilot bills (grey)
    non_env_df = done_df[~is_env]
    ne_coords  = coords[~is_env]
    if len(non_env_df):
        fig.add_trace(go.Scatter(
            x=ne_coords[:, 0], y=ne_coords[:, 1], mode='markers',
            marker=dict(color='#cccccc', size=7, opacity=0.55),
            name=f'Non-env pilot ({len(non_env_df)})',
            hovertext=[
                f'<b>{t}</b><br>score {s:.3f}<br>[{c}]'
                for t, s, c in zip(
                    non_env_df['bill_title'].fillna(''),
                    non_env_df['env_relevance_score'].fillna(0),
                    non_env_df['categories'].fillna('[]'),
                )
            ],
            hoverinfo='text', showlegend=True,
        ))

    # Env pilot bills — coloured by cluster
    env_df     = done_df[is_env].copy()
    env_coords = coords[is_env]
    env_df['cluster_id'] = pd.to_numeric(env_df['cluster_id'], errors='coerce')
    for cid in sorted(env_df['cluster_id'].dropna().astype(int).unique()):
        mask = env_df['cluster_id'].astype(int) == cid
        sub  = env_df[mask]
        sc   = env_coords[mask.values]
        lbl  = label_map.get(cid, f'Cluster {cid}')
        fig.add_trace(go.Scatter(
            x=sc[:, 0], y=sc[:, 1], mode='markers',
            marker=dict(color=PALETTE_25[cid % 25], size=12, opacity=0.92,
                        line=dict(color='black', width=1.0)),
            name=f'{lbl} ({len(sub)})',
            hovertext=[
                f'<b>{row["bill_title"]}</b>'
                f'<br>🌿 env · cluster: {lbl}'
                f'<br>score {row.get("env_relevance_score", 0):.3f}'
                f'<br>{row.get("summary", "")[:120]}'
                for _, row in sub.iterrows()
            ],
            hoverinfo='text', showlegend=True,
        ))

    n_env = int(is_env.sum())
    fig.update_layout(
        title=dict(text=(
            'MA Lobbying Bills — Summary Embeddings UMAP (pilot, 495 bills)'
            f'<br><sup>{n_env} env (LLM, coloured by cluster) · '
            f'{len(non_env_df)} non-env (grey) · '
            'all points summary-embedded · hover for details</sup>'
        ), font=dict(size=13)),
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        legend=dict(font=dict(size=9), itemsizing='constant'),
        margin=dict(l=10, r=10, t=70, b=10),
        width=940, height=640,
        plot_bgcolor='#f4f4f4', paper_bgcolor='white',
        hovermode='closest',
    )
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    html = fig.to_html(full_html=False, include_plotlyjs='cdn', config={'responsive': True})
    OUT_HTML.write_text('{% raw  %}\n' + html + '\n{% endraw %}\n', encoding='utf-8')
    print(f'  Wrote {OUT_HTML}')


def append_to_notes(results: dict) -> None:
    """Append a diagnostics section to NOTES_bill_embeddings.md."""
    ref  = results.get('reference', {})
    dis  = results.get('disagreements', {})
    tags = results.get('tags', {})
    sil  = results.get('silhouette', {})
    n    = results.get('n_pilot', 0)
    cost = results.get('cost', 0.0)

    pct_gain = sil.get('pct_gain', None)
    sil_line = (
        f'| Original title+body | {sil["sil_orig"]:.4f} |\n'
        f'| **Summary embed**   | **{sil["sil_summ"]:.4f}** | {pct_gain:+.0f}% |\n'
        if sil else '_Silhouette comparison not run._\n'
    )

    section = f"""
---

## LLM summary + taxonomy pilot diagnostics ({n}-bill sample, gemini-2.5-flash)

**Run date:** May 2026  **Cost:** ${cost:.4f} for {n} bills  \
(${cost/max(n,1)*1000:.3f}/1k bills, ${cost/max(n,1)*26000:.2f} projected 26k corpus)

### 1. Env classification — reference set precision/recall

| Metric | Value |
|--------|-------|
| Recall (20 known env titles) | {f"{ref['recall']:.0%}" if 'recall' in ref else '(not run)'} |
| Specificity (36 known non-env) | {f"{ref['specificity']:.0%}" if 'specificity' in ref else '(not run)'} |
| False negatives | {len(ref.get('false_negatives', []))} |
| False positives | {len(ref.get('false_positives', []))} |

"""
    if ref.get('false_negatives'):
        section += 'False negatives (env missed by LLM):\n'
        for t in ref['false_negatives']:
            section += f'- {t}\n'
        section += '\n'
    if ref.get('false_positives'):
        section += 'False positives (non-env wrongly flagged):\n'
        for t in ref['false_positives']:
            section += f'- {t}\n'
        section += '\n'

    n_agree   = dis.get('n_agree', '?')
    n_llm     = dis.get('n_llm_only', '?')
    n_emb     = dis.get('n_emb_only', '?')
    n_both    = dis.get('n_both', '?')
    section += f"""### 2. LLM vs embedding disagreement ({n}-bill pilot)

| | Count |
|---|---|
| Both env (agreement) | {n_both} |
| LLM env only (embedding false negatives) | {n_llm} |
| Embedding env only (embedding false positives) | {n_emb} |

"""
    if dis.get('llm_only_titles'):
        section += 'Bills LLM classifies env but embedding misses (top 10):\n'
        for t in dis['llm_only_titles'][:10]:
            section += f'- {t}\n'
        section += '\n'

    section += f"""### 3. Structured output quality

| Metric | Value |
|--------|-------|
| Avg tags per bill | {tags.get('avg_tags', '?'):.2f} |
| Bills with 0 valid tags | {tags.get('zero_tags', '?')} |
| Bills with 0 valid categories | {tags.get('zero_cats', '?')} |

### 4. Silhouette comparison (k=25 clustering)

| Method | Silhouette↑ | Δ |
|--------|-------------|---|
{sil_line}

### 5. UMAP with summary embeddings

**[→ Interactive UMAP (summary embeddings)](../docs/_includes/charts/lobbying_bill_umap_summary.html)**

"""
    existing = NOTES_MD.read_text(encoding='utf-8')
    # Don't duplicate: only append if the pilot diagnostics section isn't already there
    header = f'## LLM summary + taxonomy pilot diagnostics ({n}-bill'
    if header in existing:
        print(f'\nDiagnostics section already in {NOTES_MD} — skipping append')
        return
    NOTES_MD.write_text(existing + section, encoding='utf-8')
    print(f'\nAppended diagnostics section to {NOTES_MD}')


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sample-size', type=int, default=500,
                        help='Expected pilot sample size (for cost reporting)')
    parser.add_argument('--skip-reference', action='store_true',
                        help='Skip the reference set LLM calls')
    parser.add_argument('--skip-umap', action='store_true')
    args = parser.parse_args()

    api_key = API_KEY_PATH.read_text(encoding='utf-8').strip()
    import google.genai as genai
    client = genai.Client(api_key=api_key)

    df = _load_parquet()
    df_pilot = df[df['summary'].notna()].copy()
    print(f'{len(df_pilot)} bills with summaries in parquet')

    if len(df_pilot) == 0:
        print('ERROR: No summaries found. Run summarize_lobbying_bills.py first.')
        return

    results = {'n_pilot': len(df_pilot)}

    # Estimate cost from pilot token data (rough: use pilot averages)
    results['cost'] = len(df_pilot) * 0.000106   # $0.000106/bill from 200-bill pilot

    if not args.skip_reference:
        results['reference'] = diag_reference_set(client)

    results['disagreements'] = diag_disagreements(df_pilot)
    results['tags']          = diag_tag_validity(df_pilot)
    diag_cost_by_gc(df_pilot)

    sil_results = diag_silhouette(df_pilot, client)
    results['silhouette'] = sil_results

    if not args.skip_umap and sil_results.get('summ_emb') is not None:
        make_umap(df, sil_results['summ_emb'], sil_results['done'])

    append_to_notes(results)
    print('\nAll diagnostics complete.')


if __name__ == '__main__':
    main()
