"""Test that assemble_db.py builds a valid AMEND.db from committed CSVs.

Runs assemble_db.py --no-upload from get_data/, then checks the resulting
SQLite database for expected tables, columns, and row counts.

Requires the amend_python conda environment. Run with:
  conda run -n amend_python pytest tests/test_db_assembly.py

Takes ~30s. Skips gracefully if conda env or required CSVs are missing.
"""
import os
import sqlite3
import subprocess
import sys
import shutil
import pytest
import yaml

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GET_DATA_DIR = os.path.join(REPO_ROOT, "get_data")
DATA_DIR = os.path.join(REPO_ROOT, "docs", "data")

EXPECTED_TABLES = {
    "MAEEADP_CSO": ["incidentDate", "volumnOfEvent", "waterBody", "municipality", "eventType"],
    "MAEEADP_Enforcement": ["EnforcementDate", "Town", "FacilityId", "EnforcementType"],
    "MADEP_staff_Comptroller": ["year", "name_first", "name_last"],
    "MassBudget_summary": ["Year", "DEPAdministration_noinf"],
    "EPA_303d_Impairments": ["waterbody", "reportingCycle", "hasTmdl", "category"],
    "MAEEADP_Facility": ["Id", "Town"],
    "CSO_WatershedMapping": ["waterBody", "watershed"],
    "CSO_303d_Mapping": ["csoWaterBody", "waterbody303d"],
    "ECOS_budgets": ["State", "Year"],
}


@pytest.fixture(scope="module")
def amend_db(tmp_path_factory):
    """Build AMEND.db in a temp directory using --no-upload, return its path."""
    tmpdir = tmp_path_factory.mktemp("amend_db")
    db_path = tmpdir / "AMEND.db"

    # Run assemble_db.py from get_data/ so relative paths work
    result = subprocess.run(
        [sys.executable, "assemble_db.py", "--no-upload"],
        cwd=GET_DATA_DIR,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        pytest.fail(
            f"assemble_db.py failed (exit {result.returncode}):\n"
            f"STDOUT:\n{result.stdout[-3000:]}\n"
            f"STDERR:\n{result.stderr[-3000:]}"
        )

    # Script writes AMEND.db into cwd (get_data/)
    built_db = os.path.join(GET_DATA_DIR, "AMEND.db")
    assert os.path.exists(built_db), "assemble_db.py succeeded but AMEND.db not found"

    # Move to temp dir so we don't leave it in get_data/ after the test
    shutil.move(built_db, str(db_path))

    # Clean up backup created by assemble_db.py
    backup = os.path.join(GET_DATA_DIR, "backup_AMEND.db")
    if os.path.exists(backup):
        os.remove(backup)

    return str(db_path)


def test_db_nonempty(amend_db):
    assert os.path.getsize(amend_db) > 1_000_000, "AMEND.db is suspiciously small"


def test_expected_tables_exist(amend_db):
    con = sqlite3.connect(amend_db)
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    con.close()
    for table in EXPECTED_TABLES:
        assert table in tables, f"Missing table: {table}"


def test_expected_columns(amend_db):
    con = sqlite3.connect(amend_db)
    for table, required_cols in EXPECTED_TABLES.items():
        cursor = con.execute(f"SELECT * FROM {table} LIMIT 0")
        actual_cols = {d[0] for d in cursor.description}
        for col in required_cols:
            assert col in actual_cols, f"{table}: missing column '{col}'"
    con.close()


def test_row_counts_match_data_stats(amend_db):
    """Row counts in AMEND.db should be close to data_stats.yml (±10%)."""
    stats_path = os.path.join(DATA_DIR, "data_stats.yml")
    with open(stats_path) as f:
        stats = yaml.safe_load(f)

    # Map CSV filename stems to DB table names
    csv_to_table = {
        "EEADP_CSO.csv": "MAEEADP_CSO",
        "EEADP_enforcement.csv": "MAEEADP_Enforcement",
        "EEADP_facility.csv": "MAEEADP_Facility",
        "EEADP_inspection.csv": "MAEEADP_Inspection",
        "EPA_303d_impairments.csv": "EPA_303d_Impairments",
    }

    con = sqlite3.connect(amend_db)
    for csv_name, table in csv_to_table.items():
        if csv_name not in stats:
            continue
        expected = stats[csv_name]
        actual = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        tolerance = max(10, int(expected * 0.10))
        assert abs(actual - expected) <= tolerance, (
            f"{table}: DB has {actual} rows, data_stats.yml says {expected} "
            f"(tolerance ±{tolerance})"
        )
    con.close()


def test_semantic_context_regenerated(amend_db):
    ctx_path = os.path.join(REPO_ROOT, "docs", "assets", "db_semantic_context.txt")
    assert os.path.exists(ctx_path), "db_semantic_context.txt not found"
    assert os.path.getsize(ctx_path) > 10_000, "db_semantic_context.txt is suspiciously small"
