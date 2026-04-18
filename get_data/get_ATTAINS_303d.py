"""Fetch Massachusetts 303(d) Integrated List of Waters from MassGIS shapefile downloads.

Section 303(d) of the Clean Water Act requires MA to identify waterbodies that fail to meet
water quality standards.  MA submits a biennial Integrated List to EPA; MassGIS publishes the
approved data as shapefiles with DBF attribute tables.

Data source: MassGIS (Massachusetts Bureau of Geographic Information)
  https://www.mass.gov/info-details/massgis-data-massdep-2022-integrated-list-of-waters-305b303d

Available cycles: 2010, 2012, 2014, 2016, 2018, 2022 (see CYCLES dict below).
Note: 2002–2008 are not available from MassGIS; 2020 is missing from the S3 bucket.
The next cycle (2024) will be submitted April 2026 and added to CYCLES when published.

The impairment DBF (one row per assessment-unit × designated-use × impairment-cause) is read
directly as a binary DBF file — no geopandas or shapefile reading needed.

Column normalization across cycles:
  WATERTYPE/WATER_TYPE → waterType
  AU_Size/AU_SIZE      → auSize
  TMDLEPA_ID/ACTION_ID → tmdlId (first non-empty of TMDL ID fields)
  CLASS "Class B" form → "B" (2010 quirk)
  hasTmdl              → derived: 1 if category in (4A, 4B, 4C), else 0

Category meanings:
  1    = Fully Supporting all designated uses
  2    = Attaining (some concern, no impairment)
  3    = Insufficient information
  4A   = Impaired, TMDL approved
  4B   = Impaired, addressed through other required plans
  4C   = Impaired, addressed through alternative control requirement
  5    = Impaired, TMDL needed (the "303(d) list" proper)

Outputs:
  ../docs/data/EPA_303d_impairments.csv        — full table (~100k rows, all cycles)
  ../docs/data/EPA_303d_impairments_sample.csv — 10-row sample for Jekyll table
  ../docs/data/ts_update_ATTAINS_303d.yml      — timestamp
"""

import io
import struct
import zipfile
import datetime
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd

# ── Cycle → S3 URL mapping ─────────────────────────────────────────────────────
# Add new entries here when MassGIS publishes a new cycle.
# 2024 cycle expected April 2026 after EPA approval of MA's submission.
CYCLES = {
    2010: 'https://s3.us-east-1.amazonaws.com/download.massgis.digital.mass.gov/shapefiles/state/il2010_shp.zip',
    2012: 'https://s3.us-east-1.amazonaws.com/download.massgis.digital.mass.gov/shapefiles/state/il2012_shp.zip',
    2014: 'https://s3.us-east-1.amazonaws.com/download.massgis.digital.mass.gov/shapefiles/state/il2014_shp.zip',
    2016: 'https://s3.us-east-1.amazonaws.com/download.massgis.digital.mass.gov/shapefiles/state/il2016_shp.zip',
    2018: 'https://s3.us-east-1.amazonaws.com/download.massgis.digital.mass.gov/shapefiles/state/il2018_shp.zip',
    2022: 'https://s3.us-east-1.amazonaws.com/download.massgis.digital.mass.gov/shapefiles/state/il2022_shp.zip',
}

# Name of the impairment DBF inside each zip (varies by cycle year)
IMPAIRMENT_DBF = {
    2010: 'IL_ADB_2010.dbf',
    2012: 'IL_ADB_2012.dbf',
    2014: 'IL_ADB_2014.dbf',
    2016: 'ATTAIN16.dbf',
    2018: 'ATTAIN18.dbf',
    2022: 'IL_ATTAINS_2022.dbf',
}

OUTPUT_CSV = '../docs/data/EPA_303d_impairments.csv'
SAMPLE_CSV = '../docs/data/EPA_303d_impairments_sample.csv'
TIMESTAMP_FILE = '../docs/data/ts_update_ATTAINS_303d.yml'


def _make_session() -> requests.Session:
    """Return a requests Session with automatic retries on transient errors."""
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    session.mount('https://', HTTPAdapter(max_retries=retry))
    session.mount('http://', HTTPAdapter(max_retries=retry))
    return session


def _read_dbf(data: bytes) -> pd.DataFrame:
    """Parse a DBF file from raw bytes and return a DataFrame.

    Supports dBASE III+ format (field types C, N, F, L, D).
    No external dependencies — pure Python struct parsing.
    """
    f = io.BytesIO(data)
    # Header: version(1) + date(3) + num_records(4) + header_size(2) + record_size(2) + reserved(20)
    f.read(4)
    num_records = struct.unpack('<I', f.read(4))[0]
    header_size = struct.unpack('<H', f.read(2))[0]
    record_size = struct.unpack('<H', f.read(2))[0]  # noqa: F841
    f.read(20)  # reserved

    # Field descriptors: 32 bytes each, terminated by 0x0D
    fields = []
    while True:
        field_desc = f.read(32)
        if not field_desc or field_desc[0:1] == b'\r':
            break
        name = field_desc[0:11].replace(b'\x00', b'').decode('latin-1').strip()
        ftype = chr(field_desc[11])
        length = field_desc[16]
        fields.append((name, ftype, length))

    f.seek(header_size)

    records = []
    for _ in range(num_records):
        deletion_flag = f.read(1)
        if deletion_flag == b'*':
            # Skip deleted records but still advance position
            for _, _, length in fields:
                f.read(length)
            continue
        row = {}
        for name, ftype, length in fields:
            raw = f.read(length).decode('latin-1', errors='replace').strip()
            if raw == '<Null>' or raw == '':
                row[name] = None
            elif ftype in ('N', 'F') and raw:
                try:
                    row[name] = float(raw)
                except ValueError:
                    row[name] = raw
            else:
                row[name] = raw
        records.append(row)

    return pd.DataFrame(records)


def _normalize(df: pd.DataFrame, cycle_year: int) -> pd.DataFrame:
    """Normalize column names and values across cycle years to a common schema."""
    # ── Rename to standard output columns ────────────────────────────────────
    rename_map = {
        # Water type (2010-2014 use WATERTYPE, 2016+ use WATER_TYPE)
        'WATERTYPE': 'waterType',
        'WATER_TYPE': 'waterType',
        # Size (2018 uses AU_Size with capital S)
        'AU_SIZE': 'auSize',
        'AU_Size': 'auSize',
        # Other standard columns
        'AU_ID': 'auId',
        'WATERBODY': 'waterbody',
        'WATERSHED': 'watershed',
        'SIZE_UNIT': 'sizeUnit',
        'CLASS': 'useClass',
        'QUALIFIER': 'qualifier',
        'CATEGORY': 'category',
        'USE': 'designatedUse',
        'ATTAINMENT': 'attainment',
        'CAUSE': 'cause',
        'SOURCE': 'source',
        'LOCATION1': 'location',
        'CYCLE': 'reportingCycle',
        'WATERCODE': 'waterCode',
        # TMDL identifiers (vary by cycle — consolidated below)
        'TMDLEPA_ID': '_tmdlEpa',
        'TMDLDWM_ID': '_tmdlDwm',
        'DWM_TITLE': '_tmdlTitle',
        'ACTION_ID': '_actionId',
        'REPORT_ID': '_reportId',
        'REP_TITLE': '_repTitle',
        # 2018 variant
        'Info_Name': 'infoName',
        'INFO_NAME': 'infoName',
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    # ── Add reportingCycle if not present (2010, 2012 don't have CYCLE field) ──
    if 'reportingCycle' not in df.columns:
        df['reportingCycle'] = cycle_year
    else:
        df['reportingCycle'] = cycle_year  # use URL year as authoritative

    # ── Consolidate TMDL identifier columns ──────────────────────────────────
    tmdl_cols = [c for c in ['_tmdlEpa', '_tmdlDwm', '_actionId'] if c in df.columns]
    if tmdl_cols:
        df['tmdlId'] = df[tmdl_cols[0]].copy()
        for col in tmdl_cols[1:]:
            df['tmdlId'] = df['tmdlId'].where(df['tmdlId'].notna(), df[col])
        df.drop(columns=[c for c in ['_tmdlEpa', '_tmdlDwm', '_tmdlTitle',
                                     '_actionId', '_reportId', '_repTitle']
                          if c in df.columns], inplace=True)
    else:
        df['tmdlId'] = None

    # ── Normalize CLASS (2010 uses "Class B" form) ─────────────────────────
    if 'useClass' in df.columns:
        df['useClass'] = df['useClass'].str.replace(r'^Class\s+', '', regex=True)

    # ── Derive hasTmdl from category ─────────────────────────────────────────
    df['hasTmdl'] = df['category'].isin(['4A', '4B', '4C']).astype(int)

    # ── Drop noisy/geometry columns ──────────────────────────────────────────
    drop_cols = ['OBJECTID', 'SHAPE_LEN', 'LOCATION2', 'POLTNT_FLG', 'SRCE_CONF',
                 'ALERT', 'WBID_2022', 'infoName', 'waterCode', 'qualifier',
                 'location']
    df.drop(columns=[c for c in drop_cols if c in df.columns], inplace=True)

    # ── Select and order final columns ────────────────────────────────────────
    col_order = ['reportingCycle', 'auId', 'waterbody', 'watershed', 'waterType',
                 'auSize', 'sizeUnit', 'useClass', 'category', 'designatedUse',
                 'attainment', 'cause', 'source', 'tmdlId', 'hasTmdl']
    present = [c for c in col_order if c in df.columns]
    df = df[present]

    return df


def _get_cached_cycles() -> set:
    """Return the set of reportingCycle years already in the cached CSV."""
    try:
        df = pd.read_csv(OUTPUT_CSV, usecols=['reportingCycle'])
        return set(int(y) for y in df['reportingCycle'].dropna().unique())
    except (FileNotFoundError, ValueError, KeyError):
        return set()


def fetch_cycle(session: requests.Session, year: int) -> pd.DataFrame:
    """Download and parse the MassGIS shapefile for one reporting cycle year."""
    url = CYCLES[year]
    dbf_name = IMPAIRMENT_DBF[year]
    print(f'  Downloading {year} cycle from MassGIS...')
    resp = session.get(url, timeout=(30, 300))
    resp.raise_for_status()

    z = zipfile.ZipFile(io.BytesIO(resp.content))
    dbf_data = z.read(dbf_name)

    df = _read_dbf(dbf_data)
    df = _normalize(df, year)
    print(f'  {year}: {len(df)} rows')
    return df


def main():
    cached = _get_cached_cycles()
    new_cycles = sorted(set(CYCLES.keys()) - cached)

    if not new_cycles:
        print('303(d) data is current; no new cycles to fetch. Skipping.')
        return

    print(f'Fetching 303(d) cycles: {new_cycles}')
    session = _make_session()

    dfs = []

    # Load existing cached data if present
    if cached:
        try:
            dfs.append(pd.read_csv(OUTPUT_CSV))
            print(f'Loaded {len(dfs[0])} cached rows (cycles: {sorted(cached)})')
        except FileNotFoundError:
            pass

    for year in new_cycles:
        try:
            df = fetch_cycle(session, year)
            dfs.append(df)
            time.sleep(1)  # be polite to S3
        except Exception as e:
            print(f'  ERROR fetching {year}: {e}')
            continue

    if not dfs:
        print('No data fetched. Exiting.')
        return

    combined = pd.concat(dfs, ignore_index=True)
    combined.sort_values(['reportingCycle', 'auId'], inplace=True)

    combined.to_csv(OUTPUT_CSV, index=False)
    print(f'Wrote {len(combined)} rows to {OUTPUT_CSV}')

    # Write 10-row sample with one row per cycle for variety
    sample_rows = []
    for cycle in sorted(combined['reportingCycle'].unique()):
        subset = combined[combined['reportingCycle'] == cycle]
        sample_rows.append(subset.sample(n=min(2, len(subset)), random_state=42))
    sample = pd.concat(sample_rows).head(10)
    sample.to_csv(SAMPLE_CSV, index=False)

    # Timestamp
    latest_cycle = int(combined['reportingCycle'].max())
    with open(TIMESTAMP_FILE, 'w') as f:
        f.write(f'updated: {str(datetime.datetime.now()).split(".")[0]}\n')
        f.write(f'latest_cycle: {latest_cycle}\n')

    print(f'Done. Latest cycle: {latest_cycle}')


if __name__ == '__main__':
    main()
