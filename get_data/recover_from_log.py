"""Recover summarize_lobbying_bills.py results from a log file.

If the run crashed before saving, this script parses the log and writes
the recovered summaries/categories/tags/is_env_llm back to the parquet.
summary_embedding is NOT in the log and will need re-embedding.

Usage (from get_data/):
    python recover_from_log.py /tmp/summarize_remaining.log [--dry-run]
"""

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

DATA_DIR      = Path('../docs/data')
LOCAL_PARQUET = DATA_DIR / 'MA_bill_embeddings.parquet'
GCS_PARQUET   = 'gs://openamend-data/MA_bill_embeddings.parquet'

# Matches lines like:
#   [  42/6536] 🌿 GC192 3288 [...] $0.12 | Energy, Environmental Protection
BILL_RE   = re.compile(
    r'^\s+\[[\s\d]+/\d+\]\s+(🌿|  )\s*GC(\d+)\s+(\S+)\s+\[.*\]\s+\$[\d.]+\s+\|\s+(.+)$'
)
TAGS_RE   = re.compile(r'^\s+tags:\s+(.+)$')
TITLE_RE  = re.compile(r'^\s+"(.+)"$')
SUMM_RE   = re.compile(r'^\s+SUMMARY:\s+(.+)$')


def parse_log(path: Path) -> list[dict]:
    """Parse log, return list of dicts with gc, bill_no, is_env, categories, tags, summary."""
    records = []
    cur: dict | None = None

    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.rstrip('\n')

            m = BILL_RE.match(line)
            if m:
                if cur:
                    records.append(cur)
                env_flag, gc, bill_no, cats_raw = m.group(1), m.group(2), m.group(3), m.group(4)
                cats = [c.strip() for c in cats_raw.split(',')]
                cur = {
                    'gc':         int(gc),
                    'bill_no':    bill_no,
                    'is_env':     env_flag.strip() == '🌿',
                    'categories': cats,
                    'tags':       [],
                    'summary':    None,
                }
                continue

            if cur is None:
                continue

            m = TAGS_RE.match(line)
            if m:
                raw = m.group(1)
                # Strip trailing "…" and split
                tags = [t.strip() for t in raw.rstrip('…').split(',')]
                cur['tags'] = tags
                continue

            m = SUMM_RE.match(line)
            if m:
                cur['summary'] = m.group(1).strip()
                continue

    if cur:
        records.append(cur)

    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('log', type=Path, help='Path to summarize log file')
    parser.add_argument('--dry-run', action='store_true',
                        help='Parse and report without writing')
    args = parser.parse_args()

    if not args.log.exists():
        print(f'Log not found: {args.log}')
        sys.exit(1)

    records = parse_log(args.log)
    print(f'Parsed {len(records)} bill records from {args.log}')

    if not records:
        print('No records found — check log format.')
        sys.exit(1)

    # Load parquet
    try:
        import gcsfs
        fs = gcsfs.GCSFileSystem()
        if fs.exists(GCS_PARQUET):
            with fs.open(GCS_PARQUET, 'rb') as f:
                df = pd.read_parquet(f)
            print(f'Loaded {len(df)} rows from GCS')
    except Exception as e:
        print(f'GCS failed ({e}), using local')
        df = pd.read_parquet(LOCAL_PARQUET)
        print(f'Loaded {len(df)} rows from local')

    # Build a lookup: (gc, bill_no) → df index
    df['_gc_int'] = pd.to_numeric(df['general_court'], errors='coerce').astype('Int64')
    lookup = {}
    for idx, row in df.iterrows():
        key = (int(row['_gc_int']) if pd.notna(row['_gc_int']) else -1,
               str(row.get('bill_number', '')))
        lookup[key] = idx

    already_have = int(df['summary'].notna().sum())
    print(f'Parquet: {already_have} / {len(df)} already have summaries')

    n_match = n_already = n_no_match = n_written = 0
    for rec in records:
        key = (rec['gc'], rec['bill_no'])
        if key not in lookup:
            n_no_match += 1
            continue
        idx = lookup[key]
        if df.loc[idx, 'summary'] is not None and pd.notna(df.loc[idx, 'summary']):
            n_already += 1
            continue
        n_match += 1
        if not args.dry_run:
            if rec['summary']:
                df.loc[idx, 'summary'] = rec['summary']
            df.loc[idx, 'categories'] = json.dumps(rec['categories'])
            df.loc[idx, 'tags']       = json.dumps(rec['tags'])
            df.loc[idx, 'is_env_llm'] = rec['is_env']
            n_written += 1

    has_summary = int(df['summary'].notna().sum())
    print(f'\nResults:')
    print(f'  Matched to parquet:  {n_match}')
    print(f'  Already had summary: {n_already}')
    print(f'  No match in parquet: {n_no_match}')
    if not args.dry_run:
        print(f'  Written:             {n_written}')
        print(f'  Summaries in parquet: {has_summary} (was {already_have})')

        # Save
        df.drop(columns=['_gc_int'], inplace=True, errors='ignore')
        df.to_parquet(LOCAL_PARQUET, index=False)
        print(f'Saved to {LOCAL_PARQUET}')
        try:
            import gcsfs
            fs = gcsfs.GCSFileSystem()
            with fs.open(GCS_PARQUET, 'wb') as f:
                df.to_parquet(f, index=False)
            print(f'Uploaded to {GCS_PARQUET}')
        except Exception as e:
            print(f'GCS upload failed: {e}')
    else:
        print('  (dry-run — nothing written)')
        if n_match > 0:
            sample = next(r for r in records if
                          (r['gc'], r['bill_no']) in lookup and
                          pd.isna(df.loc[lookup[(r['gc'], r['bill_no'])], 'summary']))
            print(f'\nSample recoverable record:')
            print(f'  GC{sample["gc"]} {sample["bill_no"]}')
            print(f'  is_env: {sample["is_env"]}')
            print(f'  categories: {sample["categories"]}')
            print(f'  summary: {(sample["summary"] or "")[:120]}')


if __name__ == '__main__':
    main()
