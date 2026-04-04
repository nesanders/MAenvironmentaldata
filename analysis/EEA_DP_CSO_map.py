"""Generate folium-based map visualizations and pystan regression model fits to CSO distributions using 
MA EEA Data Portal CSO data. This follows the same basic structure as NECIR_CSO_map.py,
but is defined separately because some aspects of the data differ.
"""

from datetime import date
from typing import Any, Optional, Tuple

import chartjs
import numpy as np
import pandas as pd

from NECIR_CSO_map import COLOR_CYCLE, CSOAnalysis, get_engine, hex2rgb

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
    geo_blockgroups_path: str='../docs/assets/geo_json/cb_2017_25_bg_500k.json'
    
    def __init__(
        self, 
        cso_data_start: date=PICK_CSO_START,
        cso_data_end: date=PICK_CSO_END,
        pick_report_type: str='Verified Data Report',
        output_slug: str='MAEEADP_CSO',
        **kwargs
    ):
        """Initialize parameters for CSOAnalysisEEADP.
        
        Parameters
        ----------
        cso_data_start, cso_data_end: date
            Start and end date of the dataset to extract and do analysis on, by default PICK_CSO_START to PICK_CSO_END
        pick_report_type: str
            What type of `reporterClass` to extract and do analysis on, by default 'Verified Data Report'
        
        `kwargs` passed to `CSOAnalysis`
        """
        self.output_slug = output_slug
        super().__init__(**kwargs)
        self.cso_data_start = cso_data_start
        self.cso_data_end = cso_data_end
        # Pick one of two possible report types, 'Public Notification Report' or 'Verified Data Report'
        self.pick_report_type = pick_report_type
        self.cso_data_year: int = cso_data_end.year
        
    # -------------------------
    # Data loading functions
    # -------------------------

    EEA_DP_CSO_QUERY = """SELECT * FROM MAEEADP_CSO"""
    
    def load_data_ej(self, ejscreen_year: int=2023):
        """Overwrites the base class load_data_ej function with the updated year, 2023.
        """
        return super().load_data_ej(ejscreen_year)
    
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
        data_cso.rename(columns={
            'volumnOfEvent': self.discharge_vol_col,
            'outfallId': 'cso_id'
        }, inplace=True)
        
        ambig_data = data_cso[data_cso['cso_id'].isnull()]
        print(f'After some manual fixing, these are the remaining reports with ambiguous names: {ambig_data}')
        
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
        agg_cols = ['reporterClass', 'cso_id', 'latitude', 'longitude']
        # Columns to be aggregated with a sum function
        sum_cols = [self.discharge_vol_col]
        # Columns to be aggregated with a collapse function
        collapse_cols = ['Year', 'permiteeClass', 'permiteeName', 'permiteeId', 'municipality', 'location', 'waterBody', 'waterBodyDescription']
        # Columns to be counted
        count_cols = ['incidentId']
        
        # NOTE there are a variety of possible eventTypes: 'CSO – Treated', 'CSO – UnTreated', 'Partially Treated – Blended', 'Partially Treated – Other'
        # We choose to sum over all of them
        
        aggregators = {col: np.sum for col in sum_cols}
        aggregators.update({col: collapse for col in collapse_cols})
        aggregators.update({col: len for col in count_cols})
        
        # Fill in missing lat/long data from the state file
        sel_missing = data_cso['latitude'].isnull()
        print(f"Missing N={sum(sel_missing)} outfall lat/longs")
        print(f'Loading missing lat/long data from {self.cso_lat_long_data_file}')
        df_lat_long_cso = pd.read_excel(self.cso_lat_long_data_file, 'CSO Outfalls').set_index('Outfall ID')
        missing_lat_long_ids = data_cso[sel_missing]['cso_id']
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
    
    def plot_reports_per_month_by_event_type(self, outpath: Optional[str]=None):
        """Bar chart showing how many reports were made each day of different discharge types.
        """
        if outpath is None:
            outpath = f'../docs/_includes/charts/{self.output_slug}_counts_per_month.html'
        
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

    def plot_volume_per_month_by_event_type(self, outpath: Optional[str]=None):
        """Bar chart showing how many reports were made each month of different discharge types.
        """        
        if outpath is None:
            outpath = f'../docs/_includes/charts/{self.output_slug}_volume_per_month.html'
        
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

    def plot_volume_per_operator_by_event_type(self, outpath: Optional[str]=None):
        """Bar chart showing how many reports were made each day of different discharge types.
        """        
        if outpath is None:
            outpath = f'../docs/_includes/charts/{self.output_slug}_volume_per_operator.html'
        
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

    def plot_volume_per_waterbody_by_event_type(self, outpath: Optional[str]=None, top_n: int=20):
        """Bar chart showingvolume of discharge for each waterbody.
        
        Only the top_n by volume are shown for clarity.
        """        
        if outpath is None:
            outpath = f'../docs/_includes/charts/{self.output_slug}_volume_per_waterbody.html'
        
        print('Making chart of discharge volume per waterbody by discharge type')
        mychart = chartjs.chart("Discharge volume per waterbody by discharge type", "Bar", 640, 480)
        
        data_types = self.data_cso_filtered_reports['eventType'].unique()
        cso_df_vol = self.data_cso_filtered_reports.groupby(['eventType', self.water_body_col])[self.discharge_vol_col].sum() / 1e6
        all_waterbodies = self.data_cso_filtered_reports.groupby([self.water_body_col])[self.discharge_vol_col].sum().sort_values(ascending=False).index[:top_n]
        mychart.set_labels(all_waterbodies)
        
        for i, event_type in enumerate(data_types):
            vol_per_waterbody = cso_df_vol.loc[event_type].reindex(all_waterbodies).fillna(0)
            mychart.add_dataset(vol_per_waterbody.values.tolist(), 
                event_type,
                backgroundColor="'rgba({},0.8)'".format(", ".join([str(x) for x in hex2rgb(COLOR_CYCLE[i])])),
                yAxisID= "'y-axis-0'")
        mychart.set_params(JSinline=0, ylabel='Volume of discharges (millions of gallons)', xlabel='Water body',
            scaleBeginAtZero=1)
        mychart.stacked = 'true'

        mychart.jekyll_write(outpath)

    def plot_reports_non_zero_volume(self, outpath: Optional[str]=None):
        """Bar chart showing how many reports of each discharge type have zero volume reported.
        
        NOTE: We use a very simplistic assumption to decide if a volume report is likely modeled rather than
        metered; we simply look to see if the reported volume was rounded to the nearest 1000.
        """        
        if outpath is None:
            outpath = f'../docs/_includes/charts/{self.output_slug}_non_zero_volume.html'
        
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
    
    def plot_annual_precip_and_discharge(self, outpath: Optional[str]=None):
        """Dual-axis bar chart comparing annual CSO discharge volume against annual MA heavy-rain-day count.

        Heavy rain days are defined as days with ≥ 1 inch of precipitation at a given GHCN/COOP station,
        averaged across MA stations (from get_MA_precipitation.py).  This is a more meaningful driver
        of CSO overflows than total monthly precipitation.
        2022 is flagged as a partial CSO year (reporting began June 30).
        """
        if outpath is None:
            outpath = f'../docs/_includes/charts/{self.output_slug}_annual_precip_discharge.html'

        print('Making annual heavy-rain-days vs discharge comparison chart')
        try:
            df_rain = pd.read_csv('../docs/data/MA_precipitation_daily.csv')
        except FileNotFoundError:
            print('  Daily precipitation CSV not found; skipping chart')
            return
        df_rain['date'] = pd.to_datetime(df_rain['date'])
        df_rain['year'] = df_rain['date'].dt.year
        # Compute annual heavy-rain-day counts from daily data
        heavy_rain = (
            df_rain[df_rain['precip_in_avg'] >= 1.0]
            .groupby('year')['date'].count()
            .rename('heavy_rain_days')
        )

        disk_engine = get_engine()
        df_all = pd.read_sql_query(self.EEA_DP_CSO_QUERY, disk_engine)
        df_all['incidentDate'] = pd.to_datetime(df_all['incidentDate'])
        df_all = df_all[df_all['reporterClass'] == self.pick_report_type]
        df_all['cal_year'] = df_all['incidentDate'].dt.year
        year_months = df_all.groupby('cal_year')['incidentDate'].apply(lambda x: x.dt.month.nunique())
        full_years = year_months[year_months >= 6].index
        df_full = df_all[df_all['cal_year'].isin(full_years)]

        years = sorted(df_full['cal_year'].unique())
        year_labels = [f'{y}*' if y == 2022 else str(y) for y in years]

        annual_vol = df_full.groupby('cal_year')['volumnOfEvent'].sum() / 1e6
        mychart = chartjs.chart("Annual CSO discharge vs heavy rain days", "Bar", 700, 420)
        mychart.set_labels(year_labels)
        mychart.add_dataset(
            [float(annual_vol.get(y, 0)) for y in years],
            'CSO discharge (M gallons)',
            backgroundColor="'rgba({},0.8)'".format(", ".join([str(x) for x in hex2rgb(COLOR_CYCLE[0])])),
            yAxisID="'y-axis-0'",
        )
        mychart.add_dataset(
            [float(heavy_rain.get(y, 0)) for y in years],
            'Heavy rain days (\u22651 inch/day)',
            backgroundColor="'rgba({},0.5)'".format(", ".join([str(x) for x in hex2rgb(COLOR_CYCLE[3])])),
            yAxisID="'y-axis-1'",
        )
        mychart.set_params(
            JSinline=0,
            ylabel='Total CSO discharge (millions of gallons)',
            xlabel='Calendar year  (* 2022 reporting began June 30)',
            scaleBeginAtZero=1,
            y2nd='true',
            y2nd_title='Heavy rain days (\u22651 inch/day, MA station average)',
        )
        mychart.jekyll_write(outpath)

    def plot_annual_volume_trends(self, outpath_volume: Optional[str]=None, outpath_count: Optional[str]=None):
        """Bar charts comparing annual CSO discharge volume and count across all years in the dataset.

        Loads the full (unfiltered) CSO dataset so all calendar years are shown, not just the
        window selected for the main EJ analysis.  2022 is flagged as a partial year because
        reporting did not begin until June.
        """
        if outpath_volume is None:
            outpath_volume = f'../docs/_includes/charts/{self.output_slug}_annual_volume.html'
        if outpath_count is None:
            outpath_count = f'../docs/_includes/charts/{self.output_slug}_annual_count.html'

        print('Making annual volume and count trend charts')
        disk_engine = get_engine()
        df_all = pd.read_sql_query(self.EEA_DP_CSO_QUERY, disk_engine)
        df_all['incidentDate'] = pd.to_datetime(df_all['incidentDate'])
        df_all = df_all[df_all['reporterClass'] == self.pick_report_type]
        df_all['cal_year'] = df_all['incidentDate'].dt.year
        # Drop partial current year (< 6 full months of data in a year)
        year_months = df_all.groupby('cal_year')['incidentDate'].apply(lambda x: x.dt.month.nunique())
        full_years = year_months[year_months >= 6].index
        df_full = df_all[df_all['cal_year'].isin(full_years)]

        years = sorted(df_full['cal_year'].unique())
        year_labels = [f'{y}*' if y == 2022 else str(y) for y in years]

        # --- Volume chart ---
        annual_vol = df_full.groupby('cal_year')['volumnOfEvent'].sum() / 1e6
        mychart_v = chartjs.chart("Annual CSO discharge volume", "Bar", 640, 400)
        mychart_v.set_labels(year_labels)
        mychart_v.add_dataset(
            [annual_vol.get(y, 0) for y in years],
            'Total discharge volume (M gallons)',
            backgroundColor="'rgba({},0.8)'".format(", ".join([str(x) for x in hex2rgb(COLOR_CYCLE[0])])),
            yAxisID="'y-axis-0'",
        )
        mychart_v.set_params(
            JSinline=0,
            ylabel='Total discharge volume (millions of gallons)',
            xlabel='Calendar year  (* 2022 reporting began June 30)',
            scaleBeginAtZero=1,
        )
        mychart_v.jekyll_write(outpath_volume)

        # --- Count chart ---
        annual_count = df_full.groupby('cal_year')['incidentId'].count()
        mychart_c = chartjs.chart("Annual CSO discharge count", "Bar", 640, 400)
        mychart_c.set_labels(year_labels)
        mychart_c.add_dataset(
            [int(annual_count.get(y, 0)) for y in years],
            'Number of discharge reports',
            backgroundColor="'rgba({},0.8)'".format(", ".join([str(x) for x in hex2rgb(COLOR_CYCLE[2])])),
            yAxisID="'y-axis-0'",
        )
        mychart_c.set_params(
            JSinline=0,
            ylabel='Number of discharge reports',
            xlabel='Calendar year  (* 2022 reporting began June 30)',
            scaleBeginAtZero=1,
        )
        mychart_c.jekyll_write(outpath_count)

    def plot_annual_volume_by_operator(self, outpath: Optional[str]=None, top_n: int=8):
        """Line chart of annual discharge volume for the top operators over time.

        X-axis: calendar year. Each operator is its own line, showing year-over-year trend.
        """
        if outpath is None:
            outpath = f'../docs/_includes/charts/{self.output_slug}_annual_volume_by_operator.html'

        print('Making annual volume by operator trend chart')
        disk_engine = get_engine()
        df_all = pd.read_sql_query(self.EEA_DP_CSO_QUERY, disk_engine)
        df_all['incidentDate'] = pd.to_datetime(df_all['incidentDate'])
        df_all = df_all[df_all['reporterClass'] == self.pick_report_type]
        df_all['cal_year'] = df_all['incidentDate'].dt.year
        year_months = df_all.groupby('cal_year')['incidentDate'].apply(lambda x: x.dt.month.nunique())
        full_years = sorted(year_months[year_months >= 6].index)
        # Exclude first partial year from operator comparison since it overstates operators
        compare_years = [y for y in full_years if y > 2022]
        df_cmp = df_all[df_all['cal_year'].isin(compare_years)]

        top_operators = (
            df_cmp.groupby('permiteeName')['volumnOfEvent'].sum()
            .sort_values(ascending=False).head(top_n).index.tolist()
        )

        # X-axis: years; each operator is a line
        year_labels = [str(y) for y in compare_years]
        mychart = chartjs.chart("Annual discharge volume by operator", "Line", 640, 480)
        mychart.set_labels(year_labels)

        for i, op in enumerate(top_operators):
            df_op = df_cmp[df_cmp['permiteeName'] == op]
            vol_by_year = df_op.groupby('cal_year')['volumnOfEvent'].sum() / 1e6
            color_rgb = ", ".join([str(x) for x in hex2rgb(COLOR_CYCLE[i % len(COLOR_CYCLE)])])
            mychart.add_dataset(
                [float(vol_by_year.get(yr, 0)) for yr in compare_years],
                op,
                backgroundColor="'rgba({},0.15)'".format(color_rgb),
                borderColor="'rgba({},0.9)'".format(color_rgb),
                pointBackgroundColor="'rgba({},0.9)'".format(color_rgb),
                fill='false',
                pointRadius=4,
                pointHoverRadius=6,
                borderWidth=2,
                yAxisID="'y-axis-0'",
            )
        mychart.set_params(
            JSinline=0,
            ylabel='Discharge volume (millions of gallons)',
            xlabel='Calendar year',
            scaleBeginAtZero=1,
        )
        mychart.jekyll_write(outpath)

    def extra_plots(self):
        """Generate all extra data plots for the EEA DP CSO data
        """
        self.plot_reports_per_month_by_event_type()
        self.plot_volume_per_month_by_event_type()
        self.plot_volume_per_operator_by_event_type()
        self.plot_reports_non_zero_volume()
        self.plot_volume_per_waterbody_by_event_type()
        self.plot_annual_precip_and_discharge()
        self.plot_annual_volume_trends()
        self.plot_annual_volume_by_operator()

    # -------------------------
    # Per-year EJ evolution
    # -------------------------

    def run_annual_ej_evolution(
        self,
        analysis_years: Optional[list]=None,
        chart_outpath: Optional[str]=None,
    ) -> None:
        """Run watershed-level Stan regression per calendar year and plot beta time evolution.

        Reuses the geographic assignment from the saved data_egs_merge and data_cso files
        produced by run_analysis(), so no geopandas pipeline is required here.

        For each year and each EJ variable, fits the power-law discharge model at the watershed
        level and records the posterior median and 90% CI of 2^beta (the growth ratio for a
        doubling of the EJ indicator).  Results are written to the facts YAML and to a Chart.js
        line chart.

        Parameters
        ----------
        analysis_years : list[int], optional
            Calendar years to analyse.  Defaults to full years ≥2023 present in the database.
        chart_outpath : str, optional
            Where to write the Chart.js HTML.  Defaults to
            ``../docs/_includes/charts/{output_slug}_annual_ej_beta_evolution.html``.
        """
        import stan as pystan
        from NECIR_CSO_map import pop_weighted_average

        if chart_outpath is None:
            chart_outpath = f'../docs/_includes/charts/{self.output_slug}_annual_ej_beta_evolution.html'

        # ── Load saved geographic data ──────────────────────────────────────────
        data_egs = pd.read_csv(f'{self.data_path}{self.output_slug}_data_egs_merge.csv.gz')
        data_cso_saved = pd.read_csv(f'{self.data_path}{self.output_slug}_data_cso.csv')

        # cso_id → GEOID from the outfall-level file produced by run_analysis
        cso_geoid = (
            data_cso_saved.dropna(subset=['GEOID'])
            .set_index('cso_id')['GEOID'].astype(str).to_dict()
        )
        # GEOID → Watershed
        data_egs['ID'] = data_egs['ID'].astype(str)
        geoid_ws_map = data_egs.drop_duplicates('ID').set_index('ID')['Watershed'].to_dict()

        # Watershed-level population-weighted EJ (static across years)
        EJ_VARS = [
            ('MINORPCT',   'Fraction non-white'),
            ('LOWINCPCT',  'Fraction low income'),
            ('LINGISOPCT', 'Fraction linguistically isolated'),
        ]
        ws_ej = data_egs.groupby('Watershed').apply(
            lambda x: pop_weighted_average(x, [col for col, _ in EJ_VARS])
        )
        ws_pop = data_egs.groupby('Watershed')['ACSTOTPOP'].sum()

        # ── Load raw CSO data ───────────────────────────────────────────────────
        disk_engine = get_engine()
        df_all = pd.read_sql_query(self.EEA_DP_CSO_QUERY, disk_engine)
        df_all['incidentDate'] = pd.to_datetime(df_all['incidentDate'])
        df_all = df_all[df_all['reporterClass'] == self.pick_report_type]
        df_all['cal_year'] = df_all['incidentDate'].dt.year
        df_all['cso_id'] = df_all['outfallId']
        df_all['GEOID'] = df_all['cso_id'].map(cso_geoid)
        df_all['Watershed'] = df_all['GEOID'].map(geoid_ws_map)

        if analysis_years is None:
            year_months = df_all.groupby('cal_year')['incidentDate'].apply(
                lambda x: x.dt.month.nunique()
            )
            analysis_years = sorted(
                y for y in year_months[year_months >= 6].index if y >= 2023
            )

        print(f'Running per-year EJ beta evolution for years: {analysis_years}')

        # ── Fit Stan models per year ────────────────────────────────────────────
        stan_code = open(self.stan_model_code).read()
        results: dict = {col: {} for col, _ in EJ_VARS}

        for year in analysis_years:
            df_yr = df_all[df_all['cal_year'] == year]
            ws_discharge_yr = df_yr.groupby('Watershed')['volumnOfEvent'].sum() / 1e6

            for col, col_label in EJ_VARS:
                print(f'  Fitting Stan model: {col} / {year}')
                ws_list = [
                    ws for ws in ws_ej.index
                    if ws in ws_discharge_yr.index and ws in ws_pop.index
                ]
                x = ws_ej.loc[ws_list, col].values.astype(float)
                y = ws_discharge_yr.reindex(ws_list).fillna(0).values.astype(float)
                pop = ws_pop.reindex(ws_list).fillna(1).values.astype(float)

                sel_unpop = (pop == 0) | (x == 0) | np.isnan(x) | np.isnan(y)
                x, y, pop = x[~sel_unpop], y[~sel_unpop], pop[~sel_unpop]

                stan_dat = {
                    'J': int(len(x)),
                    'x': x.tolist(),
                    'y': y.tolist(),
                    'p': (pop / np.mean(pop)).tolist(),
                }
                sm = pystan.build(stan_code, data=stan_dat)
                fit = sm.sample(num_samples=1000, num_chains=4)
                fit_par = fit.to_frame()

                ph = 2 ** fit_par['beta']
                results[col][year] = {
                    'median': float(np.median(ph)),
                    'p5':     float(np.percentile(ph, 5)),
                    'p95':    float(np.percentile(ph, 95)),
                }

        # ── Write facts YAML ────────────────────────────────────────────────────
        with open(self.fact_file, 'a') as f:
            for col, _ in EJ_VARS:
                for yr, vals in results[col].items():
                    f.write(
                        f'annual_ej_{col}_{yr}: '
                        f'{vals["median"]:.1f} times '
                        f'(90% CI {vals["p5"]:.1f}\u2013{vals["p95"]:.1f})\n'
                    )

        # ── Write Chart.js line chart ───────────────────────────────────────────
        year_labels = [str(y) for y in analysis_years]
        mychart = chartjs.chart(
            "EJ-CSO correlation over time (watershed level)", "Line", 700, 420
        )
        mychart.set_labels(year_labels)

        for i, (col, col_label) in enumerate(EJ_VARS):
            color_rgb = ", ".join([str(x) for x in hex2rgb(COLOR_CYCLE[i % len(COLOR_CYCLE)])])
            medians = [float(results[col][y]['median']) for y in analysis_years]
            p5s     = [float(results[col][y]['p5'])     for y in analysis_years]
            p95s    = [float(results[col][y]['p95'])    for y in analysis_years]

            # Median line
            mychart.add_dataset(
                medians,
                col_label,
                borderColor="'rgba({},0.9)'".format(color_rgb),
                backgroundColor="'rgba({},0.15)'".format(color_rgb),
                pointBackgroundColor="'rgba({},0.9)'".format(color_rgb),
                fill='false',
                pointRadius=5,
                borderWidth=2,
                yAxisID="'y-axis-0'",
            )
            # 90% CI lower
            mychart.add_dataset(
                p5s,
                f'{col_label} (5th pct)',
                borderColor="'rgba({},0.3)'".format(color_rgb),
                backgroundColor="'rgba({},0.0)'".format(color_rgb),
                fill='false',
                pointRadius=2,
                borderWidth=1,
                borderDash='[4,4]',
                yAxisID="'y-axis-0'",
            )
            # 90% CI upper
            mychart.add_dataset(
                p95s,
                f'{col_label} (95th pct)',
                borderColor="'rgba({},0.3)'".format(color_rgb),
                backgroundColor="'rgba({},0.0)'".format(color_rgb),
                fill='false',
                pointRadius=2,
                borderWidth=1,
                borderDash='[4,4]',
                yAxisID="'y-axis-0'",
            )

        mychart.set_params(
            JSinline=0,
            ylabel='EJ-CSO correlation (2\u02e3 growth ratio, watershed level)',
            xlabel='Calendar year',
            scaleBeginAtZero=1,
        )
        mychart.jekyll_write(chart_outpath)
        print(f'  Wrote EJ beta evolution chart to {chart_outpath}')

    
# -------------------------
# Main logic
# -------------------------
    
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Generate CSO EJ maps and regression models.')
    parser.add_argument(
        '--plots-only', action='store_true',
        help='Skip maps, charts, and Stan regression; regenerate only extra_plots() output. '
             'Useful after adding new plot methods without re-running the full analysis.'
    )
    parser.add_argument(
        '--run', default=None,
        help='Limit execution to a single named run (e.g. "through_2025"). Runs all by default.'
    )
    args = parser.parse_args()

    RUNS = (
        (PICK_CSO_START, PICK_CSO_END, '2022', None),
        (date(2022, 6, 1), date(2023, 6, 30), 'first_year', None),
        (date(2022, 6, 1), date(2023, 6, 30), 'first_year_smooth', 0.5),
        (date(2022, 6, 1), date(2023, 9, 30), 'through_sept_2023', None),
        # Full dataset through end of 2025; used for the 2026 analysis post
        (date(2022, 6, 1), date(2025, 12, 31), 'through_2025', None),
    )

    for start_date, end_date, run_name, cbg_smooth_radius in RUNS:
        if args.run and run_name != args.run:
            continue
        csoa = CSOAnalysisEEADP(
            cso_data_start=start_date,
            cso_data_end=end_date,
            output_slug=f'MAEEADP_{run_name}',
            cbg_smooth_radius=cbg_smooth_radius,
            make_maps=not args.plots_only,
            make_charts=not args.plots_only,
            make_regression=not args.plots_only,
        )
        csoa.run_analysis()
        csoa.extra_plots()
        if run_name == 'through_2025':
            csoa.run_annual_ej_evolution()
