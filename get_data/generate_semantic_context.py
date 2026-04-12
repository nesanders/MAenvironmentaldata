"""Generate a semantic context file for the AMEND SQLite database.

Produces docs/assets/db_semantic_context.txt, a plain-text file that is fetched
by the AI Analysis page and injected into the LLM system prompt in place of the
raw CREATE TABLE statements. The format follows the LangChain SQLDatabase pattern:
schema + sample rows + AMEND-specific semantic notes.

Run from the get_data/ directory after assemble_db.py:
    conda run -n amend_python python generate_semantic_context.py [AMEND.db]
"""

import sqlite3
import sys
from datetime import date

# ─── Per-table descriptions ────────────────────────────────────────────────────
TABLE_DESCRIPTIONS = {
    'MAEEADP_CSO': (
        'EEA Data Portal: Combined Sewer Overflow (CSO) and Sanitary Sewer Overflow (SSO) '
        'discharge incidents reported to MassDEP. Each row is one discharge event at a '
        'specific outfall. Key fields: waterBody, municipality, volumnOfEvent (gallons), '
        'latitude/longitude, incidentDate, Year.'
    ),
    'MAEEADP_Enforcement': (
        'EEA Data Portal: MassDEP enforcement actions against regulated entities, 1996–present. '
        'Each row is one action. Key fields: Town, Program, EnforcementType, PenaltyAssessed, '
        'FacilityId, FacilityName, EnforcementDate. Use with MAEEADP_Facility via FacilityId.'
    ),
    'MAEEADP_Facility': (
        'EEA Data Portal: Regulated facilities tracked by MassDEP/EEA. '
        'Key fields: Id (joins to FacilityId in other tables), Town, FacilityType, '
        'FacilityName, Program, Active.'
    ),
    'MAEEADP_Inspection': (
        'EEA Data Portal: MassDEP inspection records for regulated facilities. '
        'Key fields: Town, Program, FacilityId, FacilityName, InspectionType, InspectionDate.'
    ),
    'MAEEADP_Permit': (
        'EEA Data Portal: Environmental permits issued by MassDEP. '
        'Key fields: Town, PermitType, Subtype, Program, Status, FacilityId, FacilityName, '
        'FinalDecisionDate.'
    ),
    'MAEEADP_DrinkingWater': (
        'EEA Data Portal: Annual drinking water quality monitoring results by water system. '
        'Key fields: Year, PWSName (public water system name), ContaminantGroup, Result.'
    ),
    'MADEP_enforcement': (
        'Historical MassDEP enforcement actions extracted from annual reports (through 2017). '
        'Different schema from MAEEADP_Enforcement. Contains fine amounts and topic labels. '
        'Key fields: Year, Date, Fine, municipality. Boolean columns (order_*, law_*) indicate '
        'action type and applicable law.'
    ),
    'MADEP_staff': (
        'MassDEP staffing roster from MA Comptroller/VisibleGovernment data (through 2016). '
        'Each row is one employee-year. Key fields: CalendarYear, EmployeeName, JobTitle, '
        'Earnings, Seniority.'
    ),
    'MADEP_staff_Comptroller': (
        'MassDEP staffing data from MA Comptroller payroll via SODA API (more recent, '
        'updated weekly). Each row is one employee-year. Key fields: year, name_first, '
        'name_last, position_title, pay_total_actual, pay_base_actual.'
    ),
    'MassBudget_summary': (
        'Annual MA environmental agency budget totals (FY2001–present). PREFERRED table for '
        'budget trend queries. Key fields: Year, FiscalYear, DEPAdministration_inf_float '
        '(inflation-adjusted DEP budget), TotalBudget_inf_float, GovernorsBudget.'
    ),
    'MassBudget_infadjusted': (
        'MA environmental budget line items, inflation-adjusted. Wide-format pivot: each '
        'column is a fiscal year (FY01_float through FY24_Sen_float). Use MassBudget_summary '
        'instead for simpler trend queries.'
    ),
    'MassBudget_noinfadjusted': (
        'MA environmental budget line items, nominal dollars (not inflation-adjusted). '
        'Wide-format pivot. Use MassBudget_summary for trend queries.'
    ),
    'EPARegion1_permits': (
        'EPA Region 1 NPDES (water discharge) permit listings for MA facilities. '
        'Key fields: Facility_Name, Permit_Number, Date_of_Issuance, Watershed, State, Stage.'
    ),
    'ECOS_budgets': (
        'ECOS (Environmental Council of the States) budget survey comparing state environmental '
        'agency budgets nationally. Key fields: State, BudgetDetail, value, Year.'
    ),
    'MA_precipitation_daily': (
        'Daily precipitation averages across Massachusetts weather stations (NOAA ACIS). '
        'Key fields: date (YYYY-MM-DD), precip_in_avg (inches), n_stations.'
    ),
    'NECIR_CSO_2011': (
        'New England Center for Investigative Reporting: CSO outfall locations and 2011 '
        'discharge volumes. Key fields: Municipality, DischargesBody, 2011_Discharges_MGal, '
        'Latitude, Longitude.'
    ),
    'Census_ACS': (
        'Census American Community Survey data for MA subdivisions. '
        'Key fields: Subdivision, population_acs52014, per_capita_income_acs52014.'
    ),
    'Census_statepop': (
        'Massachusetts state population by year (2000–2016). Wide format: each column '
        'is a year.'
    ),
    'SSAWages': (
        'Social Security Administration Average Wage Index by year (used to adjust '
        'staffing pay for inflation). Key fields: Year, AWI, Average amount.'
    ),
    'EPA_EJSCREEN_2017': (
        'EPA EJScreen environmental justice screening data for MA census block groups (2017). '
        '150+ columns of demographic and environmental burden percentiles. '
        'Key fields: ID (GEOID), STATE_NAME, MINORPCT, LOWINCPCT, PM25, CANCER, RESP, PNPL. '
        'Percentile columns prefixed P_, indicator columns prefixed B_, text labels prefixed T_.'
    ),
    'EPA_EJSCREEN_2023': (
        'EPA EJScreen environmental justice screening data for MA census block groups (2023). '
        '150+ columns. Similar structure to EPA_EJSCREEN_2017 with additional indicators. '
        'Key fields: ID (GEOID), STATE_NAME, CNTY_NAME, MINORPCT, LOWINCPCT, PM25, CANCER.'
    ),
    'CSO_WatershedMapping': (
        'Lookup table mapping each MAEEADP_CSO.waterBody value to its containing major '
        'MA watershed (matching the GeoJSON polygon names in the watershed choropleth map). '
        'JOIN: MAEEADP_CSO.waterBody = CSO_WatershedMapping.waterBody. '
        'Use this table whenever producing a watershed-level choropleth of CSO data. '
        'watershed values match the short ALL-CAPS names in the GeoJSON '
        '(e.g. MYSTIC, CHARLES, BLACKSTONE, MERRIMACK). watershed is NULL for the catch-all "Other" entry.'
    ),
    'EPA_303d_Impairments': (
        'MassGIS / EPA ATTAINS: Massachusetts 303(d) Integrated List of Waters. '
        'Section 303(d) of the Clean Water Act requires MA to identify waterbodies that fail '
        'to meet water quality standards. MA submits a biennial Integrated List to EPA on '
        'April 1 of even-numbered years; EPA typically approves it within 6-18 months. '
        'Available cycles: 2010, 2012, 2014, 2016, 2018, 2022 (2020 not published by MassGIS; '
        '2024/2026 cycle is in draft as of April 2026). '
        'One row per (assessment unit x designated use x impairment cause x reporting cycle). '
        'Key fields: reportingCycle (year), auId (assessment unit ID), waterbody (name), '
        'watershed (MA watershed name), waterType, category (1/2/3/4A/4B/4C/5 — see below), '
        'designatedUse, attainment, cause (specific pollutant or stressor), hasTmdl. '
        'Category meanings: 1=Fully Supporting, 2=Attaining with concern, 3=Insufficient info, '
        '4A=Impaired+TMDL approved, 4B=Impaired+other plan, 4C=Impaired+alt control, '
        '5=Impaired+TMDL needed (the 303(d) list proper). '
        'A TMDL (Total Maximum Daily Load) is a cleanup plan. hasTmdl=1 means category is 4A/4B/4C. '
        'Join to MAEEADP_CSO via CSO_303d_Mapping (35 of 56 CSO waterbodies matched). '
        'Key question: Are CSO operators discharging into already-impaired waters?'
    ),
    'CSO_303d_Mapping': (
        'Lookup table: manually verified mapping from CSO waterBody names (ALL CAPS, from MAEEADP_CSO) '
        'to 303(d) waterbody names (mixed case, from EPA_303d_Impairments). '
        '35 of 56 CSO-reporting waterways are matched; unmatched ones are absent from this table. '
        'Join: MAEEADP_CSO.waterBody = CSO_303d_Mapping.csoWaterBody, '
        'then CSO_303d_Mapping.waterbody303d = EPA_303d_Impairments.waterbody. '
        'Note: one waterbody name may correspond to multiple assessment units (AUs) in EPA_303d_Impairments '
        'since large rivers are divided into segments.'
    ),
}

# ─── Column-level notes for key tables ────────────────────────────────────────
COLUMN_NOTES = {
    'MAEEADP_CSO': {
        'waterBody': 'ALL CAPS (e.g. MYSTIC RIVER, CHARLES RIVER). Use UPPER() for filtering.',
        'municipality': 'ALL CAPS town name (e.g. BOSTON, CAMBRIDGE). Use UPPER() for filtering.',
        'volumnOfEvent': 'Discharge volume in gallons. WARNING: column name is misspelled "volumn" (not "volume").',
        'Year': 'Stored as FLOAT (e.g. 2020.0). Use CAST(Year AS INTEGER) if needed.',
        'incidentDate': 'Format: YYYY-MM-DD string.',
        'eventType': 'Values: CSO, SSO, UNPERMITTED, etc.',
        'latitude': '~97% of records have coordinates (filled from state outfall registry). Do NOT filter on latitude IS NOT NULL.',
        'longitude': '~97% of records have coordinates. Do NOT filter on longitude IS NOT NULL.',
    },
    'MAEEADP_Enforcement': {
        'Town': 'ALL CAPS town name. Use UPPER() for filtering.',
        'EnforcementDate': 'Format: YYYY-MM-DD string.',
        'PenaltyAssessed': 'Penalty in dollars. Many rows are 0 (non-monetary actions).',
        'Program': 'Regulatory program (e.g. Wetlands, Waterways, Air, Solid Waste).',
        'FacilityId': 'Joins to MAEEADP_Facility.Id.',
    },
    'MAEEADP_Facility': {
        'Town': 'ALL CAPS town name. Use UPPER() for filtering.',
        'Id': 'Primary key. Joins to FacilityId in MAEEADP_Enforcement, MAEEADP_Inspection, MAEEADP_Permit.',
        'Active': 'Boolean: 1 = active facility.',
    },
    'MAEEADP_Inspection': {
        'Town': 'ALL CAPS town name. Use UPPER() for filtering.',
        'InspectionDate': 'Format: YYYY-MM-DD string.',
        'FacilityId': 'Joins to MAEEADP_Facility.Id.',
    },
    'MAEEADP_Permit': {
        'Town': 'ALL CAPS town name. Use UPPER() for filtering.',
        'FinalDecisionDate': 'Format: YYYY-MM-DD string.',
        'FacilityId': 'Joins to MAEEADP_Facility.Id.',
        'Status': 'e.g. Active, Expired, Terminated.',
    },
    'MADEP_enforcement': {
        'municipality': 'Mixed case town name.',
        'Fine': 'Penalty in dollars.',
        'Year': 'Calendar year of enforcement action.',
    },
    'MADEP_staff_Comptroller': {
        'year': 'Calendar year (integer).',
        'pay_total_actual': 'Total annual compensation in dollars.',
    },
    'MassBudget_summary': {
        'DEPAdministration_inf_float': 'DEP budget, inflation-adjusted to current dollars.',
        'TotalBudget_inf_float': 'Total EEA agency budget, inflation-adjusted.',
        'GovernorsBudget': "Governor's recommended budget for DEP.",
        'FiscalYear': 'Fiscal year label (e.g. FY2023).',
    },
    'CSO_WatershedMapping': {
        'waterBody': 'ALL CAPS waterBody value from MAEEADP_CSO. Joins on MAEEADP_CSO.waterBody.',
        'watershed': 'ALL CAPS major watershed name matching GeoJSON polygon (e.g. MYSTIC, CHARLES, BLACKSTONE). NULL for the "Other" catch-all row.',
    },
    'EPA_303d_Impairments': {
        'reportingCycle': 'Integer year of biennial assessment (2010, 2012, 2014, 2016, 2018, 2022). Use MAX(reportingCycle) to get most recent.',
        'auId': 'Assessment unit identifier (e.g. MA51-07). One waterbody may have multiple AUs (river segments).',
        'waterbody': 'Mixed case (e.g. "Charles River"). NOT all-caps. Use CSO_303d_Mapping for joins to MAEEADP_CSO.',
        'watershed': 'MA watershed name (mixed case, e.g. "Blackstone", "Cape Cod"). Different from CSO_WatershedMapping watershed (which is ALL CAPS short names).',
        'waterType': 'Values: RIVER, FRESHWATER LAKE, ESTUARY, COASTAL, WETLAND.',
        'category': 'Assessment category: 1=Fully Supporting, 2=Attaining, 3=Insufficient Info, 4A=TMDL approved, 4B=Other plan, 4C=Alt control, 5=Impaired+TMDL needed.',
        'designatedUse': 'Designated use being assessed: Aquatic Life, Recreation, Fish Consumption, Water Supply, Shellfish Harvesting, etc.',
        'attainment': 'Whether designated use is met: "Not Supporting", "Fully Supporting", "Not Assessed", "Threatened".',
        'cause': 'Specific pollutant or stressor causing impairment (e.g. FECAL COLIFORM, PHOSPHORUS, MERCURY IN FISH TISSUE). NULL if not impaired.',
        'source': 'Probable source of impairment (e.g. Municipal point source, Urban runoff). NULL if not impaired.',
        'tmdlId': 'TMDL document identifier if a cleanup plan exists. NULL means no plan approved.',
        'hasTmdl': 'Derived: 1 if category is 4A, 4B, or 4C (impaired but has some plan); 0 otherwise.',
    },
    'CSO_303d_Mapping': {
        'csoWaterBody': 'ALL CAPS waterBody value from MAEEADP_CSO. Joins on MAEEADP_CSO.waterBody.',
        'waterbody303d': 'Mixed case waterbody name from EPA_303d_Impairments. Joins on EPA_303d_Impairments.waterbody.',
    },
}

# ─── Columns to skip in sample rows (too wide / noisy) ────────────────────────
SKIP_SAMPLE_COLS = {
    'EPA_EJSCREEN_2017': {'Shape_Length', 'Shape_Area', 'OBJECTID'},
    'EPA_EJSCREEN_2023': {'Shape_Length', 'Shape_Area', 'OID_'},
    'MassBudget_infadjusted': set(),
    'MassBudget_noinfadjusted': set(),
}

# Tables to exclude from detailed schema (too wide, rarely queried directly)
SKIP_SCHEMA_TABLES = {'AMEND_metadata'}

# Tables where we show schema but skip sample rows (too wide to be useful)
SKIP_SAMPLE_TABLES = {
    'MassBudget_infadjusted', 'MassBudget_noinfadjusted',
    'EPA_EJSCREEN_2017', 'EPA_EJSCREEN_2023',
}

JOIN_RELATIONSHIPS = """
## Key Join Relationships

- **Town-level joins** (use UPPER() on both sides):
  MAEEADP_CSO.municipality ↔ MAEEADP_Enforcement.Town ↔ MAEEADP_Facility.Town ↔ MAEEADP_Inspection.Town ↔ MAEEADP_Permit.Town

- **Facility-level joins** (integer key):
  MAEEADP_Facility.Id = MAEEADP_Inspection.FacilityId = MAEEADP_Enforcement.FacilityId = MAEEADP_Permit.FacilityId

- **Staffing + budget by year**:
  MADEP_staff_Comptroller.year = MassBudget_summary.Year

- **Precipitation + CSO by date**:
  MA_precipitation_daily.date ↔ MAEEADP_CSO.incidentDate (both YYYY-MM-DD strings; or join on substr(incidentDate,1,4) = CAST(Year AS TEXT))

- **CSO watershed choropleth** (use this pattern for watershed-level CSO aggregations):
  MAEEADP_CSO JOIN CSO_WatershedMapping ON MAEEADP_CSO.waterBody = CSO_WatershedMapping.waterBody
  → group by CSO_WatershedMapping.watershed → produce choropleth with geography='watersheds'

- **CSO discharges to 303(d) impaired waters** (two-step join):
  MAEEADP_CSO JOIN CSO_303d_Mapping ON MAEEADP_CSO.waterBody = CSO_303d_Mapping.csoWaterBody
  JOIN EPA_303d_Impairments ON CSO_303d_Mapping.waterbody303d = EPA_303d_Impairments.waterbody
  WHERE EPA_303d_Impairments.reportingCycle = (SELECT MAX(reportingCycle) FROM EPA_303d_Impairments)
  → shows which CSO discharge events occur in waters listed as "Not Supporting"
  NOTE: 35 of 56 CSO waterways are mapped; unmatched waterways won't appear in results.
"""

GLOBAL_NOTES = """
## Global Data Notes

- **ALL CAPS strings**: Geographic text fields (municipality, Town, waterBody, DischargesBody) are stored in ALL CAPS.
  Always filter with: WHERE UPPER(column) = UPPER('value')  or  WHERE UPPER(column) LIKE UPPER('%value%')

- **Preferred tables for common queries**:
  - CSO discharges → MAEEADP_CSO
  - Enforcement actions (recent) → MAEEADP_Enforcement
  - Enforcement with fines/topics (historical, through 2017) → MADEP_enforcement
  - Staffing (recent) → MADEP_staff_Comptroller
  - Budget trends → MassBudget_summary (not the wide infadjusted/noinfadjusted tables)
  - Environmental justice → EPA_EJSCREEN_2023 (more current than 2017)

- **Date formats**: incidentDate, InspectionDate, InspectionDate, EnforcementDate, FinalDecisionDate are YYYY-MM-DD strings.
  Extract year with: strftime('%Y', date_col) or substr(date_col, 1, 4).
"""


def get_distinct_values(cur, table, col, limit=30):
    """Return top distinct values for a column, ordered by frequency."""
    try:
        rows = cur.execute(
            f'SELECT "{col}", COUNT(*) as n FROM "{table}" '
            f'WHERE "{col}" IS NOT NULL GROUP BY "{col}" ORDER BY n DESC LIMIT {limit}'
        ).fetchall()
        return [str(r[0]) for r in rows if r[0] is not None]
    except Exception:
        return []


def is_all_caps(values):
    """Check if text values appear to be stored in ALL CAPS."""
    str_vals = [v for v in values[:10] if isinstance(v, str) and any(c.isalpha() for c in v)]
    return bool(str_vals) and all(v == v.upper() for v in str_vals)


def format_sample_rows(cur, table, col_names, n=5):
    """Return sample rows formatted as tab-separated text."""
    skip = SKIP_SAMPLE_COLS.get(table, set())
    show_cols = [c for c in col_names if c not in skip and c != 'index'][:20]  # cap width
    try:
        col_list = ', '.join('"' + c + '"' for c in show_cols)
        rows = cur.execute(
            f'SELECT {col_list} FROM "{table}" LIMIT {n}'
        ).fetchall()
    except Exception:
        return None, None
    return show_cols, rows


def generate_semantic_context(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    tables = [
        r[0] for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        if r[0] not in SKIP_SCHEMA_TABLES
    ]

    parts = [
        f'# AMEND Database Semantic Context',
        f'Generated: {date.today()}',
        '',
        GLOBAL_NOTES.strip(),
        '',
        JOIN_RELATIONSHIPS.strip(),
        '',
        '---',
        '',
        '## Table Schemas and Sample Data',
        '',
    ]

    for table in tables:
        row_count = cur.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        col_infos = cur.execute(f'PRAGMA table_info("{table}")').fetchall()
        col_names = [r[1] for r in col_infos]
        col_types = {r[1]: r[2] for r in col_infos}

        desc = TABLE_DESCRIPTIONS.get(table, '')
        parts.append(f'### {table} ({row_count:,} rows)')
        if desc:
            parts.append(desc)
        parts.append('')

        # CREATE TABLE statement from sqlite_master
        create_sql = cur.execute(
            f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}'"
        ).fetchone()
        if create_sql and create_sql[0]:
            parts.append('```sql')
            parts.append(create_sql[0])
            parts.append('```')
            parts.append('')

        # Sample rows
        if table not in SKIP_SAMPLE_TABLES:
            show_cols, rows = format_sample_rows(cur, table, col_names, n=5)
            if show_cols and rows:
                parts.append(f'/* 5 rows from {table}:')
                parts.append('\t'.join(show_cols))
                for row in rows:
                    parts.append('\t'.join(str(v) if v is not None else 'NULL' for v in row))
                parts.append('*/')
                parts.append('')
        else:
            parts.append('*(Wide table — sample rows omitted. See column notes below.)*')
            parts.append('')

        # Column notes
        col_notes = COLUMN_NOTES.get(table, {})

        # Auto-detect interesting categorical columns and ALL CAPS pattern
        auto_notes = []
        for col in col_names:
            if col in ('index', 'Unnamed: 0'):
                continue
            ctype = (col_types.get(col) or '').upper()
            is_text = not any(t in ctype for t in ['INT', 'FLOAT', 'DOUBLE', 'REAL', 'NUMERIC', 'BOOL'])

            if is_text and col not in col_notes:
                try:
                    distinct = cur.execute(
                        f'SELECT COUNT(DISTINCT "{col}") FROM "{table}"'
                    ).fetchone()[0]
                except Exception:
                    continue

                if 0 < distinct <= 80:
                    vals = get_distinct_values(cur, table, col, limit=40)
                    caps = is_all_caps(vals)
                    val_str = ', '.join(vals[:25])
                    if len(vals) > 25:
                        val_str += f', ... ({distinct} total)'
                    note = f'{val_str}'
                    if caps:
                        note = f'ALL CAPS. {note}'
                    auto_notes.append((col, note))

        # Combine explicit notes + auto-detected
        all_notes = list(col_notes.items()) + [(c, n) for c, n in auto_notes if c not in col_notes]

        if all_notes:
            parts.append('**Column notes:**')
            for col, note in all_notes:
                parts.append(f'- `{col}`: {note}')
            parts.append('')

        parts.append('---')
        parts.append('')

    conn.close()
    return '\n'.join(parts)


if __name__ == '__main__':
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'AMEND.db'
    output_path = '../docs/assets/db_semantic_context.txt'

    print(f'Generating semantic context from {db_path}...')
    context = generate_semantic_context(db_path)

    with open(output_path, 'w') as f:
        f.write(context)

    size_kb = len(context.encode()) / 1024
    print(f'Written to {output_path} ({size_kb:.1f} KB)')
