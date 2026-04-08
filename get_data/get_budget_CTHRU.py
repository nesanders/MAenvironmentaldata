"""Fetch MA environmental agency budget data from MA Comptroller CTHRU (Socrata API).

Replaces get_MassBudget_environmental.py, which has been blocked by Cloudflare since 2026.
Coverage: FY2005–present from CTHRU Socrata API, FY2001–FY2004 from cached MassBudget data.
Agencies: DEP (22000100), DCR (28000100+28100100), EEA (20011001+20000100), Fish&Game (23000100).
"""

import datetime
import requests
import pandas as pd

CTHRU_URL = 'https://cthru.data.socrata.com/resource/kv7m-35wn.json'

# Accounts to sum per agency
AGENCY_ACCOUNTS = {
    'DEPAdministration': ['22000100'],
    'DCRAdministration': ['28000100', '28100100'],
    'EEAAdministration': ['20011001', '20000100'],
    'FishGameAdministration': ['23000100'],
}


def fetch_agency_budget(accounts: list) -> pd.DataFrame:
    """Query CTHRU for a set of appropriation accounts, sum by fiscal year."""
    acct_filter = ' OR '.join(f"appropriation_account_number='{a}'" for a in accounts)
    params = {
        '$where': acct_filter,
        '$limit': 500,
        '$select': 'fiscal_year,original_enacted_budget',
    }
    resp = requests.get(CTHRU_URL, params=params, timeout=30)
    resp.raise_for_status()
    df = pd.DataFrame(resp.json())
    if df.empty:
        print(f'Warning: No data returned for accounts {accounts}')
        return pd.DataFrame()

    # fiscal_year may come as string "2005.0"; convert via float first
    df['fiscal_year'] = df['fiscal_year'].astype(float).astype(int)
    df['original_enacted_budget'] = pd.to_numeric(df['original_enacted_budget'], errors='coerce')

    # Sum by fiscal year (multiple accounts per agency)
    summed = df.groupby('fiscal_year')['original_enacted_budget'].sum().reset_index()
    return summed


if __name__ == '__main__':
    # Load SSA AWI from CSV for inflation adjustment (2024 base year)
    # Read from CSV instead of DB since this runs before assemble_db.py creates tables
    awi = pd.read_csv('../docs/data/SSAWages.csv').set_index('Year')
    awi_base = float(awi.loc[2024, 'AWI'])

    print(f'Using 2024 AWI base year: ${awi_base:.2f}')

    # FY2001–FY2004: read DEP nominal from cached MassBudget summary CSV
    cached = pd.read_csv('../docs/data/MassBudget_environmental_summary.csv')
    early_dep = cached[cached['Year'] <= 2004][['Year', 'DEPAdministration_noinf']].copy()
    early_dep = early_dep.rename(columns={'DEPAdministration_noinf': 'DEPAdministration_noinf_float'})
    early_dep = early_dep.set_index('Year')

    result = early_dep.copy()

    # FY2005–present: fetch from CTHRU for all agencies
    for col, accounts in AGENCY_ACCOUNTS.items():
        print(f'Fetching {col} ({accounts})...')
        cthru = fetch_agency_budget(accounts)
        if not cthru.empty:
            cthru = cthru[cthru['fiscal_year'] >= 2005].copy()
            cthru = cthru.rename(
                columns={'fiscal_year': 'Year', 'original_enacted_budget': f'{col}_noinf_float'}
            )
            cthru = cthru.set_index('Year')
            # Only add new columns (don't overwrite early DEP data)
            new_cols = cthru.columns[~cthru.columns.isin(result.columns)]
            if len(new_cols) > 0:
                result = result.join(cthru[new_cols], how='outer')
            elif col == 'DEPAdministration':
                # For DEP, we may be overwriting FY2005+ with CTHRU data (both nominal)
                result = result.join(cthru, how='outer', rsuffix='_cthru')
                # Use CTHRU version for FY2005+, cached for FY2001-FY2004
                if f'{col}_noinf_float_cthru' in result.columns:
                    result.loc[result[f'{col}_noinf_float_cthru'].notna(), f'{col}_noinf_float'] = result.loc[result[f'{col}_noinf_float_cthru'].notna(), f'{col}_noinf_float_cthru']
                    result = result.drop(columns=[f'{col}_noinf_float_cthru'])
            else:
                result = result.join(cthru, how='outer')

    result = result.sort_index()

    # Inflation adjustment to 2024 dollars
    for col in AGENCY_ACCOUNTS:
        noinf = f'{col}_noinf_float'
        inf = f'{col}_inf_float'
        if noinf in result.columns:
            def apply_awi(year_val):
                year, val = year_val
                if pd.notna(val) and year in awi.index:
                    year_awi = float(awi.loc[year, 'AWI'])
                    return val * awi_base / year_awi
                return float('nan')

            result[inf] = result[noinf].apply(lambda v: apply_awi((result.index[result[noinf] == v][0], v)) if pd.notna(v) else float('nan'))

    # Simpler approach: iterate and compute
    for year in result.index:
        for col in AGENCY_ACCOUNTS:
            noinf = f'{col}_noinf_float'
            inf = f'{col}_inf_float'
            if noinf in result.columns:
                val = result.loc[year, noinf]
                if pd.notna(val) and year in awi.index:
                    year_awi = float(awi.loc[year, 'AWI'])
                    result.loc[year, inf] = val * awi_base / year_awi

    # Compute total across all four agencies
    noinf_cols = [f'{c}_noinf_float' for c in AGENCY_ACCOUNTS if f'{c}_noinf_float' in result.columns]
    inf_cols = [f'{c}_inf_float' for c in AGENCY_ACCOUNTS if f'{c}_inf_float' in result.columns]

    if noinf_cols:
        result['TotalBudget_noinf_float'] = result[noinf_cols].sum(axis=1, min_count=1)

    if inf_cols:
        result['TotalBudget_inf_float'] = result[inf_cols].sum(axis=1, min_count=1)

    # Format for output
    result['FiscalYear'] = result.index.map(lambda y: f'FY{str(y)[-2:]}')
    result['GovernorsBudget'] = 0

    result.index.name = 'Year'
    result_reset = result.reset_index()

    # Rename columns to remove _float suffix for Jekyll compatibility
    column_rename = {col: col.replace('_float', '') for col in result_reset.columns if '_float' in col}
    result_reset = result_reset.rename(columns=column_rename)

    # Write CSV to data directory (Jekyll loads from docs/data via data_dir: data in _config.yml)
    print('Writing CSV to ../docs/data/MassBudget_environmental_summary.csv...')
    result_reset.to_csv('../docs/data/MassBudget_environmental_summary.csv', index=False, encoding='ascii')
    print('✓ Public data file written')

    print('Writing timestamp to ../docs/data/ts_update_MassBudget_environmental.yml...')
    with open('../docs/data/ts_update_MassBudget_environmental.yml', 'w') as f:
        f.write('updated: ' + str(datetime.datetime.now()).split('.')[0] + '\n')
    print('✓ Timestamp written')

    print(f'\n✓ get_budget_CTHRU.py completed successfully')
    print(f'  Wrote {len(result)} rows: FY{result.index.min()}–FY{result.index.max()}')
    print('\nDEP Administration budget (inflation-adjusted to 2024 dollars):')
    print(result[['DEPAdministration_noinf_float', 'DEPAdministration_inf_float', 'TotalBudget_inf_float']].tail(10))
    print(f'\n[{datetime.datetime.now().isoformat()}] Script complete')
