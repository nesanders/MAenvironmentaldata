"""Scrape, download, and extract structured data from MA MS4 annual report PDFs.

MS4 (Municipal Separate Storm Sewer System) annual reports are submitted by ~150+
Massachusetts municipalities to EPA Region 1 under their NPDES Phase II stormwater
permits.  This script:

  1. Scrapes the EPA MS4 community page to build an index of available PDF reports.
  2. Downloads new PDFs incrementally to a local directory and syncs to GCS.
  3. Extracts structured data from each PDF using Gemini 2.0 Flash (function calling),
     capturing source page references for manual verification.
  4. Writes extracted data to CSV.

Usage:
  python get_MS4_annual_reports.py              # full run (scrape + download + extract)
  python get_MS4_annual_reports.py --test       # 3 test PDFs only
  python get_MS4_annual_reports.py --dry-run    # estimate costs, no API calls
  python get_MS4_annual_reports.py --skip-download  # skip download phase, extract only

Outputs (relative to get_data/ working directory):
  ../docs/data/MS4_report_index.csv    index of all discovered reports
  ../docs/data/MS4_extracted.csv       extracted structured data
  ../docs/data/ts_update_MS4.yml       timestamp of last run
  MS4_annual_reports/                  local PDF cache
  gs://openamend-data/MS4_annual_reports/   GCS copy of PDFs

Environment:
  GOOGLE_API_KEY   required for extraction phase

Run from get_data/ directory:
  conda run -n amend_python python get_MS4_annual_reports.py --test
"""

import argparse
import datetime
import json
import os
import re
import shlex
import time

import fitz  # PyMuPDF
import pandas as pd
import pdfplumber
import requests
from bs4 import BeautifulSoup
from google import genai
from google.genai import types

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MS4_INDEX_URL = "https://www.epa.gov/npdes-permits/regulated-ms4-massachusetts-communities"
MS4_DIR = "MS4_annual_reports"
GS_BUCKET = "gs://openamend-data/MS4_annual_reports"
GCS_PUBLIC_BASE = "https://storage.googleapis.com/openamend-data/MS4_annual_reports"
INDEX_CSV = "../docs/data/MS4_report_index.csv"
EXTRACTED_CSV = "../docs/data/MS4_extracted.csv"
TIMESTAMP_YML = "../docs/data/ts_update_MS4.yml"

GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_INPUT_PRICE_PER_M = 0.15   # USD per million input tokens (gemini-2.5-flash)
GEMINI_OUTPUT_PRICE_PER_M = 0.60  # USD per million output tokens
TOKENS_PER_PAGE_ESTIMATE = 2000   # conservative estimate for cost pre-check
OUTPUT_TOKENS_ESTIMATE = 800      # per extraction call
MAX_PAGE_GUARD = 80               # skip PDFs over this page count (likely has bundled attachments)

COST_THRESHOLD_TEST = 0.00        # always confirm in test mode
COST_THRESHOLD_FULL = 20.00       # prompt before full runs exceeding this

# Three test PDFs spanning different municipality sizes, permit years, complexity.
TEST_PDFS = [
    {
        "url": "https://www.epa.gov/system/files/documents/2026-04/palmer-ma-ar20.pdf",
        "filename": "palmer-ma-ar20.pdf",
        "municipality": "Palmer",
    },
    {
        "url": "https://www.epa.gov/system/files/documents/2026-04/andover_ma_ar21.pdf",
        "filename": "andover_ma_ar21.pdf",
        "municipality": "Andover",
    },
    {
        "url": "https://s3.amazonaws.com/somervillema-live/s3fs-public/annual-report-year-5-ms4.pdf",
        "filename": "somerville-ma-ar-year5.pdf",
        "municipality": "Somerville",
    },
]

# ---------------------------------------------------------------------------
# Gemini extraction schema (function calling)
# ---------------------------------------------------------------------------

_EXTRACTION_PARAMETERS = {
    "type": "object",
    "properties": {
        "municipality": {"type": "string", "description": "Municipality or town name"},
        "permit_number": {"type": "string", "description": "NPDES permit number (e.g. MAR041234)"},
        "report_year": {"type": "integer", "description": "Calendar year the report covers"},
        "permit_year": {"type": "integer", "description": "Permit year number (1 through 7)"},
        "report_period_start": {"type": "string", "description": "Report period start date YYYY-MM-DD"},
        "report_period_end": {"type": "string", "description": "Report period end date YYYY-MM-DD"},
        "source_page_refs": {
            "type": "object",
            "description": "Maps schema section names to PDF page numbers where that data appears",
            "properties": {
                "mcm1": {"type": "array", "items": {"type": "integer"}},
                "mcm2": {"type": "array", "items": {"type": "integer"}},
                "mcm3_idde": {"type": "array", "items": {"type": "integer"}},
                "mcm4_construction": {"type": "array", "items": {"type": "integer"}},
                "mcm5_post_construction": {"type": "array", "items": {"type": "integer"}},
                "mcm6_pollution_prevention": {"type": "array", "items": {"type": "integer"}},
                "tmdl": {"type": "array", "items": {"type": "integer"}},
            },
        },
        "mcm1_public_education": {
            "type": "object",
            "properties": {
                "activities_count": {"type": "integer", "description": "Number of outreach activities or events"},
                "notes": {"type": "string"},
            },
        },
        "mcm2_public_participation": {
            "type": "object",
            "properties": {
                "activities_count": {"type": "integer", "description": "Number of participation events or meetings"},
            },
        },
        "mcm3_idde": {
            "type": "object",
            "properties": {
                "outfalls_total": {"type": "integer", "description": "Total outfalls in the MS4 system"},
                "outfalls_screened": {"type": "integer", "description": "Outfalls screened/inspected this period"},
                "outfalls_not_accessed": {"type": "integer", "description": "Outfalls that could not be found or accessed"},
                "illicit_discharges_found": {"type": "integer"},
                "illicit_discharges_eliminated": {"type": "integer"},
                "count_type": {
                    "type": "string",
                    "enum": ["current_period", "cumulative_since_permit_start", "unknown"],
                    "description": "Whether illicit discharge counts are for this period only or cumulative since permit start",
                },
                "sampling_conducted": {"type": "boolean", "description": "Whether outfall water quality sampling was conducted"},
            },
        },
        "mcm4_construction": {
            "type": "object",
            "properties": {
                "sites_inspected": {"type": "integer"},
                "violations_found": {"type": "integer"},
            },
        },
        "mcm5_post_construction": {
            "type": "object",
            "properties": {
                "sites_inspected": {"type": "integer", "description": "Number of post-construction BMP sites inspected"},
                "bmps_inspected": {"type": "integer", "description": "Number of individual BMP structures inspected"},
            },
        },
        "mcm6_pollution_prevention": {
            "type": "object",
            "properties": {
                "facilities_inspected": {"type": "integer", "description": "Municipal facilities or catch basins inspected"},
                "notes": {"type": "string", "description": "Clarify if count refers to catch basins, facilities, or other"},
            },
        },
        "system_mapping_pct_complete": {"type": "number", "description": "Percent of stormwater system mapping completed (0-100)"},
        "tmdl_municipality_specific": {
            "type": "boolean",
            "description": "True if TMDL list contains only TMDLs applicable to this municipality; false if it is the general permit's full MA TMDL list",
        },
        "tmdl_waterbodies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "waterbody": {"type": "string"},
                    "pollutant": {"type": "string"},
                    "reduction_achieved_pct": {"type": "number"},
                    "wasteload_allocation_pct": {"type": "number"},
                    "reduction_achieved_lbs_per_year": {"type": "number", "description": "Reduction in lbs/year if reported instead of percent"},
                    "wasteload_allocation_lbs_per_year": {"type": "number", "description": "Allocation target in lbs/year if reported instead of percent"},
                    "source_page": {"type": "integer"},
                },
                "required": ["waterbody", "pollutant"],
            },
        },
        "compliance_issues": {"type": "string", "description": "Any compliance violations or NOVs mentioned"},
        "extraction_confidence": {
            "type": "string",
            "enum": ["high", "medium", "low"],
            "description": "high: all major sections found; medium: some sections missing or ambiguous; low: scanned/poor quality or major gaps",
        },
        "extraction_notes": {"type": "string", "description": "Notes on data quality, missing sections, or ambiguities"},
    },
    "required": ["municipality", "extraction_confidence", "extraction_notes"],
}

EXTRACTION_FUNCTION_DECL = types.FunctionDeclaration(
    name="extract_ms4_data",
    description=(
        "Extract structured data from an MS4 annual report PDF. "
        "Return null for any field not found in the document. "
        "Include source_page_refs indicating which PDF page numbers contain each section."
    ),
    parameters=_EXTRACTION_PARAMETERS,
)

EXTRACTION_PROMPT = """You are extracting structured data from a Massachusetts MS4 (Municipal Separate Storm Sewer System) annual report.

Extract all available data according to the function schema. Key guidance:
- MCM sections (Minimum Control Measures) are the six required program elements.
- For activity counts, extract the total number reported for the permit year.
- For TMDL sections: extract each listed waterbody, its target pollutant, percent reduction achieved if stated, and the wasteload allocation target percent if stated.
- Record source_page_refs: the PDF page number(s) where you found each section.
- If a field is not present or clearly stated, return null (omit the field).
- Set extraction_confidence=low if the PDF appears to be scanned/non-text, or if major required sections are absent.
- In extraction_notes, flag any ambiguities, merged sections, or fields you are uncertain about.
"""

# ---------------------------------------------------------------------------
# Phase 1: Scrape report index
# ---------------------------------------------------------------------------

def scrape_report_index():
    """Parse the EPA MS4 MA community page and return a DataFrame of report URLs."""
    print(f"Scraping {MS4_INDEX_URL} ...")
    resp = requests.get(MS4_INDEX_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    rows = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Match filenames like palmer-ma-ar20.pdf or andover_ma_ar21.pdf
        if re.search(r"-ma-ar\d+\.pdf$|_ma_ar\d+\.pdf$", href, re.IGNORECASE):
            full_url = href if href.startswith("http") else "https://www.epa.gov" + href
            filename = full_url.split("/")[-1]
            # Extract year digits from filename
            m = re.search(r"ar(\d+)\.pdf$", filename, re.IGNORECASE)
            report_year_suffix = m.group(1) if m else None
            # Municipality: strip trailing -ma-arXX or _ma_arXX
            muni_raw = re.sub(r"[-_]ma[-_]ar\d+\.pdf$", "", filename, flags=re.IGNORECASE)
            muni = muni_raw.replace("-", " ").replace("_", " ").title().strip()
            rows.append({
                "municipality": muni,
                "report_year_suffix": report_year_suffix,
                "url": full_url,
                "filename": filename,
            })

    if not rows:
        raise ValueError("No MS4 PDF links found on EPA page — page structure may have changed.")

    df = pd.DataFrame(rows).drop_duplicates(subset=["url"])
    print(f"Found {len(df)} report PDFs across {df['municipality'].nunique()} municipalities.")
    return df


# ---------------------------------------------------------------------------
# Phase 2: Download PDFs
# ---------------------------------------------------------------------------

def download_pdfs(index_df, test_mode=False):
    """Download PDFs not already in GCS, then upload. Returns list of local paths."""
    os.makedirs(MS4_DIR, exist_ok=True)

    if test_mode:
        rows = TEST_PDFS
    else:
        rows = index_df[["url", "filename"]].to_dict("records")

    # Get existing GCS files in one listing call.
    print("Listing existing PDFs in GCS ...")
    gs_ls = os.popen(f'gsutil ls "{GS_BUCKET}/**" 2>/dev/null').read()
    existing_in_gcs = set(os.path.basename(p) for p in gs_ls.splitlines() if p.strip())
    print(f"  {len(existing_in_gcs)} files already in GCS.")

    local_paths = []
    new_count = 0
    for row in rows:
        filename = row["filename"]
        local_path = os.path.join(MS4_DIR, filename)
        local_paths.append(local_path)
        if filename not in existing_in_gcs and not os.path.exists(local_path):
            print(f"  Downloading {filename} ...")
            os.system(
                "wget " + shlex.quote(row["url"])
                + f" --no-clobber --timeout=30 --tries=3 -O "
                + shlex.quote(local_path)
            )
            if os.path.exists(local_path):
                os.system(f"gsutil cp {shlex.quote(local_path)} {GS_BUCKET}/{filename}")
                new_count += 1
        elif not os.path.exists(local_path):
            # In GCS but not local — download from GCS
            os.system(f"gsutil cp {GS_BUCKET}/{filename} {shlex.quote(local_path)}")
        else:
            print(f"  Already have {filename}.")

    print(f"Downloaded {new_count} new PDFs.")
    return local_paths


# ---------------------------------------------------------------------------
# Phase 3: Extract structured data with Gemini
# ---------------------------------------------------------------------------

def estimate_cost(page_count):
    """Return estimated USD cost for extracting one PDF of given page count."""
    input_tokens = page_count * TOKENS_PER_PAGE_ESTIMATE
    cost = (input_tokens / 1_000_000 * GEMINI_INPUT_PRICE_PER_M
            + OUTPUT_TOKENS_ESTIMATE / 1_000_000 * GEMINI_OUTPUT_PRICE_PER_M)
    return cost


def get_page_count(pdf_path):
    """Return (page_count, format_issue) where format_issue is None, 'xfa', or 'unreadable'."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages = len(pdf.pages)
            if pages <= 2:
                text = pdf.pages[0].extract_text() or ""
                if "Please wait" in text:
                    return pages, "xfa"
        return pages, None
    except Exception as e:
        print(f"  Warning: pdfplumber could not read {pdf_path}: {e}")
        return None, "unreadable"


def extract_xfa_xml(pdf_path):
    """Return the XFA datasets XML string from an XFA form PDF, or None if not found."""
    doc = fitz.open(pdf_path)
    try:
        catalog_xref = doc.pdf_catalog()
        catalog = doc.xref_object(catalog_xref)
        acroform_m = re.search(r"/AcroForm\s+(\d+)\s+0\s+R", catalog)
        if not acroform_m:
            return None
        acroform_xref = int(acroform_m.group(1))
        acroform = doc.xref_object(acroform_xref)
        xfa_m = re.search(r"\(datasets\)\s+(\d+)\s+0\s+R", acroform)
        if not xfa_m:
            return None
        datasets_xref = int(xfa_m.group(1))
        data = doc.xref_stream(datasets_xref)
        return data.decode("utf-8", errors="replace")
    finally:
        doc.close()


def extract_one(client, pdf_path, source_url):
    """Upload PDF to Gemini and extract structured data. Returns dict."""
    print(f"  Uploading {os.path.basename(pdf_path)} to Gemini ...")
    with open(pdf_path, "rb") as f:
        uploaded = client.files.upload(
            file=f,
            config=types.UploadFileConfig(mime_type="application/pdf"),
        )

    # Poll until file is ready
    for _ in range(15):
        file_info = client.files.get(name=uploaded.name)
        if file_info.state.name == "ACTIVE":
            break
        elif file_info.state.name == "FAILED":
            raise RuntimeError(f"Gemini file upload failed: {uploaded.name}")
        time.sleep(2)
    else:
        raise RuntimeError(f"Gemini file {uploaded.name} did not become ACTIVE in time.")

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[file_info, EXTRACTION_PROMPT],
            config=types.GenerateContentConfig(
                tools=[types.Tool(function_declarations=[EXTRACTION_FUNCTION_DECL])],
                tool_config=types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(
                        mode="ANY",
                        allowed_function_names=["extract_ms4_data"],
                    )
                ),
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
    finally:
        client.files.delete(name=uploaded.name)

    # Parse function call response
    for part in response.candidates[0].content.parts:
        if part.function_call:
            result = dict(part.function_call.args)
            result["source_url"] = source_url
            result["source_page_refs"] = result.get("source_page_refs", {})
            return result

    raise ValueError("Gemini response contained no function call.")


XFA_EXTRACTION_PROMPT = """You are extracting structured data from a Massachusetts MS4 (Municipal Separate Storm Sewer System) annual report.
The data below is the XFA form datasets XML from the PDF — it contains the structured fields the municipality filled in.
Extract all available data according to the function schema. Key guidance:
- MCM sections (Minimum Control Measures) are the six required program elements.
- For TMDL sections: extract each listed waterbody, its target pollutant, and reduction/allocation if stated.
- source_page_refs: leave empty ({}) since this is XML, not a paged document.
- If a field is not present in the XML, return null (omit the field).
- Set extraction_confidence=high if all major MCM fields are present and unambiguous.
- In extraction_notes, flag any ambiguities or missing sections.

XFA FORM DATA (XML):
"""


def extract_one_xfa(client, xml_text, source_url):
    """Extract structured data from XFA datasets XML. Returns dict (no file upload needed)."""
    prompt = XFA_EXTRACTION_PROMPT + xml_text
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[prompt],
        config=types.GenerateContentConfig(
            tools=[types.Tool(function_declarations=[EXTRACTION_FUNCTION_DECL])],
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode="ANY",
                    allowed_function_names=["extract_ms4_data"],
                )
            ),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        ),
    )
    for part in response.candidates[0].content.parts:
        if part.function_call:
            result = dict(part.function_call.args)
            result["source_url"] = source_url
            result["source_page_refs"] = {}
            return result
    raise ValueError("Gemini response contained no function call.")


def extract_all(local_paths, index_df, dry_run=False, test_mode=False, yes=False):
    """Run extraction on all PDFs not yet in the output CSV."""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        secret_file = os.path.join(os.path.dirname(__file__), "SECRET_GOOGLE_API_KEY")
        if os.path.exists(secret_file):
            with open(secret_file) as f:
                api_key = f.read().strip()
    if not api_key and not dry_run:
        raise EnvironmentError(
            "GOOGLE_API_KEY env var not set and get_data/SECRET_GOOGLE_API_KEY not found."
        )

    # Load already-extracted records to skip
    already_done = set()
    if os.path.exists(EXTRACTED_CSV):
        existing = pd.read_csv(EXTRACTED_CSV)
        already_done = set(existing["source_url"].dropna())
        print(f"  {len(already_done)} reports already extracted; skipping.")

    # Build URL lookup from index
    url_by_filename = {}
    if not test_mode and index_df is not None:
        url_by_filename = dict(zip(index_df["filename"], index_df["url"]))
    else:
        url_by_filename = {row["filename"]: row["url"] for row in TEST_PDFS}

    # Pre-check costs
    XFA_TOKENS_ESTIMATE = 4000  # ~13KB XML ≈ 3K tokens input; generous estimate
    XFA_COST = (XFA_TOKENS_ESTIMATE / 1_000_000 * GEMINI_INPUT_PRICE_PER_M
                + OUTPUT_TOKENS_ESTIMATE / 1_000_000 * GEMINI_OUTPUT_PRICE_PER_M)

    total_cost = 0.0
    pdf_queue = []   # list of (lp, source_url, pages, cost, is_xfa)
    for lp in local_paths:
        filename = os.path.basename(lp)
        source_url = url_by_filename.get(filename, lp)
        if source_url in already_done:
            continue
        if not os.path.exists(lp):
            print(f"  Skipping {filename}: file not found locally.")
            continue
        pages, fmt_issue = get_page_count(lp)
        if fmt_issue == "xfa":
            print(f"  {filename}: XFA form — will extract from XML datasets stream.")
            total_cost += XFA_COST
            pdf_queue.append((lp, source_url, 1, XFA_COST, True))
            continue
        if fmt_issue == "unreadable" or pages is None:
            print(f"  Skipping {filename}: unreadable by pdfplumber.")
            continue
        if pages > MAX_PAGE_GUARD:
            print(f"  Skipping {filename}: {pages} pages exceeds guard ({MAX_PAGE_GUARD}). Review manually.")
            continue
        cost = estimate_cost(pages)
        total_cost += cost
        pdf_queue.append((lp, source_url, pages, cost, False))

    print(f"\nExtraction queue: {len(pdf_queue)} PDFs, estimated total cost: ${total_cost:.4f}")

    threshold = COST_THRESHOLD_TEST if test_mode else COST_THRESHOLD_FULL
    if total_cost > threshold and not dry_run and not yes and not test_mode:
        answer = input(f"Estimated cost ${total_cost:.4f} exceeds threshold ${threshold:.2f}. Proceed? [y/N] ")
        if answer.strip().lower() != "y":
            print("Aborted.")
            return
    elif total_cost > threshold and not dry_run:
        print(f"Estimated cost ${total_cost:.4f} (auto-confirmed).")

    if dry_run:
        print("Dry run — no API calls made.")
        for lp, _, pages, cost, is_xfa in pdf_queue:
            kind = "XFA" if is_xfa else f"{pages} pages"
            print(f"  {os.path.basename(lp)}: {kind}, ~${cost:.4f}")
        return

    client = genai.Client(api_key=api_key)
    results = []

    for lp, source_url, pages, cost, is_xfa in pdf_queue:
        kind = "XFA" if is_xfa else f"{pages} pages"
        print(f"\nExtracting {os.path.basename(lp)} ({kind}, ~${cost:.4f}) ...")
        try:
            if is_xfa:
                xml_text = extract_xfa_xml(lp)
                if xml_text is None:
                    raise ValueError("Could not find XFA datasets stream in PDF.")
                result = extract_one_xfa(client, xml_text, source_url)
                result["pdf_pages"] = None
            else:
                result = extract_one(client, lp, source_url)
                result["pdf_pages"] = pages
            result["estimated_cost_usd"] = round(cost, 5)
            results.append(result)
            print(f"  Done. Confidence: {result.get('extraction_confidence', '?')}")
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({
                "source_url": source_url,
                "extraction_confidence": "low",
                "extraction_notes": f"Extraction failed: {e}",
                "pdf_pages": pages if not is_xfa else None,
                "estimated_cost_usd": round(cost, 5),
            })

    if not results:
        return

    # Flatten and append to CSV
    flat_rows = []
    for r in results:
        src_url = r.get("source_url", "")
        filename = src_url.split("/")[-1] if src_url else ""
        gcs_url = f"{GCS_PUBLIC_BASE}/{filename}" if filename else None

        # permit_year: cast float→int; fall back to None (post-process from filename elsewhere)
        raw_py = r.get("permit_year")
        permit_year = int(raw_py) if raw_py is not None else None

        idde = r.get("mcm3_idde") or {}
        flat = {
            "source_url": src_url,
            "gcs_url": gcs_url,
            "municipality": r.get("municipality"),
            "permit_number": r.get("permit_number"),
            "report_year": r.get("report_year"),
            "permit_year": permit_year,
            "report_period_start": r.get("report_period_start"),
            "report_period_end": r.get("report_period_end"),
            "source_page_refs": json.dumps(r.get("source_page_refs", {})),
            "mcm1_activities_count": (r.get("mcm1_public_education") or {}).get("activities_count"),
            "mcm1_notes": (r.get("mcm1_public_education") or {}).get("notes"),
            "mcm2_activities_count": (r.get("mcm2_public_participation") or {}).get("activities_count"),
            "mcm3_outfalls_total": idde.get("outfalls_total"),
            "mcm3_outfalls_screened": idde.get("outfalls_screened"),
            "mcm3_outfalls_not_accessed": idde.get("outfalls_not_accessed"),
            "mcm3_illicit_found": idde.get("illicit_discharges_found"),
            "mcm3_illicit_eliminated": idde.get("illicit_discharges_eliminated"),
            "mcm3_count_type": idde.get("count_type"),
            "mcm3_sampling_conducted": idde.get("sampling_conducted"),
            "mcm4_sites_inspected": (r.get("mcm4_construction") or {}).get("sites_inspected"),
            "mcm4_violations_found": (r.get("mcm4_construction") or {}).get("violations_found"),
            "mcm5_sites_inspected": (r.get("mcm5_post_construction") or {}).get("sites_inspected"),
            "mcm5_bmps_inspected": (r.get("mcm5_post_construction") or {}).get("bmps_inspected"),
            "mcm6_facilities_inspected": (r.get("mcm6_pollution_prevention") or {}).get("facilities_inspected"),
            "mcm6_notes": (r.get("mcm6_pollution_prevention") or {}).get("notes"),
            "system_mapping_pct_complete": r.get("system_mapping_pct_complete"),
            "tmdl_municipality_specific": r.get("tmdl_municipality_specific"),
            "tmdl_waterbodies_json": json.dumps(r.get("tmdl_waterbodies") or []),
            "compliance_issues": r.get("compliance_issues"),
            "extraction_confidence": r.get("extraction_confidence"),
            "extraction_notes": r.get("extraction_notes"),
            "pdf_pages": r.get("pdf_pages"),
            "estimated_cost_usd": r.get("estimated_cost_usd"),
        }
        flat_rows.append(flat)

    new_df = pd.DataFrame(flat_rows)

    # Print results for manual review
    print("\n" + "=" * 60)
    print("EXTRACTION RESULTS")
    print("=" * 60)
    for _, row in new_df.iterrows():
        print(f"\n--- {row.get('municipality', '?')} ---")
        for col in new_df.columns:
            val = row.get(col)
            if val is not None and str(val) not in ("nan", "None", ""):
                print(f"  {col}: {val}")

    if os.path.exists(EXTRACTED_CSV):
        existing = pd.read_csv(EXTRACTED_CSV)
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df

    combined.to_csv(EXTRACTED_CSV, index=False)
    print(f"\nWrote {len(new_df)} new records to {EXTRACTED_CSV} ({len(combined)} total).")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MS4 annual report scrape + extract pipeline")
    parser.add_argument("--test", action="store_true", help="Run on 3 test PDFs only")
    parser.add_argument("--dry-run", action="store_true", help="Estimate costs without API calls")
    parser.add_argument("--skip-download", action="store_true", help="Skip download phase")
    parser.add_argument("--yes", action="store_true", help="Skip cost confirmation prompt")
    args = parser.parse_args()

    # Phase 1: Scrape index
    if args.test:
        index_df = pd.DataFrame(TEST_PDFS)
    else:
        index_df = scrape_report_index()
        index_df.to_csv(INDEX_CSV, index=False)
        print(f"Index written to {INDEX_CSV}.")

    # Phase 2: Download
    if not args.skip_download:
        local_paths = download_pdfs(index_df, test_mode=args.test)
    else:
        if args.test:
            local_paths = [os.path.join(MS4_DIR, r["filename"]) for r in TEST_PDFS]
        else:
            local_paths = [
                os.path.join(MS4_DIR, fn)
                for fn in index_df["filename"]
                if os.path.exists(os.path.join(MS4_DIR, fn))
            ]

    # Phase 3: Extract
    extract_all(local_paths, index_df, dry_run=args.dry_run, test_mode=args.test, yes=args.yes)

    # Timestamp
    if not args.dry_run:
        with open(TIMESTAMP_YML, "w") as f:
            f.write("updated: " + str(datetime.datetime.now()).split(".")[0] + "\n")
