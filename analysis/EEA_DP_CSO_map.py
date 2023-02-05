"""Generate folium-based map visualizations and pystan regression model fits to CSO distributions using 
MA EEA Data Portal CSO data. This follows the same basic structure as NECIR_CSO_map.py,
but is defined separately because some aspects of the data differ.
"""

from typing import Any, Optional, Tuple

import chartjs
from joblib import Memory
import numpy as np
import pandas as pd

from NECIR_CSO_map import COLOR_CYCLE, CSOAnalysis, get_engine, hex2rgb

# Create a joblib cache
memory = Memory('eea_dp_cso_data_cache', verbose=1)

PICK_CSO_YEAR = 2022

def collapse(x: list) -> Any:
    """Pick an arbitrary non-null value from a list.
    """
    for val in x:
        if val is not None and (isinstance(val, float) == False or np.isnan(val) == False):
            return val
    return None

class CSOAnalysisEEADP(CSOAnalysis):
    """Class containing methods and attributes related to CSO EJ analysis using EEA DP CSO data.
    """
        
    output_slug_dataset: str = 'MAEEADP'
    output_slug: str = 'MAEEADP_CSO'
    discharge_vol_col: str = 'DischargeVolume'
    discharge_count_col: str = 'DischargeCount'
    outfall_address_col: str = 'location'
    water_body_col: str = 'waterBody'
    municipality_col: str = 'municipality'
    latitude_col: str = 'latitude'
    longitude_col: str = 'longitude'
    # Path to file with lat long data from the state
    cso_lat_long_data_file: str = '../docs/data/ma_permittee-and-outfall-lists.xlsx'
    
    def __init__(
        self, 
        fact_file: str='../docs/data/facts_EEA_DP_CSO.yml',
        out_path: str='../docs/assets/maps/',
        fig_path: str='../docs/assets/figures/',
        stan_model_code: str='discharge_regression_model.stan',
        geo_towns_path: str='../docs/assets/geo_json/TOWNSSURVEY_POLYM_geojson_simple.json',
        geo_watershed_path: str='../docs/assets/geo_json/watshdp1_geojson_simple.json',
        geo_blockgroups_path: str='../docs/assets/geo_json/cb_2017_25_bg_500k.json',
        cso_data_year: int=2022,
        pick_report_type: str='Verified Data Report'
    ):
        """Initialize parameters for CSOAnalysisEEADP
        """
        super().__init__(
            fact_file,
            out_path,
            fig_path,
            stan_model_code,
            geo_towns_path,
            geo_watershed_path,
            geo_blockgroups_path
        )
        self.cso_data_year = cso_data_year
        # Pick one of two possible report types, 'Public Notification Report' or 'Verified Data Report'
        self.pick_report_type = pick_report_type

    # -------------------------
    # Data loading functions
    # -------------------------

    EEA_DP_CSO_QUERY = """SELECT * FROM MAEEADP_CSO"""

    def load_data_cso(self, pick_year: Optional[int]=None) -> pd.DataFrame:
        """Load EEA Data Portal CSO data, adding latitude and longitude from the NECIR_CSO_2011 data table
        where possible.
        """
        if pick_year is None:
            pick_year = self.cso_data_year
        print(f'Loading EEA Data Portal CSO data for {self.cso_data_year}')
        disk_engine = get_engine()
        data_cso = pd.read_sql_query(self.EEA_DP_CSO_QUERY, disk_engine)
        data_cso['incidentDate'] = pd.to_datetime(data_cso['incidentDate'])
        data_cso_trans = self.transform_data_cso(data_cso)
        
        # Save for use in `extra_plots`
        self.data_cso_raw = data_cso
        
        return data_cso_trans

    def transform_data_cso(self, data_cso: pd.DataFrame, pick_year: int=PICK_CSO_YEAR) -> pd.DataFrame:
        """Transform the loaded MA EEA DP CSO data by aggregating results for `pick_year` over outfalls.
        """
        # Columns to be aggregated over
        # NOTE we aggregate over lat/long because there are several outfalls named '001' that have different lat/longs
        agg_cols = ['reporterClass', 'outfallId', 'latitude', 'longitude']
        # Columns to be aggregated with a sum function
        sum_cols = ['volumnOfEvent']
        # Columns to be aggregated with a collapse function
        collapse_cols = ['Year', 'permiteeClass', 'permiteeName', 'permiteeId', 'municipality', 'location', 'waterBody', 'waterBodyDescription']
        # Columns to be counted
        count_cols = ['incidentId']
        
        # NOTE there are tree possible eventTypes: 'CSO – Treated', 'CSO – UnTreated', 'Partially Treated – Blended', 'Partially Treated – Other'
        # We choose to sum over all of them
        
        aggregators = {col: np.sum for col in sum_cols}
        aggregators.update({col: collapse for col in collapse_cols})
        aggregators.update({col: len for col in count_cols})
        
        print(f'Aggregating CSO data for year {pick_year}')
        df_pick = data_cso[data_cso['Year'].astype(int) == pick_year]
        print(f'N={len(df_pick)} total CSO records loaded from {pick_year}')
        
        # Fill in missing lat/long data from the state file
        sel_missing = df_pick['latitude'].isnull()
        print(f"Missing N={sum(sel_missing)} outfall lat/longs")
        print(f'Loading missing lat/long data from {self.cso_lat_long_data_file}')
        df_lat_long_cso = pd.read_excel(self.cso_lat_long_data_file, 'CSO Outfalls').set_index('Outfall ID')
        missing_lat_long_ids = df_pick[sel_missing]['outfallId']
        missing_lat_long_coords = df_lat_long_cso.reindex(missing_lat_long_ids)[['Lat', 'Long']]
        df_pick.loc[sel_missing, ['latitude', 'longitude']] = missing_lat_long_coords.values
        print(f"Missing N={sum(df_pick['latitude'].isnull())} outfall lat/longs after replacement")
        
        df_agg = df_pick.groupby(agg_cols).agg(aggregators)
        df_per_outfall = df_agg.loc[self.pick_report_type].reset_index()
        
        # Rename some columns
        df_per_outfall.rename(columns={'volumnOfEvent': 'DischargeVolume', 'incidentId': 'DischargeCount'}, inplace=True)
        # Convert to millions of gallons
        df_per_outfall['DischargeVolume'] /= 1e6
        
        return df_per_outfall

    # -------------------------
    # Extra plots of dataset characteristics
    # -------------------------
    
    def plot_reports_per_day_by_event_type(self, outpath: str='../docs/_includes/charts/EEA_DP_CSO_counts_per_day.html'):
        """Bar chart showing how many reports were made each day of different data types.
        """        
        print('Making map of CSO counts per day by event type')
        mychart = chartjs.chart("CSO counts per day by event type", "Bar", 640, 480)
        
        data_types = self.data_cso_raw['eventType'].unique()
        all_days = pd.date_range(start=f'1/1/{self.cso_data_year}', end=f'12/31/{self.cso_data_year}')
        mychart.set_labels(all_days.tolist())
        cso_df_counts = self.data_cso_raw.groupby(['eventType', 'incidentDate']).size()
        
        cumulative_counts = pd.Series(index=all_days, data=np.zeros(len(all_days)))
        for i, event_type in enumerate(data_types):
            counts_per_day = cso_df_counts.loc[event_type].reindex(all_days).fillna(0)
            mychart.add_dataset(counts_per_day.values.tolist(), 
                event_type,
                backgroundColor="'rgba({},0.8)'".format(", ".join([str(x) for x in hex2rgb(COLOR_CYCLE[i])])),
                yAxisID= "'y-axis-0'")
        mychart.set_params(JSinline=0, ylabel='Number of discharges', xlabel='Date',
            scaleBeginAtZero=1)

        mychart.jekyll_write(outpath)
        breakpoint()
    
    def extra_plots(self):
        """Generate all extra data plots for the EEA DP CSO data
        """
        self.plot_reports_per_day_by_event_type()

    
# -------------------------
# Main logic
# -------------------------
    
if __name__ == '__main__':
    csoa = CSOAnalysisEEADP(cso_data_year=PICK_CSO_YEAR)
    csoa.run_analysis()
    csoa.extra_plots()
