"""Extract state environmental agency budget data from ECOS PDF reports and
merge with previously extracted historical data to produce
``../docs/data/ECOS_budget_history.csv``.

This script replaces ``transform_ECOS_data.py`` for updates going forward.
The old tabula-extracted CSVs (2009-2016) are already baked into the existing
CSV; this script only needs to be re-run when ECOS publishes a new report.

Usage (from get_data/):
    conda run -n amend_python python get_ECOS_data.py

Requires:
    pdfplumber (pip install pdfplumber)
"""

import re
import pdfplumber
import pandas as pd
import us

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PDF_REPORTS = [
    {
        'path': 'ECOS/ECOS-Budget-Report-2016-2019.pdf',
        'years': ['2016', '2017', '2018', '2019'],
    },
    {
        'path': 'ECOS/ECOS-Budget-Report-2020-2023.pdf',
        'years': ['2020', '2021', '2022', '2023'],
    },
]

# States / territories that appear as table headers
ALL_TERRITORIES = set(
    [s.name for s in us.STATES]
    + ['Puerto Rico', 'District of Columbia', 'Northern Mariana Islands',
       'CNMI', 'U.S. Virgin Islands', 'Guam']
)

# Canonical field name mapping (after collapsing newlines / extra spaces)
FIELD_MAP = {
    'Environmental Agency Budget': 'Environmental Agency Budget',
    'Environmental Agency\nBudget': 'Environmental Agency Budget',
    'Environmental\nAgency Budget': 'Environmental Agency Budget',
    'Amount from General Fund': 'Amount from General Fund',
    'Amount from General\nFund': 'Amount from General Fund',
    "Amount from Federal Gov't (e.g., U.S. EPA)": 'Amount from Federal Government',
    "Amount from Federal\nGov't (e.g., U.S. EPA)": 'Amount from Federal Government',
    "Amount from Federal Gov't\n(e.g., U.S. EPA)": 'Amount from Federal Government',
    # Unicode right single quotation mark (U+2019) variant from PDFs
    "Amount from Federal Gov\u2019t (e.g., U.S. EPA)": 'Amount from Federal Government',
    "Amount from Federal\nGov\u2019t (e.g., U.S. EPA)": 'Amount from Federal Government',
    "Amount from Federal Gov\u2019t\n(e.g., U.S. EPA)": 'Amount from Federal Government',
    "Amount from Federal Government": 'Amount from Federal Government',
    'Amount from Fees, Other': 'Amount from Fees / Other',
    'Amount from Fees/Other': 'Amount from Fees / Other',
    'Amount from Fees / Other': 'Amount from Fees / Other',
    # 2020-2023 splits fees into two rows – handled specially below
    'Amount from Permit Fees': '_permit_fees',
    'Amount from Other': '_other_fees',
    'Budget Status': 'Status of Budget',
    'Status of Budget': 'Status of Budget',
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_dollar(val):
    """Return a cleaned numeric string, or '' if not parseable."""
    if val is None:
        return ''
    s = str(val).strip()
    # If value has a newline, take only the first line (e.g. Florida "1319841941\nFY 2015-16")
    s = s.split('\n')[0].strip()
    # Remove dollar sign, commas
    s = re.sub(r'[\$,]', '', s)
    # Handle B / M suffixes (e.g. "$3.7B")
    if s.upper().endswith('B'):
        try:
            return str(int(float(s[:-1]) * 1e9))
        except ValueError:
            return ''
    if s.upper().endswith('M'):
        try:
            return str(int(float(s[:-1]) * 1e6))
        except ValueError:
            return ''
    s = s.strip()
    return s


def _normalize_field(raw):
    """Return canonical field name or None if we don't care about this row."""
    if raw is None:
        return None
    # Normalize Unicode curly apostrophe → straight apostrophe before lookup
    cleaned = raw.replace('\u2019', "'").strip()
    return FIELD_MAP.get(cleaned)


def _find_year_value_cols(header_row, years):
    """Return dict mapping year_str -> column_index for data values.

    The ECOS per-state tables have a header row like:
        ['State', '', 'FY 2016', '', '', 'FY 2017', ...]
    The data value for each year sits one column *before* the 'FY XXXX' header,
    i.e. at header_col - 1.  Fall back to header_col if col-1 is None in data.
    """
    year_to_col = {}
    for j, cell in enumerate(header_row):
        if not cell:
            continue
        m = re.search(r'FY\s*(\d{4})', str(cell))
        if m:
            yr = m.group(1)
            if yr in years:
                # value is normally one column to the left of the year header
                year_to_col[yr] = j  # store header col; we'll try j-1 first
    return year_to_col


def _get_value(row, header_col):
    """Return the data value associated with a given header column.

    Column 0 is always the field label — skip it to avoid returning the
    field name as a value when the year header sits at column 1.
    """
    for offset in (-1, 0, 1):
        idx = header_col + offset
        if idx <= 0:  # col 0 is the field label
            continue
        if idx < len(row):
            v = row[idx]
            if v and str(v).strip() not in ('', 'None'):
                return str(v).strip()
    return ''


# ---------------------------------------------------------------------------
# Main extraction
# ---------------------------------------------------------------------------

def extract_pdf(pdf_path, years):
    """Extract per-state budget rows from one ECOS PDF.

    Returns a list of dicts: {State, BudgetDetail, value, Year}
    """
    records = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not table or not table[0]:
                    continue
                state = (table[0][0] or '').strip()
                if state not in ALL_TERRITORIES:
                    continue

                header = table[0]
                year_cols = _find_year_value_cols(header, years)
                if not year_cols:
                    continue  # not a budget data table

                # Accumulate split fees rows
                permit_fees = {yr: '' for yr in years}
                other_fees = {yr: '' for yr in years}

                for row in table[1:]:
                    raw_field = (row[0] or '').strip()
                    canonical = _normalize_field(raw_field)
                    if canonical is None:
                        continue

                    for yr, hcol in year_cols.items():
                        raw_val = _get_value(row, hcol)
                        # Status of Budget is a string, don't clean as dollar
                        if canonical == 'Status of Budget':
                            val = raw_val.replace('\n', ' ').strip()
                        elif canonical == '_permit_fees':
                            permit_fees[yr] = _clean_dollar(raw_val)
                            continue
                        elif canonical == '_other_fees':
                            other_fees[yr] = _clean_dollar(raw_val)
                            continue
                        else:
                            val = _clean_dollar(raw_val)

                        records.append({
                            'State': state,
                            'BudgetDetail': canonical,
                            'value': val,
                            'Year': yr,
                        })

                # Combine split fees into Fees / Other
                for yr in years:
                    pf = permit_fees[yr]
                    of = other_fees[yr]
                    if pf or of:
                        combined = ''
                        try:
                            combined = str(
                                (float(pf) if pf else 0)
                                + (float(of) if of else 0)
                            )
                            # Drop ".0" suffix if integer
                            if combined.endswith('.0'):
                                combined = combined[:-2]
                        except ValueError:
                            combined = pf or of
                        records.append({
                            'State': state,
                            'BudgetDetail': 'Amount from Fees / Other',
                            'value': combined,
                            'Year': yr,
                        })

    return records


def compute_percents(df):
    """Add Percent from X rows derived from Amount from X / Budget rows."""
    rows_to_add = []
    amount_fields = [
        'Amount from Federal Government',
        'Amount from General Fund',
        'Amount from Fees / Other',
    ]
    budget_field = 'Environmental Agency Budget'

    for (state, year), grp in df.groupby(['State', 'Year']):
        budget_rows = grp[grp['BudgetDetail'] == budget_field]
        if budget_rows.empty:
            continue
        try:
            budget_val = float(budget_rows.iloc[0]['value'])
        except (ValueError, TypeError):
            continue
        if budget_val == 0:
            continue

        for af in amount_fields:
            amount_rows = grp[grp['BudgetDetail'] == af]
            if amount_rows.empty:
                continue
            try:
                amount_val = float(amount_rows.iloc[0]['value'])
            except (ValueError, TypeError):
                continue
            pct_field = af.replace('Amount from ', 'Percent from ')
            rows_to_add.append({
                'State': state,
                'BudgetDetail': pct_field,
                'value': str(round(amount_val / budget_val * 100, 2)),
                'Year': year,
            })

    return pd.concat([df, pd.DataFrame(rows_to_add)], ignore_index=True)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    EXISTING_CSV = '../docs/data/ECOS_budget_history.csv'
    OUTPUT_CSV = '../docs/data/ECOS_budget_history.csv'

    # Load existing data (pre-2016 from tabula-extracted + transform_ECOS_data.py)
    existing = pd.read_csv(EXISTING_CSV, dtype=str)
    # The existing "2016" year comes from the 2015-2017 report.
    # The new 2016-2019 PDF has a cleaner 2016 – rename old one to preserve it.
    existing.loc[existing['Year'] == '2016', 'Year'] = '2016_old'
    print(f'Loaded {len(existing)} rows from existing CSV (years: '
          f'{sorted(existing.Year.unique())})')

    # Extract new data from PDFs
    all_new = []
    for report in PDF_REPORTS:
        print(f'\nExtracting {report["path"]} ...')
        rows = extract_pdf(report['path'], report['years'])
        all_new.extend(rows)
        states = sorted(set(r['State'] for r in rows))
        print(f'  Found {len(rows)} records across {len(states)} states')
        print(f'  States: {states}')

    new_df = pd.DataFrame(all_new, dtype=str)
    new_df = compute_percents(new_df)
    print(f'\nTotal new records (with percents): {len(new_df)}')

    # Merge: existing (up to 2015 + 2016_old) + new (2016-2023)
    combined = pd.concat([existing, new_df], ignore_index=True)

    # Drop empty values, remove duplicates (keep last occurrence)
    combined = combined[combined['value'].notna() & (combined['value'] != '')]
    combined = combined.drop_duplicates(
        subset=['State', 'BudgetDetail', 'Year'], keep='last')

    combined = combined.sort_values(['State', 'BudgetDetail', 'Year'])
    combined.to_csv(OUTPUT_CSV, index=False, encoding='ascii', errors='replace')

    import datetime
    with open('../docs/data/ts_update_ECOS_budget_history.yml', 'w') as f:
        f.write('updated: ' + str(datetime.datetime.now()).split('.')[0] + '\n')

    print(f'\nWrote {len(combined)} rows to {OUTPUT_CSV}')
    print(f'Years now in data: {sorted(combined.Year.unique())}')
    print(f'States: {sorted(combined.State.unique())}')
