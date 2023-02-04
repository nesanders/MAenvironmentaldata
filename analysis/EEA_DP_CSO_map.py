"""Generate folium-based map visualizations and pystan regression model fits to CSO distributions using 
MA EEA Data Portal CSO data. This follows the same basic structure as NECIR_CSO_map.py
"""

import pandas as pd

from ./NECIR_CSO_map import get_engine, load_data_ej

## Establish file to export facts
FACT_FILE = '../docs/data/facts_EEA_DP_CSO.yml'
# Which year's CSO data to load
PICK_CSO_YEAR = 2022

# -------------------------
# Data loading functions
# -------------------------

def load_data_cso(pick_year: int=PICK_CSO_YEAR) -> pd.DataFrame:
    """Load EEA Data Portal CSO data
    """
    print(f'Loading EEA Data Portal CSO data for {pick_year}')
    disk_engine = get_engine()
    data_cso = pd.read_sql_query('SELECT * FROM MAEEADP_CSO', disk_engine)
    data_cso['2011_Discharges_MGal'] = data_cso['2011_Discharges_MGal'].apply(safe_float)
    data_cso['2011_Discharge_N'] = data_cso['2011_Discharge_N'].apply(safe_float)
    return data_cso

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
    
if __name__ == '__main__':
    main()
