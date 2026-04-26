"""Unit tests for get_MS4_annual_reports.py logic — no API calls, no network.

Tests that work offline:
  - estimate_cost: arithmetic sanity
  - get_page_count: normal PDF, XFA form, corrupt/missing file
  - extract_xfa_xml: returns valid XML with expected municipality field
  - URL regex: scrape_report_index filename/year/municipality parsing
  - _flatten_result: full flat-row structure from a mock Gemini result dict
"""
import importlib.util
import json
import os
import re

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_PATH = os.path.join(REPO_ROOT, "get_data", "get_MS4_annual_reports.py")
FIXTURES_DIR = os.path.join(REPO_ROOT, "tests", "fixtures")

# Load the module without executing __main__
spec = importlib.util.spec_from_file_location("get_MS4_annual_reports", SCRIPT_PATH)
ms4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ms4)

NORMAL_PDF = os.path.join(FIXTURES_DIR, "palmer-ma-ar20.pdf")
XFA_PDF = os.path.join(FIXTURES_DIR, "cambridge_ma_ar25.pdf")


# ---------------------------------------------------------------------------
# estimate_cost
# ---------------------------------------------------------------------------

def test_estimate_cost_zero_pages():
    cost = ms4.estimate_cost(0)
    assert cost >= 0


def test_estimate_cost_scales_with_pages():
    cost_10 = ms4.estimate_cost(10)
    cost_20 = ms4.estimate_cost(20)
    assert cost_20 > cost_10


def test_estimate_cost_reasonable_range():
    # A 24-page report should cost between $0.001 and $0.05
    cost = ms4.estimate_cost(24)
    assert 0.001 < cost < 0.05


# ---------------------------------------------------------------------------
# get_page_count — normal PDF
# ---------------------------------------------------------------------------

def test_get_page_count_normal_pdf():
    pages, fmt = ms4.get_page_count(NORMAL_PDF)
    assert fmt is None
    assert pages > 1


# ---------------------------------------------------------------------------
# get_page_count — XFA form
# ---------------------------------------------------------------------------

def test_get_page_count_xfa_pdf():
    pages, fmt = ms4.get_page_count(XFA_PDF)
    assert fmt == "xfa"
    assert pages <= 2


# ---------------------------------------------------------------------------
# get_page_count — unreadable / missing
# ---------------------------------------------------------------------------

def test_get_page_count_missing_file(tmp_path):
    pages, fmt = ms4.get_page_count(str(tmp_path / "nonexistent.pdf"))
    assert fmt == "unreadable"
    assert pages is None


def test_get_page_count_corrupt_file(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"this is not a pdf")
    pages, fmt = ms4.get_page_count(str(bad))
    assert fmt == "unreadable"
    assert pages is None


# ---------------------------------------------------------------------------
# extract_xfa_xml
# ---------------------------------------------------------------------------

def test_extract_xfa_xml_returns_string():
    xml = ms4.extract_xfa_xml(XFA_PDF)
    assert xml is not None
    assert isinstance(xml, str)
    assert len(xml) > 1000


def test_extract_xfa_xml_cambridge_content():
    xml = ms4.extract_xfa_xml(XFA_PDF)
    assert "Cambridge" in xml
    assert "Municipality" in xml
    # MCM3 illicit discharge fields should be present
    assert "Illicit" in xml
    # MCM6 catch basin count
    assert "Num_CBs_Inspected" in xml


def test_extract_xfa_xml_is_valid_xml():
    import xml.etree.ElementTree as ET
    xml = ms4.extract_xfa_xml(XFA_PDF)
    # Should parse without error
    root = ET.fromstring(xml)
    assert root is not None


# ---------------------------------------------------------------------------
# URL / filename parsing (scrape_report_index regex logic)
# ---------------------------------------------------------------------------

# Replicate the regex logic from scrape_report_index for unit testing
_FILENAME_RE = re.compile(r"-ma-ar\d+\.pdf$|_ma_ar\d+\.pdf$", re.IGNORECASE)
_YEAR_RE = re.compile(r"ar(\d+)\.pdf$", re.IGNORECASE)
_MUNI_RE = re.compile(r"[-_]ma[-_]ar\d+\.pdf$", re.IGNORECASE)


def _parse_filename(filename):
    m = _YEAR_RE.search(filename)
    year = m.group(1) if m else None
    muni_raw = _MUNI_RE.sub("", filename)
    muni = muni_raw.replace("-", " ").replace("_", " ").title().strip()
    return year, muni


@pytest.mark.parametrize("filename,expected_year,expected_muni", [
    ("palmer-ma-ar20.pdf", "20", "Palmer"),
    ("andover_ma_ar21.pdf", "21", "Andover"),
    ("new_bedford_ma_ar25.pdf", "25", "New Bedford"),
    ("cambridge_ma_ar25.pdf", "25", "Cambridge"),
    ("worcester_state_university_ma_ar25.pdf", "25", "Worcester State University"),
])
def test_filename_parsing(filename, expected_year, expected_muni):
    year, muni = _parse_filename(filename)
    assert year == expected_year
    assert muni == expected_muni


@pytest.mark.parametrize("filename,should_match", [
    ("palmer-ma-ar20.pdf", True),
    ("andover_ma_ar21.pdf", True),
    ("unrelated-document.pdf", False),
    ("ma-ar20-wrong.pdf", False),
])
def test_filename_regex_matches(filename, should_match):
    assert bool(_FILENAME_RE.search(filename)) == should_match


# ---------------------------------------------------------------------------
# _flatten_result: flat CSV row builder
# ---------------------------------------------------------------------------

def _make_mock_result():
    """Build a realistic mock Gemini extraction result dict."""
    return {
        "source_url": "https://www.epa.gov/system/files/documents/2026-04/palmer-ma-ar20.pdf",
        "municipality": "Town of Palmer",
        "permit_number": "MAR041017",
        "report_year": 2020,
        "permit_year": 2.0,   # Gemini returns floats
        "report_period_start": "2019-07-01",
        "report_period_end": "2020-06-30",
        "source_page_refs": {"mcm3_idde": [4, 5], "tmdl": [12]},
        "mcm1_public_education": {"activities_count": 5, "notes": "Five events held."},
        "mcm2_public_participation": {"activities_count": 2},
        "mcm3_idde": {
            "outfalls_total": 42,
            "outfalls_screened": 40,
            "outfalls_not_accessed": 2,
            "illicit_discharges_found": 1,
            "illicit_discharges_eliminated": 1,
            "count_type": "current_period",
            "sampling_conducted": True,
        },
        "mcm4_construction": {"sites_inspected": 10, "violations_found": 2},
        "mcm5_post_construction": {"sites_inspected": 3, "bmps_inspected": 5},
        "mcm6_pollution_prevention": {"facilities_inspected": 95, "notes": "Catch basins only."},
        "system_mapping_pct_complete": 80.0,
        "tmdl_municipality_specific": True,
        "tmdl_waterbodies": [
            {"waterbody": "Farmers Pond", "pollutant": "Phosphorus",
             "reduction_achieved_lbs_per_year": 10.5,
             "wasteload_allocation_lbs_per_year": 50.0, "source_page": 12}
        ],
        "compliance_issues": None,
        "extraction_confidence": "high",
        "extraction_notes": "All sections found.",
        "pdf_pages": 28,
        "estimated_cost_usd": 0.009,
    }


def _flatten(r):
    return ms4._flatten_result(r)


def test_flatten_basic_fields():
    r = _make_mock_result()
    flat = _flatten(r)
    assert flat["municipality"] == "Town of Palmer"
    assert flat["permit_number"] == "MAR041017"
    assert flat["report_year"] == 2020


def test_flatten_permit_year_cast_from_float():
    r = _make_mock_result()
    flat = _flatten(r)
    assert flat["permit_year"] == 2
    assert isinstance(flat["permit_year"], int)


def test_flatten_gcs_url_constructed():
    r = _make_mock_result()
    flat = _flatten(r)
    assert flat["gcs_url"] == f"{ms4.GCS_PUBLIC_BASE}/palmer-ma-ar20.pdf"


def test_flatten_idde_fields():
    r = _make_mock_result()
    flat = _flatten(r)
    assert flat["mcm3_outfalls_total"] == 42
    assert flat["mcm3_illicit_found"] == 1
    assert flat["mcm3_count_type"] == "current_period"
    assert flat["mcm3_sampling_conducted"] is True


def test_flatten_tmdl_json_parseable():
    r = _make_mock_result()
    flat = _flatten(r)
    tmdl = json.loads(flat["tmdl_waterbodies_json"])
    assert len(tmdl) == 1
    assert tmdl[0]["waterbody"] == "Farmers Pond"
    assert tmdl[0]["pollutant"] == "Phosphorus"
    assert tmdl[0]["reduction_achieved_lbs_per_year"] == 10.5


def test_flatten_source_page_refs_json():
    r = _make_mock_result()
    flat = _flatten(r)
    refs = json.loads(flat["source_page_refs"])
    assert refs["mcm3_idde"] == [4, 5]


def test_flatten_missing_sections_are_none():
    r = {"source_url": "https://example.com/test.pdf",
         "extraction_confidence": "low", "extraction_notes": "failed"}
    flat = _flatten(r)
    assert flat["municipality"] is None
    assert flat["mcm3_outfalls_total"] is None
    assert flat["permit_year"] is None
    assert flat["tmdl_waterbodies_json"] == "[]"
    assert flat["gcs_url"] == f"{ms4.GCS_PUBLIC_BASE}/test.pdf"


def test_flatten_permit_year_none_stays_none():
    r = _make_mock_result()
    r["permit_year"] = None
    flat = _flatten(r)
    assert flat["permit_year"] is None


# ---------------------------------------------------------------------------
# Truncation: prepare_upload_pdf
# ---------------------------------------------------------------------------

def _make_pdf(path, n_pages):
    """Write a synthetic n-page PDF to path."""
    import fitz
    doc = fitz.open()
    for i in range(n_pages):
        doc.new_page().insert_text((72, 72), f"Page {i + 1}")
    doc.save(str(path))
    doc.close()


def test_prepare_upload_pdf_no_truncation_needed(tmp_path):
    src = tmp_path / "short.pdf"
    _make_pdf(src, 5)
    upload_path, tmp_path_out = ms4.prepare_upload_pdf(str(src), max_pages=10)
    assert upload_path == str(src)
    assert tmp_path_out is None


def test_prepare_upload_pdf_truncates(tmp_path):
    import fitz
    src = tmp_path / "long.pdf"
    _make_pdf(src, 10)
    upload_path, tmp_path_out = ms4.prepare_upload_pdf(str(src), max_pages=4)
    try:
        assert upload_path != str(src)
        assert tmp_path_out == upload_path
        doc = fitz.open(upload_path)
        assert len(doc) == 4
        doc.close()
    finally:
        if tmp_path_out:
            os.unlink(tmp_path_out)


def test_prepare_upload_pdf_exact_limit_not_truncated(tmp_path):
    src = tmp_path / "exact.pdf"
    _make_pdf(src, ms4.MAX_PAGE_GUARD)
    upload_path, tmp_path_out = ms4.prepare_upload_pdf(str(src), max_pages=ms4.MAX_PAGE_GUARD)
    assert upload_path == str(src)
    assert tmp_path_out is None


# ---------------------------------------------------------------------------
# Sample: apply_sample
# ---------------------------------------------------------------------------

def test_apply_sample_reduces_queue():
    queue = list(range(100))
    sampled = ms4.apply_sample(queue, 0.1)
    assert len(sampled) == 10


def test_apply_sample_full_fraction():
    queue = list(range(50))
    sampled = ms4.apply_sample(queue, 1.0)
    assert len(sampled) == 50


def test_apply_sample_tiny_queue_returns_at_least_one():
    queue = [("a", "b", 1, 0.001, False)]
    sampled = ms4.apply_sample(queue, 0.01)
    assert len(sampled) == 1


def test_apply_sample_returns_subset_of_original():
    queue = list(range(200))
    sampled = ms4.apply_sample(queue, 0.05)
    assert all(item in queue for item in sampled)
