"""Generate folium-based map visualizations and pystan regression model fits to CSO distributions using 
MA EEA Data Portal CSO data. This follows the same basic structure as NECIR_CSO_map.py,
but is defined separately because some aspects of the data differ.
"""

from typing import Any, Tuple

import numpy as np
import pandas as pd

from NECIR_CSO_map import get_engine, load_data_ej

## Establish file to export facts
FACT_FILE = '../docs/data/facts_EEA_DP_CSO.yml'
# Which year's CSO data to load
PICK_CSO_YEAR = 2022
# Pick one of two possible report types, 'Public Notification Report' or 'Verified Data Report'
PICK_REPORT_TYPE = 'Verified Data Report'
# Path to file with lat long data from the state
CSO_LAT_LONG_DATA_FILE = '../docs/data/ma_permittee-and-outfall-lists.xlsx'

# -------------------------
# Data loading functions
# -------------------------

EEA_DP_CSO_QUERY = """SELECT * FROM MAEEADP_CSO"""

def load_data_cso(pick_year: int=PICK_CSO_YEAR) -> pd.DataFrame:
    """Load EEA Data Portal CSO data, adding latitude and longitude from the NECIR_CSO_2011 data table
    where possible.
    """
    print(f'Loading EEA Data Portal CSO data for {pick_year}')
    disk_engine = get_engine()
    data_cso = pd.read_sql_query(EEA_DP_CSO_QUERY, disk_engine)
    data_cso_trans = transform_data_cso(data_cso)
    breakpoint()
    #data_cso['2011_Discharges_MGal'] = data_cso['2011_Discharges_MGal'].apply(safe_float)
    #data_cso['2011_Discharge_N'] = data_cso['2011_Discharge_N'].apply(safe_float)
    return data_cso

def collapse(x: list) -> Any:
    """Pick an arbitrary non-null value from a list.
    """
    for val in x:
        if val is not None and (isinstance(val, float) == False or np.isnan(val) == False):
            return val
    return None

def transform_data_cso(data_cso: pd.DataFrame, pick_year: int=PICK_CSO_YEAR) -> pd.DataFrame:
    """Transform the loaded MA EEA DP CSO data by aggregating results for `pick_year` over outfalls.
    """
    # Columns to be aggregated over
    agg_cols = ['reporterClass', 'outfallId']
    # Columns to be aggregated with a sum function
    sum_cols = ['volumnOfEvent']
    # Columns to be aggregated with a collapse function
    collapse_cols = ['Year', 'permiteeClass', 'permiteeName', 'permiteeId', 'municipality', 'location', 'latitude', 'longitude', 'waterBody', 'waterBodyDescription']
    
    # NOTE ther are tree possible eventTypes: 'CSO – Treated', 'CSO – UnTreated', 'Partially Treated – Blended', 'Partially Treated – Other'
    # We choose to sum over all of them
    
    aggregators = {col: np.sum for col in sum_cols}
    aggregators.update({col: collapse for col in collapse_cols})
    
    print(f'Aggregating CSO data for year {pick_year}')
    df_pick = data_cso[data_cso['Year'].astype(int) == pick_year]
    print(f'N={len(df_pick)} total CSO records loaded')
    df_agg = df_pick.groupby(agg_cols).agg(aggregators)
    df_per_outfall = df_agg.loc[PICK_REPORT_TYPE].reset_index()
    
    # Fill in missing lat/long data from the state file
    sel_missing = df_per_outfall['latitude'].isnull()
    print(f"Missing N={sum(sel_missing)} outfall lat/longs")
    print(f'Loading missing lat/long data from {CSO_LAT_LONG_DATA_FILE}')
    df_lat_long_cso = pd.read_excel(CSO_LAT_LONG_DATA_FILE, 'CSO Outfalls').set_index('Outfall ID')
    missing_lat_long_ids = df_per_outfall[sel_missing]['outfallId']
    missing_lat_long_coords = df_lat_long_cso.reindex(missing_lat_long_ids)[['Lat', 'Long']]
    df_per_outfall.loc[sel_missing, ['latitude', 'longitude']] = missing_lat_long_coords.values
    print(f"Missing N={sum(df_per_outfall['latitude'].isnull())} outfall lat/longs after replacement")
    breakpoint()
    
    return df_per_outfall

def load_data() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load all data, CSO and EJ.
    """
    print('Loading all data')
    data_cso = load_data_cso()
    data_ejs = load_data_ej()
    return data_cso, data_ejs

# -------------------------
# Main logic
# -------------------------


def main():
    """Load all data and generate all plots and analysis.
    """
    data_cso, data_ejs = load_data()
    
if __name__ == '__main__':
    main()
