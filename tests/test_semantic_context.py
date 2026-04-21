"""Structural checks for docs/assets/db_semantic_context.txt.

Verifies that the generated semantic context stays in sync with AMEND.db as
new tables are added:
  - Every table in AMEND.db has a ### section in the context
  - Key ALL-CAPS geographic columns are documented as such
  - Key Join Relationships section is present and non-empty
  - Sample rows exist for every table not in SKIP_SAMPLE_TABLES

The DB path is skipped gracefully when AMEND.db is not present (same as
test_db_assembly.py / test_semantic_evals.py).
"""
import os
import re
import sqlite3

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTEXT_PATH = os.path.join(REPO_ROOT, "docs", "assets", "db_semantic_context.txt")
DB_CANDIDATES = [
    os.path.join(REPO_ROOT, "get_data", "AMEND.db"),
    os.path.join(REPO_ROOT, "AMEND.db"),
]

# Tables that are internal housekeeping and intentionally excluded from the context.
INTERNAL_TABLES = {"AMEND_metadata"}

# Tables where sample rows are intentionally omitted (too wide).
# Kept in sync with generate_semantic_context.py:SKIP_SAMPLE_TABLES.
SKIP_SAMPLE_TABLES = {
    "MassBudget_infadjusted",
    "MassBudget_noinfadjusted",
    "EPA_EJSCREEN_2017",
    "EPA_EJSCREEN_2023",
}

# Geographic text columns that must be documented as ALL CAPS in the context.
ALL_CAPS_COLUMNS = ["municipality", "Town", "waterBody", "DischargesBody"]



# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def context_text():
    assert os.path.exists(CONTEXT_PATH), f"Semantic context not found: {CONTEXT_PATH}"
    with open(CONTEXT_PATH) as f:
        return f.read()


@pytest.fixture(scope="module")
def db_tables():
    """Return the set of table names from AMEND.db, or skip if DB absent."""
    db_path = next((p for p in DB_CANDIDATES if os.path.exists(p)), None)
    if db_path is None:
        pytest.skip("AMEND.db not found — skipping DB-driven context checks")
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    finally:
        con.close()
    return {r[0] for r in rows}


def _section_for_table(context_text, table_name):
    """Return the text of the ### TableName section, or empty string."""
    pattern = rf"(### {re.escape(table_name)} \(.*?\n[\s\S]*?)(?=\n### |\Z)"
    m = re.search(pattern, context_text)
    return m.group(1) if m else ""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_join_relationships_present(context_text):
    """Key Join Relationships section must exist and contain at least 3 join entries."""
    assert "## Key Join Relationships" in context_text
    section_start = context_text.index("## Key Join Relationships")
    section_end = context_text.find("\n---", section_start)
    section = context_text[section_start:section_end] if section_end != -1 else context_text[section_start:]
    join_bullets = [ln for ln in section.splitlines() if ln.strip().startswith("- ")]
    assert len(join_bullets) >= 3, (
        f"Expected ≥3 join relationship bullets, found {len(join_bullets)}"
    )


@pytest.mark.parametrize("col", ALL_CAPS_COLUMNS)
def test_all_caps_column_documented(context_text, col):
    """Each known ALL-CAPS column must appear in a context that also mentions ALL CAPS or UPPER.

    The Global Data Notes section lists all such columns alongside an ALL CAPS warning and
    UPPER() usage examples — we check that both the column name and the pattern appear in
    that preamble (before the Table Schemas divider).
    """
    marker = "\n## Table Schemas and Sample Data"
    preamble = context_text[: context_text.find(marker)] if marker in context_text else context_text
    assert col in preamble, (
        f"Column '{col}' not mentioned in the semantic context preamble"
    )
    assert re.search(r"ALL\s+CAPS|UPPER\s*\(", preamble, re.IGNORECASE), (
        "Preamble does not contain an ALL CAPS / UPPER() warning"
    )



def test_every_db_table_has_section(context_text, db_tables):
    """Every table in AMEND.db must have a ### TableName section in the context."""
    missing = []
    for table in sorted(db_tables - INTERNAL_TABLES):
        if not re.search(rf"^### {re.escape(table)} \(", context_text, re.MULTILINE):
            missing.append(table)
    assert not missing, (
        f"Tables in AMEND.db with no section in db_semantic_context.txt:\n"
        + "\n".join(f"  - {t}" for t in missing)
    )


def test_sample_rows_present_for_all_tables(context_text, db_tables):
    """Every non-skipped table must have at least one sample data row."""
    missing = []
    for table in sorted(db_tables):
        if table in SKIP_SAMPLE_TABLES:
            continue
        section = _section_for_table(context_text, table)
        if not section:
            continue  # caught by test_every_db_table_has_section
        # Sample block looks like: /* 5 rows from TableName:\ncol1\tcol2\nrow...\n*/
        sample_match = re.search(
            rf"/\* \d+ rows? from {re.escape(table)}:(.*?)\*/",
            section,
            re.DOTALL,
        )
        if not sample_match:
            missing.append(table)
            continue
        # Must have at least one data line after the header line
        lines = [ln for ln in sample_match.group(1).strip().splitlines() if ln.strip()]
        if len(lines) < 2:  # header + at least one data row
            missing.append(table)
    assert not missing, (
        f"Tables missing sample rows in db_semantic_context.txt:\n"
        + "\n".join(f"  - {t}" for t in missing)
    )
