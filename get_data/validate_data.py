"""Validate freshly fetched data before it overwrites committed CSVs.

Checks for each dataset:
  - Required columns are present
  - Row count has not decreased vs. the last recorded run (data_stats.yml)

On success: updates data_stats.yml with new row counts.
On failure: exits with code 1 so the CI workflow stops before committing.

Run from the get_data/ directory (same as the other fetch scripts).
"""

import sys
import os
import pandas as pd
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / 'docs' / 'data'
STATS_FILE = DATA_DIR / 'data_stats.yml'

# Each entry: CSV path (relative to DATA_DIR) -> list of required columns.
# Only columns critical for downstream analysis are listed; extras are fine.
DATASETS = {
    'EPARegion1_NPDES_permit_data.csv': [
        'State', 'Stage', 'Facility_Name', 'Permit_Number',
    ],
    'MADEP_enforcement_actions.csv': [
        'Year',
    ],
    'MADEP_staff.csv': [
        'CalendarYear',
    ],
    'MADEP_staff_SODA.csv': [
        'year',
    ],
    'MassBudget_environmental_infadjusted.csv': [],
    'MassBudget_environmental_noinfadjusted.csv': [],
    'MassBudget_environmental_summary.csv': [],
    'EEADP_permit.csv': [
        'FacilityName', 'PermitNumber', 'PermitType',
    ],
    'EEADP_facility.csv': [
        'FacilityName', 'FacilityType', 'Town',
    ],
    'EEADP_inspection.csv': [
        'FacilityName', 'InspectionDate', 'InspectionType',
    ],
    'EEADP_enforcement.csv': [
        'FacilityName', 'EnforcementDate', 'EnforcementType',
    ],
    'EEADP_CSO.csv': [
        'incidentId', 'incidentDate',
    ],
    'MA_precipitation_daily.csv': [
        'date', 'precip_in_avg', 'n_stations',
    ],
    'EPA_303d_impairments.csv': [
        'reportingCycle', 'auId', 'waterbody', 'watershed', 'waterType',
        'category', 'designatedUse', 'attainment',
    ],
    # Lobbying tables — present only after get_MA_lobbying.py has run at least once.
    # validate_data.py skips missing files gracefully (file-not-found check below).
    'MA_lobbying_employers.csv': ['entity_name', 'year'],
    'MA_lobbying_lobbyists.csv': ['lobbyist_name', 'entity_name', 'year'],
    'MA_lobbying_bills.csv': ['bill_number', 'general_court', 'entity_name', 'year'],
    'MA_legislature_bills.csv': ['bill_number', 'general_court', 'title'],
    # Archive-derived fields (reparse_lobbying_archive.py)
    'MA_lobbying_campaign_contributions.csv': ['entity_name', 'year', 'recipient_name', 'amount'],
    'MA_lobbying_expenses.csv': ['entity_name', 'year', 'expense_type', 'amount'],
    'MA_lobbying_client_purposes.csv': ['entity_name', 'client_name', 'year'],
}

# Minimum absolute row counts as a hard floor (catches total fetch failures).
MIN_ROWS = {
    'EPARegion1_NPDES_permit_data.csv': 500,
    'EEADP_permit.csv': 1000,
    'EEADP_facility.csv': 1000,
    'EEADP_inspection.csv': 1000,
    'EEADP_enforcement.csv': 100,
    'EEADP_CSO.csv': 100,
    'MA_precipitation_daily.csv': 8000,  # ~25 years × 365 days
    'EPA_303d_impairments.csv': 80000,  # 6 cycles × ~14k+ rows each
    # Lobbying tables — populated after first full fetch (~2007–present)
    'MA_lobbying_employers.csv': 500,
    'MA_lobbying_lobbyists.csv': 500,
    'MA_lobbying_bills.csv': 1000,
    'MA_legislature_bills.csv': 500,
}

# Files that are not yet present on first CI run (populated by optional/manual fetch steps).
# Missing files in this set produce a warning rather than a validation failure.
OPTIONAL_DATASETS = {
    'MA_lobbying_employers.csv',
    'MA_lobbying_lobbyists.csv',
    'MA_lobbying_bills.csv',
    'MA_legislature_bills.csv',
    'MA_lobbying_campaign_contributions.csv',
    'MA_lobbying_expenses.csv',
    'MA_lobbying_client_purposes.csv',
}

# Allow small row decreases (%) due to data source updates, API changes, etc.
# Only datasets prone to churn (EEA portal data) get tolerance; others must stay stable.
ROW_DECREASE_TOLERANCE_PCT = {
    'EEADP_permit.csv': 1.0,      # EEA API may drop/merge permits
    'EEADP_facility.csv': 1.0,    # EEA API may drop/merge facilities
    'EEADP_inspection.csv': 1.0,  # EEA API data source updates
    'EEADP_enforcement.csv': 1.0, # EEA API data source updates
}


def load_stats() -> dict:
    if not STATS_FILE.exists():
        return {}
    stats = {}
    with open(STATS_FILE) as f:
        for line in f:
            line = line.strip()
            if ':' in line:
                filename, _, rest = line.partition(':')
                try:
                    stats[filename.strip()] = {'rows': int(rest.strip())}
                except ValueError:
                    pass
    return stats


def save_stats(stats: dict) -> None:
    with open(STATS_FILE, 'w') as f:
        for filename in sorted(stats):
            f.write(f"{filename}: {stats[filename]['rows']}\n")


def validate() -> bool:
    stats = load_stats()
    new_stats = {}
    failures = []

    for filename, required_cols in DATASETS.items():
        path = DATA_DIR / filename
        if not path.exists():
            if filename in OPTIONAL_DATASETS:
                print(f'  SKIP {filename}: not yet fetched (optional dataset)')
                continue
            failures.append(f'MISSING FILE: {filename}')
            continue

        try:
            df = pd.read_csv(path, nrows=0)  # header only for column check
            actual_cols = set(df.columns)
        except Exception as e:
            failures.append(f'UNREADABLE: {filename}: {e}')
            continue

        # Column check
        missing_cols = [c for c in required_cols if c not in actual_cols]
        if missing_cols:
            failures.append(
                f'MISSING COLUMNS in {filename}: {missing_cols}'
            )

        # Row count (re-read with data)
        try:
            row_count = sum(1 for _ in open(path)) - 1  # fast line count
        except Exception as e:
            failures.append(f'CANNOT COUNT ROWS in {filename}: {e}')
            continue

        # Hard floor
        min_rows = MIN_ROWS.get(filename, 1)
        if row_count < min_rows:
            failures.append(
                f'TOO FEW ROWS in {filename}: got {row_count}, minimum {min_rows}'
            )

        # Regression vs previous run (with tolerance for data source updates)
        prev_count = stats.get(filename, {}).get('rows')
        if prev_count is not None and row_count < prev_count:
            tolerance_pct = ROW_DECREASE_TOLERANCE_PCT.get(filename, 0.0)
            max_allowed = int(prev_count * (1.0 - tolerance_pct / 100.0))
            if row_count < max_allowed:
                failures.append(
                    f'ROW COUNT DECREASED in {filename}: '
                    f'was {prev_count}, now {row_count} (tolerance: -{tolerance_pct}%)'
                )

        new_stats[filename] = {'rows': row_count}
        print(
            f'  OK  {filename}: {row_count} rows'
            + (f' (was {prev_count})' if prev_count else ' (first run)')
        )

    if failures:
        print('\nValidation FAILED:')
        for f in failures:
            print(f'  FAIL  {f}')
        return False

    save_stats(new_stats)
    print('\nAll validation checks passed. data_stats.yml updated.')
    return True


if __name__ == '__main__':
    print('Validating fetched data...\n')
    ok = validate()
    sys.exit(0 if ok else 1)
