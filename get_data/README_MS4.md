# MS4 Annual Report Pipeline

This document explains the design of `get_MS4_annual_reports.py`, which scrapes, archives, and extracts structured data from Massachusetts MS4 (Municipal Separate Storm Sewer System) annual report PDFs.

## Background

Under EPA's NPDES Phase II stormwater program, approximately 316 Massachusetts municipalities and institutions submit annual compliance reports documenting their Stormwater Management Programs. These reports cover six Minimum Control Measures (MCMs): public education, public participation, illicit discharge detection and elimination (IDDE), construction site runoff control, post-construction stormwater management, and pollution prevention/good housekeeping.

EPA posts these reports on a single HTML listing page but provides no bulk download API and no structured data. The only access to the underlying numbers is reading each PDF manually.

## Pipeline overview

The script runs in three sequential phases:

```
1. Scrape   →   2. Download + GCS archive   →   3. AI extraction
```

### Phase 1: Index scraping

The [EPA Region 1 MS4 community page](https://www.epa.gov/npdes-permits/regulated-ms4-massachusetts-communities) is scraped with BeautifulSoup. Links matching the pattern `*-ma-ar[YY].pdf` or `*_ma_ar[YY].pdf` are extracted. Municipality name and report year are parsed from the filename. The resulting index is written to `docs/data/MS4_report_index.csv`.

### Phase 2: Download and GCS archive

Each PDF is downloaded from EPA and uploaded to `gs://openamend-data/MS4_annual_reports/`. Processing is incremental: the GCS bucket is listed once at the start, and any file already present is skipped. The public GCS URL (`https://storage.googleapis.com/openamend-data/MS4_annual_reports/<filename>`) is stored alongside the EPA source URL to provide a permanent archive copy independent of EPA's hosting.

### Phase 3: Structured extraction

Extraction is incremental: `docs/data/MS4_extracted.csv` is checked for already-extracted `source_url` values and those reports are skipped.

Before any API call, `pdfplumber` opens each PDF to count pages and detect format issues. This pre-check catches two classes of problematic files at zero API cost:

- **XFA dynamic forms** — detected by a "Please wait..." placeholder on a single-page PDF. Routed to the XFA extraction path (see below).
- **Oversized PDFs** — reports over 80 pages are skipped and logged for manual review, as they likely contain bundled appendices.

The estimated cost for the remaining queue is printed before any API calls are made. In non-test mode with total cost above $20, the user is prompted to confirm.

## PDF format: two distinct extraction paths

MS4 annual reports exist in two distinct PDF formats that require fundamentally different extraction approaches.

### Standard PDFs (majority of reports, especially FY2019–FY2022)

Standard reports are conventional PDFs with selectable text generated from a Word document or similar tool. They are uploaded to the [Gemini File API](https://ai.google.dev/gemini-api/docs/files), which processes both the visual rendering and embedded text of each page.

**Why not extract text with pdfplumber and send that instead?**

Text extraction via pdfplumber would reduce token costs by approximately 4x (from ~2,000 to ~400–650 tokens per page) because the Gemini File API charges for the full rendered representation of each PDF page, not just its text content. However, text extraction is not used because:

1. **Checkboxes are invisible to text extraction.** MS4 annual reports use checkbox fields in their self-assessment sections to indicate which permit requirements were completed. pdfplumber returns only the label text, not whether the box is checked. Gemini reading the visual rendering sees the checkmark. This data is analytically meaningful and silently lost with text extraction.
2. **Scanned pages fail.** Older reports occasionally include scanned attachments. pdfplumber returns empty strings for these; Gemini handles them via OCR.
3. **Multi-column table layout can scramble.** Some MCM summary tables use multi-column layouts that pdfplumber linearizes incorrectly. The visual rendering avoids this.

At current pricing ($0.15/M input tokens, $0.60/M output tokens for Gemini 2.5 Flash), a typical 24-page standard report costs approximately **$0.007**.

### XFA dynamic forms (~25–40% of recent reports, especially FY2024–FY2025)

XFA (XML Forms Architecture) is an Adobe format where the PDF contains both a visual template and a separate XML data stream. When opened in a standard PDF viewer, the XFA rendering engine populates the template with the data — but the visible content is not embedded as static text or images. This produces the "Please wait while the document is being loaded" placeholder seen in PDF readers that do not support XFA rendering.

These PDFs cannot be sent to the Gemini File API for useful extraction — the uploaded file contains only the template and placeholder, not the rendered form fields.

**XFA extraction approach:**

Instead of PDF upload, PyMuPDF (`fitz`) is used to directly read the XFA `datasets` stream from the PDF's internal structure:

```
PDF catalog  →  AcroForm object  →  XFA array  →  (datasets) xref  →  XML stream
```

The `datasets` stream contains all form field values as structured XML, for example:

```xml
<MCM3>
  <Num_Outfalls_Screened>117.00000000</Num_Outfalls_Screened>
  <Num_Illicit_Dis_Identified>5.00000000</Num_Illicit_Dis_Identified>
  <Num_Illicit_Dis_Removed>3.00000000</Num_Illicit_Dis_Removed>
  ...
</MCM3>
```

This XML (~7–13KB per report, 1,600–3,300 tokens) is sent as plain text to Gemini with the same function-calling schema. No file upload is needed.

XFA extraction is **cheaper** (~$0.0009/report vs ~$0.007 for standard PDFs) and typically produces **higher confidence** results because the XML field names are unambiguous machine-readable identifiers, unlike the narrative prose in standard PDFs.

## Gemini extraction: function calling

Both extraction paths use Gemini 2.5 Flash with [forced function calling](https://ai.google.dev/gemini-api/docs/function-calling) (`mode="ANY"`, `automatic_function_calling` disabled). This ensures Gemini always returns a structured JSON object matching the extraction schema rather than free-form text. The schema covers:

- Municipality, permit number, report year, permit year, reporting period
- MCM1–MCM6 activity counts and notes
- MCM3 IDDE: outfalls total/screened/not accessed, illicit discharges found/eliminated, count type (current period vs. cumulative since permit start), sampling conducted
- System mapping completion percentage
- TMDL waterbodies with pollutant, reduction achieved, and wasteload allocation (in both percent and lbs/year)
- Source page references: a dict mapping each schema section to the PDF page numbers where that data was found, enabling manual verification
- Extraction confidence (`high`/`medium`/`low`) and notes

## Cost summary

| Format | Token cost | Approx. cost/report |
|--------|-----------|---------------------|
| Standard PDF (avg 23 pages) | ~46,000 input + 800 output | ~$0.007 |
| XFA form | ~2,500 input + 800 output | ~$0.0009 |

For the full corpus of ~1,779 unextracted reports (estimated ~47% XFA based on local sample):

| Scenario | Est. cost |
|----------|-----------|
| Conservative (25% XFA, 35 pg avg) | ~$15 |
| Central estimate (47% XFA, 23 pg avg) | ~$8 |

The `$20` confirmation threshold in the script covers the conservative case comfortably.

## Running the pipeline

```bash
cd get_data

# Full run (scrape + download + extract all unprocessed PDFs)
conda run -n amend_python python get_MS4_annual_reports.py --yes

# Test run (3 pre-selected PDFs only, no cost confirmation)
conda run -n amend_python python get_MS4_annual_reports.py --test

# Estimate costs without API calls
conda run -n amend_python python get_MS4_annual_reports.py --dry-run

# Re-extract only (skip download phase)
conda run -n amend_python python get_MS4_annual_reports.py --skip-download --yes
```

API key is read from the `GOOGLE_API_KEY` environment variable, or from `get_data/SECRET_GOOGLE_API_KEY` (two-line file: key only). Do not commit this file (covered by `.gitignore` via `*SECRET*`).

## Outputs

| File | Description |
|------|-------------|
| `docs/data/MS4_report_index.csv` | One row per discovered PDF: EPA URL, filename, municipality, report year suffix |
| `docs/data/MS4_extracted.csv` | One row per extracted report: all MCM fields, TMDL waterbodies (JSON), source page refs (JSON), GCS archive URL, confidence, extraction notes |
| `docs/data/ts_update_MS4.yml` | Timestamp of last successful run (used by Jekyll data page) |
| `gs://openamend-data/MS4_annual_reports/` | GCS archive of all downloaded PDFs |
