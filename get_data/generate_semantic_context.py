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
        'specific outfall. Key fields: waterBody, municipality, volumeOfEvent / volumnOfEvent (gallons), '
        'latitude/longitude, incidentDate, Year. '
        'IMPORTANT: Data spans June 2022 to present — years available: {cso_year_range}. '
        'Do NOT assume data ends in an earlier year; always query the full range and check MAX(Year) if unsure.'
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
        'agency budgets nationally. Data covers FY2009–FY2023 from four published Green Reports. '
        'Key fields: State (full name, e.g. "Massachusetts"), BudgetDetail (spending category, '
        'e.g. "Environmental Agency Budget", "Amount from Federal Government"), value (dollars), Year. '
        'Values are total dollar amounts, not per-capita. To compute per-capita spending, '
        'join to Census_statepop on State name and divide by the population for that year.'
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
        'US state population estimates by year (2000–2024). Wide format: one row per state, '
        'year columns named as integers (e.g. "2014", "2020"). State column contains full names '
        'matching ECOS_budgets.State (e.g. "Massachusetts"). To join with ECOS_budgets for a '
        'specific year, reference the year column directly: '
        'JOIN Census_statepop p ON p.State = e.State ... e.value / p."2020" AS per_capita. '
        'Sources: Census intercensal 2000–2009, vintage-2019 2010–2019, vintage-2024 2020–2024.'
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
        'Join to MAEEADP_CSO via CSO_303d_Mapping (39 of 56 CSO waterbodies matched). '
        'Key question: Are CSO operators discharging into already-impaired waters?'
    ),
    'CSO_303d_Mapping': (
        'Lookup table: manually verified mapping from CSO waterBody names (ALL CAPS, from MAEEADP_CSO) '
        'to 303(d) waterbody names (mixed case, from EPA_303d_Impairments). '
        '39 of 56 CSO-reporting waterways are matched; unmatched ones are absent from this table. '
        'IMPORTANT: This table has ONLY TWO columns: csoWaterBody and waterbody303d. '
        'It has NO reportingCycle, NO hasTmdl, NO attainment, NO category column. '
        'Those columns live in EPA_303d_Impairments. Always apply reportingCycle filters to '
        'EPA_303d_Impairments, never to CSO_303d_Mapping. '
        'Join: MAEEADP_CSO.waterBody = CSO_303d_Mapping.csoWaterBody, '
        'then CSO_303d_Mapping.waterbody303d = EPA_303d_Impairments.waterbody. '
        'Note: one waterbody name may correspond to multiple assessment units (AUs) in EPA_303d_Impairments '
        'since large rivers are divided into segments.'
    ),
    'MS4_AnnualReports': (
        'AI-extracted structured data from Massachusetts MS4 (Municipal Separate Storm Sewer System) annual compliance reports '
        'submitted to EPA Region 1. One row per report (~1787 rows covering FY2019–FY2026, 316 municipalities). '
        'Fields cover all six Minimum Control Measures (MCMs): MCM1 public education, MCM2 public participation, '
        'MCM3 IDDE (illicit discharge detection), MCM4 construction site inspections, MCM5 post-construction BMP inspections, '
        'MCM6 pollution prevention. '
        'IMPORTANT: permit_year is null for ~35% of reports where report_year is also null (Gemini could not extract it). '
        'permit_year_imputed=1 where permit_year was imputed from report_year. '
        'For trend analysis use report_year (2019–2026) rather than permit_year. '
        'mcm3_count_type distinguishes current_period vs cumulative_since_permit_start counts — '
        'filter to current_period for trend analysis. '
        'extraction_confidence (high/medium/low) reflects AI extraction quality; exclude low for analysis. '
        'municipality_normalized is uppercased with "Town of"/"City of" prefix stripped for joins to MAEEADP_CSO.municipality. '
        'TMDL data is in the separate MS4_TMDL table (joined on source_url).'
    ),
    'MS4_TMDL': (
        'Exploded TMDL (Total Maximum Daily Load) waterbody entries from MS4 annual reports. '
        'One row per (municipality, report_year, waterbody, pollutant) combination. '
        'Joined to MS4_AnnualReports on source_url. '
        'IMPORTANT: only rows where tmdl_municipality_specific=1 in MS4_AnnualReports reflect municipality-specific obligations '
        '(many municipalities list the general permit TMDL table, not their own applicable TMDLs). '
        'Only rows where BOTH reduction_achieved_lbs_per_year AND wasteload_allocation_lbs_per_year are non-null '
        'have quantitative progress data suitable for analysis. '
        'Charles River phosphorus dominates the quantitative data; other watersheds have fewer records.'
    ),
}

# ─── Column-level notes for key tables ────────────────────────────────────────
COLUMN_NOTES = {
    'MS4_AnnualReports': {
        'mcm3_count_type': 'Filter to current_period for trend analysis; cumulative_since_permit_start reporters inflate year-over-year counts.',
        'tmdl_municipality_specific': 'Only True/1 rows reflect municipality-specific TMDL obligations. Many municipalities copy the general permit TMDL list (False/0), which is not analytically meaningful.',
        'municipality': 'Mixed case with "Town of"/"City of" prefix (e.g. "Town of Palmer"). Use municipality_normalized for joins.',
        'municipality_normalized': 'Uppercased, prefix-stripped municipality name for joining to MAEEADP_CSO.municipality.',
        'report_year': 'Null for ~35% of records where Gemini could not extract it from the PDF. Use for trend analysis.',
        'permit_year': 'Null where report_year is also null. permit_year_imputed=1 where derived from report_year.',
        'extraction_confidence': 'high/medium/low. Exclude low records from analysis.',
    },
    'MS4_TMDL': {
        'reduction_achieved_lbs_per_year': 'Null for most rows — only municipalities with quantitative TMDL targets report this.',
        'wasteload_allocation_lbs_per_year': 'Null for most rows. Rows where both this and reduction_achieved_lbs_per_year are non-null are the analytically useful subset.',
        'waterbody': 'Free-text waterbody name as reported by municipality; spelling varies.',
    },
    'MAEEADP_CSO': {
        'waterBody': 'ALL CAPS (e.g. MYSTIC RIVER, CHARLES RIVER). Use UPPER() for filtering.',
        'municipality': 'ALL CAPS town name (e.g. BOSTON, CAMBRIDGE). Use UPPER() for filtering.',
        'volumnOfEvent': 'Discharge volume in gallons. Source data uses this misspelled name; volumeOfEvent is an alias with identical values — prefer volumeOfEvent in new queries.',
        'volumeOfEvent': 'Discharge volume in gallons. Correctly-spelled alias for volumnOfEvent.',
        'Year': 'Calendar year as INTEGER (e.g. 2023).',
        'incidentDate': 'Format: YYYY-MM-DD HH:MM:SS datetime string (e.g. "2022-07-02 00:00:00"). NOT a plain date — use substr(incidentDate, 1, 10) to get the YYYY-MM-DD portion for date comparisons.',
        'eventType': 'Values include: "CSO – UnTreated", "CSO – Treated", "Partially Treated – Blended", "SSO – System Surcharging Under High Flow Conditions", etc. WARNING: there is NO simple "CSO" value — to filter for CSO events use: eventType LIKE \'CSO%\'',
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
        'waterbody303d': 'Mixed case waterbody name from EPA_303d_Impairments. Joins on EPA_303d_Impairments.waterbody. WARNING: this table has no other columns — reportingCycle, hasTmdl, attainment all come from EPA_303d_Impairments, not this table.',
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

- **Precipitation + CSO by month** (IMPORTANT: incidentDate is YYYY-MM-DD HH:MM:SS, date is YYYY-MM-DD — never join them directly with =, always aggregate to month first):
  WITH monthly_cso AS (
    SELECT strftime('%Y-%m', incidentDate) AS month, SUM(volumnOfEvent) AS total_vol
    FROM MAEEADP_CSO WHERE eventType LIKE 'CSO%' GROUP BY 1
  ), monthly_precip AS (
    SELECT strftime('%Y-%m', date) AS month, SUM(precip_in_avg) AS total_precip
    FROM MA_precipitation_daily GROUP BY 1
  )
  SELECT c.month, c.total_vol, p.total_precip FROM monthly_cso c JOIN monthly_precip p ON c.month = p.month ORDER BY 1

- **CSO watershed choropleth** (use this pattern for watershed-level CSO aggregations):
  MAEEADP_CSO JOIN CSO_WatershedMapping ON MAEEADP_CSO.waterBody = CSO_WatershedMapping.waterBody
  → group by CSO_WatershedMapping.watershed → produce choropleth with geography='watersheds'

- **303(d) status or TMDL for a named waterbody** (direct lookup — do NOT use CSO_303d_Mapping):
  SELECT waterbody, hasTmdl, attainment, category FROM EPA_303d_Impairments
  WHERE waterbody LIKE '%Mystic%'
  AND reportingCycle = (SELECT MAX(reportingCycle) FROM EPA_303d_Impairments)
  → reportingCycle and hasTmdl are columns of EPA_303d_Impairments; never put them on CSO_303d_Mapping

- **EJSCREEN environmental justice + CSO by county** (no direct municipality join; use county approximation):
  SELECT e.CNTY_NAME, AVG(e.MINORPCT) AS avg_minority_pct, SUM(c.volumnOfEvent) AS total_cso_gal
  FROM MAEEADP_CSO c
  JOIN EPA_EJSCREEN_2023 e ON e.CNTY_NAME = (
    CASE UPPER(c.municipality)
      WHEN 'BOSTON' THEN 'Suffolk' WHEN 'CAMBRIDGE' THEN 'Middlesex'
      WHEN 'LOWELL' THEN 'Middlesex' WHEN 'WORCESTER' THEN 'Worcester'
      ELSE NULL END)
  WHERE c.eventType LIKE 'CSO%'
  GROUP BY e.CNTY_NAME
  NOTE: EPA_EJSCREEN_2023 has no municipality field — only CNTY_NAME (county). There is NO direct join
  between EJSCREEN and MAEEADP_CSO.municipality. Always warn the user that results are county-level approximations.

- **MS4 stormwater reports + TMDL entries** (one-to-many):
  MS4_AnnualReports JOIN MS4_TMDL ON MS4_AnnualReports.source_url = MS4_TMDL.source_url
  → use WHERE MS4_AnnualReports.tmdl_municipality_specific = 1 to filter to municipality-specific obligations
  → use WHERE MS4_TMDL.reduction_achieved_lbs_per_year IS NOT NULL for quantitative TMDL analysis

- **MS4 + CSO cross-dataset** (municipality join):
  MS4_AnnualReports.municipality_normalized = MAEEADP_CSO.municipality
  Example: SELECT m.municipality_normalized, AVG(m.mcm3_illicit_found) as avg_illicit, SUM(c.volumnOfEvent) as total_cso
  FROM MS4_AnnualReports m JOIN MAEEADP_CSO c ON m.municipality_normalized = c.municipality
  WHERE m.extraction_confidence != 'low' AND c.eventType LIKE 'CSO%' GROUP BY 1

- **CSO discharges to 303(d) impaired waters** (two-step join):
  MAEEADP_CSO JOIN CSO_303d_Mapping ON MAEEADP_CSO.waterBody = CSO_303d_Mapping.csoWaterBody
  JOIN EPA_303d_Impairments ON CSO_303d_Mapping.waterbody303d = EPA_303d_Impairments.waterbody
  WHERE EPA_303d_Impairments.reportingCycle = (SELECT MAX(reportingCycle) FROM EPA_303d_Impairments)
  → shows which CSO discharge events occur in waters listed as "Not Supporting"
  Column ownership: CSO_303d_Mapping has only (csoWaterBody, waterbody303d) — it is a mapping table with no other columns.
  reportingCycle, hasTmdl, attainment, category all belong to EPA_303d_Impairments.
  NOTE: 39 of 56 CSO waterways are mapped; unmatched waterways won't appear in results.
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

- **EJSCREEN joins**: EPA_EJSCREEN_2023 is at the census block group level (ID is a 12-digit FIPS code).
  It has NO municipality or town field. CNTY_NAME is county-level. There is NO direct join to CSO municipality names.
  To connect EJ data to CSO events, the best approach is to aggregate EJSCREEN to county level using CNTY_NAME
  and match to CSO data aggregated by UPPER(municipality) → county via a manual lookup, OR note the limitation
  to the user and provide county-level results instead of town-level.
  Census_ACS.Subdivision contains MA town names in Title Case (e.g. "Lowell") that can be UPPER()-compared to
  MAEEADP_CSO.municipality, but Census_ACS has no EJSCREEN percentile data.

- **Date formats**: InspectionDate, EnforcementDate, FinalDecisionDate are YYYY-MM-DD strings.
  incidentDate (MAEEADP_CSO) is YYYY-MM-DD HH:MM:SS — use substr(incidentDate, 1, 10) or strftime('%Y-%m', incidentDate) to extract date/month.
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

    # Dynamically patch descriptions that depend on DB contents.
    try:
        years = cur.execute(
            'SELECT CAST(Year AS INTEGER) FROM MAEEADP_CSO '
            'WHERE Year IS NOT NULL GROUP BY 1 ORDER BY 1'
        ).fetchall()
        year_list = ', '.join(str(r[0]) for r in years)
        TABLE_DESCRIPTIONS['MAEEADP_CSO'] = TABLE_DESCRIPTIONS['MAEEADP_CSO'].format(
            cso_year_range=year_list
        )
    except Exception:
        TABLE_DESCRIPTIONS['MAEEADP_CSO'] = TABLE_DESCRIPTIONS['MAEEADP_CSO'].format(
            cso_year_range='2022 onward'
        )

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
