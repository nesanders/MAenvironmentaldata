"""Data integrity checks against committed CSVs in docs/data/.

Runs entirely offline against committed files — no network, no script execution.
Guards against: missing files, schema regressions, data truncation.
"""
import csv
import os
import pytest
import yaml

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "docs", "data")

# (relative path from DATA_DIR, min_rows, required_columns)
REQUIRED_FILES = [
    (
        "EEADP_CSO.csv",
        15000,
        ["incidentDate", "volumnOfEvent", "waterBody", "municipality", "eventType"],
    ),
    (
        "EEADP_enforcement.csv",
        10000,
        ["EnforcementDate", "Town", "FacilityId", "EnforcementType"],
    ),
    (
        "MADEP_staff_SODA.csv",
        500,
        ["year", "name_first", "name_last", "position_title"],
    ),
    (
        "MassBudget_environmental_summary.csv",
        20,
        ["Year", "DEPAdministration_noinf"],
    ),
    (
        "EPA_303d_impairments.csv",
        50000,
        ["waterbody", "reportingCycle", "hasTmdl", "category"],
    ),
    (
        "EEADP_facility.csv",
        10000,
        ["Id", "Town"],
    ),
    (
        "EEADP_inspection.csv",
        1000,
        ["FacilityId", "Town"],
    ),
    (
        "EPA_EJSCREEN_MA_2023.csv",
        1000,
        ["CNTY_NAME"],
    ),
    (
        "ECOS_budget_history.csv",
        10,
        ["State", "Year"],
    ),
    (
        "EPARegion1_NPDES_permit_data.csv",
        100,
        ["Permit_Number"],
    ),
    (
        "MA_precipitation_daily.csv",
        1000,
        ["date", "precip_in_avg"],
    ),
]


@pytest.mark.parametrize(
    "relpath,min_rows,required_cols",
    REQUIRED_FILES,
    ids=[f[0] for f in REQUIRED_FILES],
)
def test_csv_exists_and_has_rows(relpath, min_rows, required_cols):
    path = os.path.join(DATA_DIR, relpath)
    assert os.path.exists(path), f"Missing: {relpath}"
    assert os.path.getsize(path) > 0, f"Empty file: {relpath}"

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        row_count = sum(1 for _ in reader)

    for col in required_cols:
        assert col in header, f"{relpath}: missing column '{col}' (found: {header[:10]})"

    assert row_count >= min_rows, (
        f"{relpath}: only {row_count} rows, expected >= {min_rows}"
    )


def test_data_stats_yml_parseable():
    path = os.path.join(DATA_DIR, "data_stats.yml")
    assert os.path.exists(path), "Missing docs/data/data_stats.yml"
    with open(path) as f:
        stats = yaml.safe_load(f)
    assert isinstance(stats, dict), "data_stats.yml should parse to a dict"
    assert len(stats) > 0, "data_stats.yml is empty"


def test_data_stats_consistent_with_files():
    """Row counts in data_stats.yml should be within 10% of actual file row counts."""
    stats_path = os.path.join(DATA_DIR, "data_stats.yml")
    with open(stats_path) as f:
        stats = yaml.safe_load(f)

    for filename, expected_rows in stats.items():
        filepath = os.path.join(DATA_DIR, filename)
        if not os.path.exists(filepath) or not filename.endswith(".csv"):
            continue
        with open(filepath, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            actual_rows = sum(1 for _ in reader)
        tolerance = max(10, int(expected_rows * 0.10))
        assert abs(actual_rows - expected_rows) <= tolerance, (
            f"{filename}: data_stats.yml says {expected_rows} rows, "
            f"file has {actual_rows} (tolerance ±{tolerance})"
        )
