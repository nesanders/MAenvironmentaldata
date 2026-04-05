---
title: Massachusetts Daily Precipitation
author: NES
layout: data_listing
ancillary: 1
---

## Data source

This dataset provides a daily time series of precipitation for Massachusetts, expressed as the average precipitation (inches) across all MA GHCN/COOP stations that reported on each day.  Storing daily values allows downstream analysis to apply any aggregation or threshold — annual totals, heavy-rain-day counts (e.g. days ≥ 1 inch), or event-level correlations with CSO discharges — without re-fetching data.

Precipitation observations come from the [NOAA Applied Climate Information System (ACIS)](https://www.rcc-acis.org/), which aggregates data from the GHCN and COOP station networks operated by the National Weather Service and state climate offices.  No API key is required for ACIS access.  Data are fetched year-by-year in daily resolution and averaged across reporting stations.

Note that the number of reporting stations has increased over time as the COOP network expanded; the `n_stations` column reflects the count of stations contributing to each day's average.  All values represent a simple (unweighted) spatial average and are intended as a qualitative index rather than a spatially precise estimate.

This dataset is updated **{{ site.data.ts_update_MA_precipitation.updated | date: "%-d %B %Y" }}**.

The script used to generate this data is [`get_data/get_MA_precipitation.py`](https://github.com/nesanders/MAenvironmentaldata/blob/master/get_data/get_MA_precipitation.py).

## Download archive

* MA daily precipitation [CSV format](MA_precipitation_daily.csv)

## Data table

| Date | Avg Precipitation (inches) | Number of Stations |
| --- | --- | --- |{% for row in site.data.MA_precipitation_daily_sample %}
| {{ row.date }} | {{ row.precip_in_avg | round: 2 }} | {{ row.n_stations }} |{% endfor %}
{: .sortable}

*Table shows a sample of rows from the full dataset.*
