"""Package AMEND CSO / environmental-justice layers for ArcGIS Online.

Produces a local ``arcgis_export/`` directory (gitignored) containing
point CSVs and polygon GeoJSONs ready to upload to ArcGIS Online as
hosted feature layers, plus a README.md data dictionary with suggested
field aliases.

All layers use the ``MAEEADP_through_2025`` data window (June 30 2022 –
December 31 2025) to stay consistent with the 2026-04 analysis post.
No spatial joins are performed here — point-to-polygon assignment is
already encoded in the pre-aggregated CSVs written by EEA_DP_CSO_map.py.

Run from the analysis/ directory:

    conda run -n amend_python python export_arcgis.py [--outdir ../arcgis_export] [--include-2011]
"""

import argparse
import os
from datetime import datetime

import geopandas as gpd
import pandas as pd

DATA_PATH = '../docs/data/'
GEO_PATH = '../docs/assets/geo_json/'
SLUG = 'MAEEADP_through_2025'

# Data window, for README text and field aliases
WINDOW_LABEL = 'Jun 30 2022 – Dec 31 2025'

# Massachusetts sanity bounding box (WGS84)
MA_BBOX = (-74.0, 41.0, -69.0, 43.2)

EJ_RENAME = {
    'MINORPCT': 'pct_minority',
    'LOWINCPCT': 'pct_lowincome',
    'LINGISOPCT': 'pct_ling_iso',
}

FIELD_ALIASES = {
    'discharge_mgal': f'Total sewage discharge (million gallons, {WINDOW_LABEL})',
    'discharge_count': 'Number of discharge reports',
    'operator_name': 'Sewer operator',
    'operator_class': 'Operator class',
    'permit_id': 'NPDES permit ID',
    'outfall_id': 'Outfall ID',
    'outfall_location': 'Outfall location description',
    'municipality': 'Municipality',
    'water_body': 'Receiving water body',
    'water_body_desc': 'Receiving water body description',
    'geoid_bg': 'Census block group GEOID (2017)',
    'pct_minority': 'People of color (%)',
    'pct_lowincome': 'Low-income population (%)',
    'pct_ling_iso': 'Linguistically isolated households (%)',
    'population': 'Total population (ACS, via EJSCREEN 2023)',
    'town': 'Municipality',
    'watershed': 'Major watershed',
    'NAME': 'Watershed name',
    'SQ_MI': 'Watershed area (sq mi)',
    'TOWN': 'Town name',
    'POP2010': 'Population (2010 Census)',
    'GEOID': 'Census block group GEOID (2017)',
    'discharge_mgal_2011': 'Total sewage discharge 2011 (million gallons)',
    'discharge_count_2011': 'Number of discharges 2011',
}


def _check_bbox(gdf: gpd.GeoDataFrame, name: str) -> None:
    minx, miny, maxx, maxy = gdf.total_bounds
    assert MA_BBOX[0] < minx and miny > MA_BBOX[1] and maxx < MA_BBOX[2] and maxy < MA_BBOX[3], \
        f'{name}: bounds {gdf.total_bounds} outside Massachusetts sanity box {MA_BBOX}'


def _pct(df: pd.DataFrame) -> pd.DataFrame:
    """Convert EJSCREEN 0-1 fractions to 0-100 percentages, renamed per EJ_RENAME."""
    out = df.rename(columns=EJ_RENAME)
    for col in EJ_RENAME.values():
        out[col] = (out[col] * 100).round(1)
    return out


def load_discharge_by_watershed() -> pd.DataFrame:
    """Watershed discharge totals are not written to any CSV by the analysis
    pipeline; derive them from the block-group master table."""
    egs = pd.read_csv(
        f'{DATA_PATH}{SLUG}_data_egs_merge.csv.gz', dtype={'ID': str}, low_memory=False
    )
    egs = egs[egs['Watershed'] != '[UNKNOWN]']
    agg = (
        egs.groupby('Watershed')[['DischargeVolume', 'DischargeCount']]
        .sum()
        .reset_index()
        .rename(columns={'DischargeVolume': 'discharge_mgal', 'DischargeCount': 'discharge_count'})
    )
    return agg


def export_outfalls(outdir: str) -> float:
    df = pd.read_csv(f'{DATA_PATH}{SLUG}_data_cso.csv', index_col=0, dtype={'GEOID': str})
    df = df.drop(columns=['Year'])
    df = df.rename(columns={
        'cso_id': 'outfall_id',
        'DischargeVolume': 'discharge_mgal',
        'DischargeCount': 'discharge_count',
        'permiteeName': 'operator_name',
        'permiteeId': 'permit_id',
        'permiteeClass': 'operator_class',
        'location': 'outfall_location',
        'waterBody': 'water_body',
        'waterBodyDescription': 'water_body_desc',
        'GEOID': 'geoid_bg',
    })
    assert len(df) == 193, f'outfalls: expected 193 rows, got {len(df)}'

    # Repair swapped lat/lon pairs in the source data (e.g. Haverhill HAV021B is
    # reported as latitude=-71.08, longitude=42.77). A Massachusetts latitude is
    # always positive and a longitude always negative, so a negative latitude
    # paired with a positive longitude is an unambiguous swap.
    swapped = (df['latitude'] < 0) & (df['longitude'] > 0)
    if swapped.any():
        print(f'  repairing {swapped.sum()} outfall(s) with swapped lat/lon: '
              f'{df.loc[swapped, "outfall_id"].tolist()}')
        df.loc[swapped, ['latitude', 'longitude']] = (
            df.loc[swapped, ['longitude', 'latitude']].values
        )

    assert df['latitude'].between(MA_BBOX[1], MA_BBOX[3]).all()
    assert df['longitude'].between(MA_BBOX[0], MA_BBOX[2]).all()
    path = os.path.join(outdir, 'cso_outfalls_2022_2025.csv')
    df.to_csv(path, index=False)
    total = df['discharge_mgal'].sum()
    print(f'  {path}: {len(df)} outfall points, {total:,.1f} Mgal total')
    return total


def export_watersheds(outdir: str) -> float:
    geo = gpd.read_file(f'{GEO_PATH}watshdp1_geojson_simple.json')[['NAME', 'SQ_MI', 'geometry']]
    ej = _pct(pd.read_csv(f'{DATA_PATH}{SLUG}_df_watershed_level.csv'))
    ej = ej[ej['Watershed'] != '[UNKNOWN]']
    discharge = load_discharge_by_watershed()

    gdf = geo.merge(ej, left_on='NAME', right_on='Watershed', how='left').drop(columns=['Watershed'])
    gdf = gdf.merge(discharge, left_on='NAME', right_on='Watershed', how='left').drop(columns=['Watershed'])
    gdf[['discharge_mgal', 'discharge_count']] = gdf[['discharge_mgal', 'discharge_count']].fillna(0)
    gdf['discharge_mgal'] = gdf['discharge_mgal'].round(3)

    assert len(gdf) == 32, f'watersheds: expected 32 features, got {len(gdf)}'
    assert gdf.crs.to_epsg() == 4326
    _check_bbox(gdf, 'watersheds')
    path = os.path.join(outdir, 'watersheds_ej_discharge.geojson')
    gdf.to_file(path, driver='GeoJSON')
    total = gdf['discharge_mgal'].sum()
    print(f'  {path}: {len(gdf)} watershed polygons, {total:,.1f} Mgal total')
    return total


def export_towns(outdir: str) -> float:
    geo = gpd.read_file(f'{GEO_PATH}TOWNSSURVEY_POLYM_geojson_simple.json')[['TOWN', 'POP2010', 'geometry']]
    ej = _pct(pd.read_csv(f'{DATA_PATH}{SLUG}_df_town_level.csv'))
    ej = ej[ej['Town'] != '[UNKNOWN]']
    discharge = pd.read_csv(f'{DATA_PATH}{SLUG}_data_ins_g_muni_j.csv')
    discharge = discharge[discharge['Town'] != '[UNKNOWN]'].rename(
        columns={'DischargeVolume': 'discharge_mgal', 'DischargeCount': 'discharge_count'}
    )
    dropped = None

    gdf = geo.merge(ej, left_on='TOWN', right_on='Town', how='left').drop(columns=['Town'])
    gdf = gdf.merge(discharge, left_on='TOWN', right_on='Town', how='left').drop(columns=['Town'])
    gdf[['discharge_mgal', 'discharge_count']] = gdf[['discharge_mgal', 'discharge_count']].fillna(0)
    gdf['discharge_mgal'] = gdf['discharge_mgal'].round(3)

    assert len(gdf) == 351, f'towns: expected 351 features, got {len(gdf)}'
    assert gdf.crs.to_epsg() == 4326
    _check_bbox(gdf, 'towns')
    n_no_ej = gdf['pct_minority'].isna().sum()
    path = os.path.join(outdir, 'towns_ej_discharge.geojson')
    gdf.to_file(path, driver='GeoJSON')
    total = gdf['discharge_mgal'].sum()
    print(f'  {path}: {len(gdf)} town polygons ({n_no_ej} without EJ data), {total:,.1f} Mgal total')
    return total


def export_block_groups(outdir: str) -> float:
    geo = gpd.read_file(f'{GEO_PATH}cb_2017_25_bg_500k.json')[['GEOID', 'geometry']]
    geo['GEOID'] = geo['GEOID'].astype(str)
    egs = pd.read_csv(
        f'{DATA_PATH}{SLUG}_data_egs_merge.csv.gz', dtype={'ID': str}, low_memory=False
    )
    keep = ['ID', 'ACSTOTPOP', 'MINORPCT', 'LOWINCPCT', 'LINGISOPCT',
            'DischargeVolume', 'DischargeCount', 'Town', 'Watershed']
    egs = _pct(egs[keep]).rename(columns={
        'ACSTOTPOP': 'population',
        'DischargeVolume': 'discharge_mgal',
        'DischargeCount': 'discharge_count',
        'Town': 'town',
        'Watershed': 'watershed',
    })
    egs['population'] = egs['population'].round().astype('Int64')

    gdf = geo.merge(egs, left_on='GEOID', right_on='ID', how='left').drop(columns=['ID'])
    gdf[['discharge_mgal', 'discharge_count']] = gdf[['discharge_mgal', 'discharge_count']].fillna(0)
    gdf['discharge_mgal'] = gdf['discharge_mgal'].round(3)

    assert len(gdf) == 4982, f'block groups: expected 4982 features, got {len(gdf)}'
    assert gdf.crs.to_epsg() == 4326
    _check_bbox(gdf, 'block groups')
    path = os.path.join(outdir, 'block_groups_ej_discharge.geojson')
    gdf.to_file(path, driver='GeoJSON')
    total = gdf['discharge_mgal'].sum()
    size_mb = os.path.getsize(path) / 1e6
    print(f'  {path}: {len(gdf)} block-group polygons ({size_mb:.1f} MB), {total:,.1f} Mgal total')
    return total


def export_necir_2011(outdir: str) -> None:
    df = pd.read_csv(f'{DATA_PATH}NECIR_CSO_data_cso.csv', index_col=0, dtype={'GEOID': str})
    df = df.rename(columns={
        'cso_id': 'outfall_id',
        'Latitude': 'latitude',
        'Longitude': 'longitude',
        'Nearest_Pipe_Address': 'outfall_location',
        'Municipality': 'municipality',
        'DischargesBody': 'water_body',
        '2011_Discharges_MGal': 'discharge_mgal_2011',
        '2011_Discharge_N': 'discharge_count_2011',
        'GEOID': 'geoid_bg',
    })
    # ArcGIS Online rejects field names that start with a digit; verify none remain
    assert not any(c[0].isdigit() for c in df.columns), df.columns.tolist()
    path = os.path.join(outdir, 'cso_outfalls_2011_necir.csv')
    df.to_csv(path, index=False)
    print(f'  {path}: {len(df)} outfall points (2011 NECIR baseline)')


def write_readme(outdir: str, include_2011: bool) -> None:
    alias_rows = '\n'.join(
        f'| `{field}` | {alias} |' for field, alias in FIELD_ALIASES.items()
    )
    necir_section = (
        '\n- `cso_outfalls_2011_necir.csv` — 2011 CSO outfall discharges from the NECIR survey '
        '(historical baseline; column meanings as above with `_2011` suffix).'
        if include_2011 else ''
    )
    content = f"""# AMEND ArcGIS Online export

Generated {datetime.now():%Y-%m-%d %H:%M} by `analysis/export_arcgis.py` from the
[AMEND](https://openamend.org) repository. Upload each file to ArcGIS Online
(Content → New item) and choose "Add and create a hosted feature layer".

## Files

- `cso_outfalls_2022_2025.csv` — 193 CSO/SSO outfall points (locate by `latitude`/`longitude`, WGS84).
- `watersheds_ej_discharge.geojson` — 32 major watersheds (MassGIS) with EJ + discharge attributes.
- `towns_ej_discharge.geojson` — 351 municipalities (MassGIS) with EJ + discharge attributes.
- `block_groups_ej_discharge.geojson` — 4,982 census block groups (2017 cartographic boundaries) with EJ + discharge attributes.{necir_section}

## Units and definitions

- `discharge_mgal`: total reported sewage discharge volume in **millions of US gallons**
  over {WINDOW_LABEL} (2022 is a partial year — reporting began June 30, 2022).
- `discharge_count`: number of discharge reports over the same window.
- `pct_minority` / `pct_lowincome` / `pct_ling_iso`: EPA EJSCREEN 2023 demographic
  indicators, expressed as **percent (0–100)**. Town and watershed values are
  population-weighted averages of block-group values.
- `population`: ACS total population from EJSCREEN 2023.
- All geometries are EPSG:4326 (WGS84).

## Suggested ArcGIS field aliases

Set these on each hosted layer (item page → Data → Fields) so popups read cleanly:

| Field | Alias |
|---|---|
{alias_rows}

## Caveats

- 33 towns (and the BASHBISH watershed) have no EJ attribute data (null) — they contain
  no analyzed census block groups; their discharge totals are 0.
- `outfall_id` is only unique in combination with `permit_id` (e.g. outfall "001"
  exists for several operators).
- Outfalls with swapped latitude/longitude in the source data (detected as a negative
  latitude with positive longitude) are repaired on export; the script logs which.
- Town discharge totals sum to less than the watershed/block-group/outfall totals:
  roughly 7% of volume comes from outfalls whose town assignment is unknown in the
  source data. Do not treat town sums as a complete statewide total.
- Discharge volumes mix metered and modeled estimates (roughly half of untreated CSO
  and SSO reports are modeled); see the AMEND analysis posts for details.

## Attribution

- Discharge reports: [MA EEA Data Portal](https://eeaonline.eea.state.ma.us/portal) (Sewage Notification Act reporting)
- Demographics: EPA EJSCREEN 2023 (archived at openamend.org)
- Watershed and town boundaries: MassGIS
- Census block group boundaries: US Census cartographic boundary files (2017)
- 2011 baseline: New England Center for Investigative Reporting (NECIR)
- Compiled by AMEND — <https://openamend.org>
"""
    path = os.path.join(outdir, 'README.md')
    with open(path, 'w') as f:
        f.write(content)
    print(f'  {path}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Export AMEND layers for ArcGIS Online.')
    parser.add_argument('--outdir', default='../arcgis_export', help='Output directory')
    parser.add_argument('--include-2011', action='store_true',
                        help='Also export the 2011 NECIR outfall baseline CSV')
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    print(f'Exporting ArcGIS layers to {args.outdir}')

    total_outfalls = export_outfalls(args.outdir)
    total_ws = export_watersheds(args.outdir)
    total_towns = export_towns(args.outdir)
    total_bg = export_block_groups(args.outdir)
    if args.include_2011:
        export_necir_2011(args.outdir)
    write_readme(args.outdir, args.include_2011)

    # Volume conservation: watershed and block-group totals both derive from the
    # egs_merge table and must match; the outfall CSV is aggregated independently
    # upstream and should agree closely. Town totals may drop [UNKNOWN] volume.
    assert abs(total_ws - total_bg) < 1.0, (total_ws, total_bg)
    assert abs(total_outfalls - total_bg) / total_outfalls < 0.01, (total_outfalls, total_bg)
    print(f'Volume conservation: outfalls {total_outfalls:,.1f} | watersheds {total_ws:,.1f} | '
          f'block groups {total_bg:,.1f} | towns {total_towns:,.1f} Mgal '
          f'(town deficit = [UNKNOWN]-town volume: {total_bg - total_towns:,.1f})')
    print('Done.')
