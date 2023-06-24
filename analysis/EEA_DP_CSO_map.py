"""Generate folium-based map visualizations and pystan regression model fits to CSO distributions using 
MA EEA Data Portal CSO data. This follows the same basic structure as NECIR_CSO_map.py,
but is defined separately because some aspects of the data differ.
"""

from datetime import date
from typing import Any, Optional, Tuple

import chartjs
from joblib import Memory
import numpy as np
import pandas as pd

from NECIR_CSO_map import COLOR_CYCLE, CSOAnalysis, get_engine, hex2rgb

# Create a joblib cache
memory = Memory('eea_dp_cso_data_cache', verbose=1)

PICK_CSO_START = date(2022, 6, 1)
PICK_CSO_END = date(2022, 12, 31)

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
        cso_data_start: date=PICK_CSO_START,
        cso_data_end: date=PICK_CSO_END,
        pick_report_type: str='Verified Data Report',
        **kwargs
    ):
        """Initialize parameters for CSOAnalysisEEADP.
        
        Parameters
        ----------
        fact_file: str
            Path of yml file to write calculated results to, by default '../docs/data/facts_EEA_DP_CSO.yml'
        cso_data_start, cso_data_end: date
            Start and end date of the dataset to extract and do analysis on, by default PICK_CSO_START to PICK_CSO_END
        pick_report_type: str
            What type of `reporterClass` to extract and do analysis on, by default 'Verified Data Report'
        
        `kwargs` passed to `CSOAnalysis`
        """
        super().__init__(fact_file=fact_file, **kwargs)
        self.cso_data_start = cso_data_start
        self.cso_data_end = cso_data_end
        # Pick one of two possible report types, 'Public Notification Report' or 'Verified Data Report'
        self.pick_report_type = pick_report_type

    # -------------------------
    # Data loading functions
    # -------------------------

    EEA_DP_CSO_QUERY = """SELECT * FROM MAEEADP_CSO"""

    def load_data_cso(self, pick_start: Optional[date]=None, pick_end: Optional[date]=None) -> pd.DataFrame:
        """Load EEA Data Portal CSO data, adding latitude and longitude from the NECIR_CSO_2011 data table
        where possible.
        """
        if pick_start is None:
            pick_start = self.cso_data_start
        if pick_end is None:
            pick_end = self.cso_data_end
            
        print(f'Loading EEA Data Portal CSO data')
        disk_engine = get_engine()
        data_cso = pd.read_sql_query(self.EEA_DP_CSO_QUERY, disk_engine)
        data_cso['incidentDate'] = pd.to_datetime(data_cso['incidentDate'])
        data_cso.rename(columns={'volumnOfEvent': self.discharge_vol_col}, inplace=True)
        
        print(f'Filtering CSO data for year {self.cso_data_start} - {self.cso_data_end}')
        df_pick = data_cso[(
            data_cso['incidentDate'] >= pd.to_datetime(pick_start)) & 
            (data_cso['incidentDate'] <= pd.to_datetime(pick_end))]
        print(f'N={len(df_pick)} total CSO records loaded from {self.cso_data_start} - {self.cso_data_end}')
        
        print(f'Filtering CSO data for class {self.pick_report_type}')
        df_pick = df_pick[df_pick['reporterClass'] == self.pick_report_type]
        print(f'N={len(df_pick)} total CSO records loaded from {self.pick_report_type}')
        
        # Save for use in `extra_plots`
        self.data_cso_filtered_reports = df_pick
        
        data_cso_trans = self.transform_data_cso(df_pick)
        
        return data_cso_trans

    def transform_data_cso(self, data_cso: pd.DataFrame) -> pd.DataFrame:
        """Transform the loaded MA EEA DP CSO data by aggregating results over outfalls.
        """
        # Columns to be aggregated over
        # NOTE we aggregate over lat/long because there are several outfalls named '001' that have different lat/longs
        agg_cols = ['reporterClass', 'outfallId', 'latitude', 'longitude']
        # Columns to be aggregated with a sum function
        sum_cols = [self.discharge_vol_col]
        # Columns to be aggregated with a collapse function
        collapse_cols = ['Year', 'permiteeClass', 'permiteeName', 'permiteeId', 'municipality', 'location', 'waterBody', 'waterBodyDescription']
        # Columns to be counted
        count_cols = ['incidentId']
        
        # NOTE there are tree possible eventTypes: 'CSO – Treated', 'CSO – UnTreated', 'Partially Treated – Blended', 'Partially Treated – Other'
        # We choose to sum over all of them
        
        aggregators = {col: np.sum for col in sum_cols}
        aggregators.update({col: collapse for col in collapse_cols})
        aggregators.update({col: len for col in count_cols})
        
        # Fill in missing lat/long data from the state file
        sel_missing = data_cso['latitude'].isnull()
        print(f"Missing N={sum(sel_missing)} outfall lat/longs")
        print(f'Loading missing lat/long data from {self.cso_lat_long_data_file}')
        df_lat_long_cso = pd.read_excel(self.cso_lat_long_data_file, 'CSO Outfalls').set_index('Outfall ID')
        missing_lat_long_ids = data_cso[sel_missing]['outfallId']
        missing_lat_long_coords = df_lat_long_cso.reindex(missing_lat_long_ids)[['Lat', 'Long']]
        data_cso.loc[sel_missing, ['latitude', 'longitude']] = missing_lat_long_coords.values
        print(f"Missing N={sum(data_cso['latitude'].isnull())} outfall lat/longs after replacement")
        
        df_agg = data_cso.groupby(agg_cols).agg(aggregators)
        df_per_outfall = df_agg.loc[self.pick_report_type].reset_index()
        
        # Rename some columns
        df_per_outfall.rename(columns={'incidentId': 'DischargeCount'}, inplace=True)
        # Convert to millions of gallons
        df_per_outfall['DischargeVolume'] /= 1e6
        
        return df_per_outfall

    # -------------------------
    # Extra plots of dataset characteristics
    # -------------------------
    
    def plot_reports_per_month_by_event_type(self, outpath: str='../docs/_includes/charts/EEA_DP_CSO_counts_per_month.html'):
        """Bar chart showing how many reports were made each day of different discharge types.
        """        
        print('Making chart of discharge counts per month by discharge type')
        mychart = chartjs.chart("Discharge counts per month by discharge type", "Bar", 640, 480)
        
        data_types = self.data_cso_filtered_reports['eventType'].unique()
        all_months = pd.date_range(start=self.cso_data_start, end=self.cso_data_end, freq='MS')
        mychart.set_labels(all_months.tolist())
        cso_df_counts = self.data_cso_filtered_reports.groupby(['eventType', 'incidentDate']).size()
        
        for i, event_type in enumerate(data_types):
            counts_per_month = cso_df_counts.loc[event_type].resample('MS').sum().reindex(all_months).fillna(0)
            mychart.add_dataset(counts_per_month.values.tolist(), 
                event_type,
                backgroundColor="'rgba({},0.8)'".format(", ".join([str(x) for x in hex2rgb(COLOR_CYCLE[i])])),
                yAxisID= "'y-axis-0'")
        mychart.set_params(JSinline=0, ylabel='Number of discharges', xlabel='Date',
            scaleBeginAtZero=1)
        mychart.stacked = 'true'

        mychart.jekyll_write(outpath)

    def plot_volume_per_month_by_event_type(self, outpath: str='../docs/_includes/charts/EEA_DP_CSO_volume_per_month.html'):
        """Bar chart showing how many reports were made each month of different discharge types.
        """        
        print('Making chart of discharge volume per month by discharge type')
        mychart = chartjs.chart("Discharge volume per month by discharge type", "Bar", 640, 480)
        
        data_types = self.data_cso_filtered_reports['eventType'].unique()
        all_months = pd.date_range(start=self.cso_data_start, end=self.cso_data_end, freq='MS')
        mychart.set_labels(all_months.tolist())
        cso_df_vol = self.data_cso_filtered_reports.groupby(['eventType', 'incidentDate'])[self.discharge_vol_col].sum() / 1e6
        
        for i, event_type in enumerate(data_types):
            counts_per_month = cso_df_vol.loc[event_type].resample('MS').sum().reindex(all_months).fillna(0)
            mychart.add_dataset(counts_per_month.values.tolist(), 
                event_type,
                backgroundColor="'rgba({},0.8)'".format(", ".join([str(x) for x in hex2rgb(COLOR_CYCLE[i])])),
                yAxisID= "'y-axis-0'")
        mychart.set_params(JSinline=0, ylabel='Volume of discharges (millions of gallons)', xlabel='Date',
            scaleBeginAtZero=1)
        mychart.stacked = 'true'

        mychart.jekyll_write(outpath)

    def plot_volume_per_operator_by_event_type(self, outpath: str='../docs/_includes/charts/EEA_DP_CSO_volume_per_operator.html'):
        """Bar chart showing how many reports were made each day of different discharge types.
        """        
        print('Making chart of discharge volume per operator by discharge type')
        mychart = chartjs.chart("Discharge volume per operator by discharge type", "Bar", 640, 480)
        
        data_types = self.data_cso_filtered_reports['eventType'].unique()
        all_operators = sorted(self.data_cso_filtered_reports['permiteeName'].unique())
        mychart.set_labels(all_operators)
        cso_df_vol = self.data_cso_filtered_reports.groupby(['eventType', 'permiteeName'])[self.discharge_vol_col].sum() / 1e6
        
        for i, event_type in enumerate(data_types):
            counts_per_operator = cso_df_vol.loc[event_type].reindex(all_operators).fillna(0)
            mychart.add_dataset(counts_per_operator.values.tolist(), 
                event_type,
                backgroundColor="'rgba({},0.8)'".format(", ".join([str(x) for x in hex2rgb(COLOR_CYCLE[i])])),
                yAxisID= "'y-axis-0'")
        mychart.set_params(JSinline=0, ylabel='Volume of discharges (millions of gallons)', xlabel='Sewer operator (permittee)',
            scaleBeginAtZero=1)
        mychart.stacked = 'true'

        mychart.jekyll_write(outpath)

    def plot_reports_non_zero_volume(self, outpath: str='../docs/_includes/charts/EEA_DP_CSO_non_zero_volume.html'):
        """Bar chart showing how many reports of each discharge type have zero volume reported.
        
        NOTE: We use a very simplistic assumption to decide if a volume report is likely modeled rather than
        metered; we simply look to see if the reported volume was rounded to the nearest 1000.
        """        
        print('Making chart of discharges with no volume reported by discharge type')
        mychart = chartjs.chart("Discharges with no volume reported by discharge type", "Bar", 640, 480)
        
        data_types = self.data_cso_filtered_reports['eventType'].unique()
        mychart.set_labels(data_types)
        
        def vol_gtr_0(x: float) -> float:
            return 100 * np.mean(x > 0)
        
        def likely_modeled(x: float) -> bool:
            return 100 * np.mean((x % 1000) == 0)
        
        nonzero_rates = self.data_cso_filtered_reports.groupby(['eventType'])[self.discharge_vol_col].apply(vol_gtr_0)
        likely_modeled_rates = self.data_cso_filtered_reports.groupby(['eventType'])[self.discharge_vol_col].apply(likely_modeled)
        
        mychart.add_dataset(nonzero_rates.reindex(data_types).tolist(), 
            '...with nonzero volume reported',
            backgroundColor="'rgba({},0.5)'".format(", ".join([str(x) for x in hex2rgb(COLOR_CYCLE[0])])),
        )
        mychart.add_dataset(likely_modeled_rates.reindex(data_types).tolist(), 
            '...with likely-modeled volume reported',
            backgroundColor="'rgba({},0.5)'".format(", ".join([str(x) for x in hex2rgb(COLOR_CYCLE[1])])),
        )
        mychart.set_params(JSinline=0, ylabel='% of discharges...', 
            xlabel='Discharge type', scaleBeginAtZero=1)

        mychart.jekyll_write(outpath)
    
    def extra_plots(self):
        """Generate all extra data plots for the EEA DP CSO data
        """
        self.plot_reports_per_month_by_event_type()
        self.plot_volume_per_month_by_event_type()
        self.plot_volume_per_operator_by_event_type()
        self.plot_reports_non_zero_volume()

    
# -------------------------
# Main logic
# -------------------------
    
if __name__ == '__main__':
    for start_date, end_date, run_name in (
        (PICK_CSO_START, PICK_CSO_END, '2022'),
        (date(2022, 6, 1), date(2023, 6, 30), 'first_year')
        ):
        # NOTE for fast debugging of the `extra_plot`, try using these parameters:
        # > make_maps=False, make_charts=False, make_regression=False
        csoa = CSOAnalysisEEADP(cso_data_start=start_date, cso_data_end=end_date, output_slug_dataset=f'MAEEADP_{run_name}')
        csoa.run_analysis()
        csoa.extra_plots()
