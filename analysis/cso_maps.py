"""Plotly-based choropleth map generation for CSO discharge and EJ analysis.

Replaces the folium-based map code that broke with folium 0.20.

Each public function produces a single self-contained HTML file.  Maps use
CartoDB positron tiles (no API key, no Referer policy) and Plotly's native
dropdown buttons to toggle between watershed, municipality, and census block
group choropleth layers.  CSO outfall points are overlaid on every map with
hover tooltips.

Public API
----------
make_discharge_map(...)
    Choropleth of total CSO discharge volume with CSO point layer.

make_ej_map(...)
    Choropleth of one EJ indicator (MINORPCT / LOWINCPCT / LINGISOPCT)
    with CSO point layer.

make_inspection_map(...)
    Simple single-layer choropleth of inspection counts by municipality.

make_enforcement_map(...)
    Choropleth of DEP enforcement counts by municipality with town-center
    marker overlay showing top enforcement actions in hover tooltip.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go

# ── colour palette ────────────────────────────────────────────────────────────
# Plotly sequential scales used per layer
_SCALE_WATERSHED   = 'PuBu'
_SCALE_MUNI        = 'PuRd'
_SCALE_CBG         = 'BuGn'
_CSO_POINT_COLOUR  = '#2ca02c'   # green, same as original

# ── map defaults ──────────────────────────────────────────────────────────────
_MAP_CENTER = {'lat': 42.2, 'lon': -71.7}
_MAP_ZOOM   = 7.2
_MAP_STYLE  = 'carto-positron'
_MAP_HEIGHT = 400
_MAP_WIDTH  = 700


def _load_geojson(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def _choropleth_trace(
    geojson: dict,
    featureidkey: str,
    ids: list,
    values: list,
    name: str,
    colorscale: str,
    label: str,
    visible: bool,
) -> go.Choroplethmapbox:
    return go.Choroplethmapbox(
        geojson=geojson,
        featureidkey=featureidkey,
        locations=ids,
        z=values,
        colorscale=colorscale,
        marker_opacity=0.65,
        marker_line_width=0.5,
        name=name,
        showscale=True,
        colorbar=dict(
            orientation='h',
            x=0.5, xanchor='center',
            y=0.01, yanchor='bottom',
            thickness=12,
            len=0.55,
            tickfont=dict(size=11),
            title=dict(text=label, side='top', font=dict(size=12)),
        ),
        visible=visible,
        hovertemplate='<b>%{location}</b><br>' + label + ': %{z:.3f}<extra></extra>',
    )


def _cso_point_trace(
    data_cso: pd.DataFrame,
    lat_col: str,
    lon_col: str,
    vol_col: str,
    count_col: str,
    loc_col: str,
    waterbody_col: str,
    muni_col: str,
    operator_col: str,
    period_label: str,
) -> go.Scattermapbox:
    """Scatter trace of CSO outfall locations with hover tooltips."""
    # Aggregate by outfall (cso_id) to get one point per unique outfall
    agg = (
        data_cso.groupby([lat_col, lon_col, loc_col, waterbody_col, muni_col, operator_col])
        .agg({vol_col: 'sum', count_col: 'sum'})
        .reset_index()
    )
    agg[vol_col] = agg[vol_col] / 1e6  # gallons → millions of gallons

    hover = (
        '<b>CSO outfall: ' + agg[loc_col].astype(str) + '</b><br>'
        + 'Operator: ' + agg[operator_col].astype(str) + '<br>'
        + 'Water body: ' + agg[waterbody_col].astype(str) + '<br>'
        + 'Municipality: ' + agg[muni_col].astype(str) + '<br>'
        + 'Total discharge ' + period_label + ': ' + agg[vol_col].round(2).astype(str) + ' M gal<br>'
        + 'Number of events ' + period_label + ': ' + agg[count_col].astype(str)
        + '<extra></extra>'
    )
    return go.Scattermapbox(
        lat=agg[lat_col],
        lon=agg[lon_col],
        mode='markers',
        marker=dict(size=6, color=_CSO_POINT_COLOUR, opacity=0.8),
        hovertemplate=hover,
        name='CSO outfalls',
        visible=True,
    )


def _layer_buttons(n_choropleth_layers: int, layer_names: list[str]) -> list[dict]:
    """Return updatemenus button dicts that toggle choropleth layers.

    The last trace (index n_choropleth_layers) is always the CSO point scatter
    and stays visible on every button.
    """
    buttons = []
    for i, label in enumerate(layer_names):
        visibility = [j == i for j in range(n_choropleth_layers)] + [True]
        buttons.append(dict(
            label=label,
            method='update',
            args=[{'visible': visibility}],
        ))
    return buttons


def _save_map(fig: go.Figure, outpath: str) -> None:
    Path(outpath).parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(
        outpath,
        include_plotlyjs='cdn',
        full_html=True,
        config={'scrollZoom': True},
    )


def _town_centroids(geojson: dict) -> dict:
    """Return {TOWN_NAME: (lat, lon)} centroid for each feature in a towns GeoJSON."""
    from shapely.geometry import shape
    centroids = {}
    for feat in geojson['features']:
        name = feat['properties'].get('TOWN') or feat['properties'].get('NAME', '')
        geom = shape(feat['geometry'])
        c = geom.centroid
        centroids[name] = (c.y, c.x)   # lat, lon
    return centroids


# ── public functions ──────────────────────────────────────────────────────────

def make_discharge_map(
    data_cso: pd.DataFrame,
    data_ins_g_bg: pd.DataFrame,
    data_ins_g_muni: pd.DataFrame,
    data_ins_g_ws: pd.DataFrame,
    geo_blockgroups_path: str,
    geo_towns_path: str,
    geo_watershed_path: str,
    outpath: str,
    vol_col: str = 'DischargeVolume',
    count_col: str = 'DischargeCount',
    lat_col: str = 'latitude',
    lon_col: str = 'longitude',
    loc_col: str = 'location',
    waterbody_col: str = 'waterBody',
    muni_col: str = 'municipality',
    operator_col: str = 'permiteeName',
    period_label: str = '',
) -> None:
    """Write a discharge-volume choropleth map with watershed/municipality/CBG
    layer toggle and CSO outfall point overlay.
    """
    gj_bg   = _load_geojson(geo_blockgroups_path)
    gj_town = _load_geojson(geo_towns_path)
    gj_ws   = _load_geojson(geo_watershed_path)

    vol_bg   = data_ins_g_bg[vol_col]   / 1e6
    vol_muni = data_ins_g_muni[vol_col] / 1e6
    vol_ws   = data_ins_g_ws[vol_col]   / 1e6

    label = f'Total discharge {period_label} (M gal)'

    traces = [
        _choropleth_trace(gj_ws,   'properties.NAME', vol_ws.index.tolist(),   vol_ws.tolist(),   'Watersheds',          _SCALE_WATERSHED, label, visible=True),
        _choropleth_trace(gj_town, 'properties.TOWN', vol_muni.index.tolist(), vol_muni.tolist(), 'Municipalities',      _SCALE_MUNI,      label, visible=False),
        _choropleth_trace(gj_bg,   'properties.GEOID', [str(x) for x in vol_bg.index.tolist()],  vol_bg.tolist(),   'Census Block Groups', _SCALE_CBG,       label, visible=False),
        _cso_point_trace(data_cso, lat_col, lon_col, vol_col, count_col, loc_col, waterbody_col, muni_col, operator_col, period_label),
    ]

    fig = go.Figure(traces)
    fig.update_layout(
        mapbox=dict(style=_MAP_STYLE, center=_MAP_CENTER, zoom=_MAP_ZOOM),
        margin={'r': 0, 't': 0, 'l': 0, 'b': 0},
        height=_MAP_HEIGHT,
        width=_MAP_WIDTH,
        updatemenus=[dict(
            type='buttons',
            direction='right',
            x=0.01, y=0.99, xanchor='left', yanchor='top',
            bgcolor='rgba(255,255,255,0.85)',
            buttons=_layer_buttons(3, ['Watersheds', 'Municipalities', 'Census Block Groups']),
            showactive=True,
        )],
        showlegend=False,
    )
    _save_map(fig, outpath)


def make_ej_map(
    data_cso: pd.DataFrame,
    data_egs_merge: pd.DataFrame,
    df_town_level: pd.DataFrame,
    df_watershed_level: pd.DataFrame,
    geo_blockgroups_path: str,
    geo_towns_path: str,
    geo_watershed_path: str,
    outpath: str,
    ej_col: str = 'MINORPCT',
    ej_label: str = '',
    vol_col: str = 'DischargeVolume',
    count_col: str = 'DischargeCount',
    lat_col: str = 'latitude',
    lon_col: str = 'longitude',
    loc_col: str = 'location',
    waterbody_col: str = 'waterBody',
    muni_col: str = 'municipality',
    operator_col: str = 'permiteeName',
    period_label: str = '',
) -> None:
    """Write an EJ-indicator choropleth map with watershed/municipality/CBG
    layer toggle and CSO outfall point overlay.
    """
    gj_bg   = _load_geojson(geo_blockgroups_path)
    gj_town = _load_geojson(geo_towns_path)
    gj_ws   = _load_geojson(geo_watershed_path)

    ws_vals   = df_watershed_level[ej_col]
    town_vals = df_town_level[ej_col]
    bg_vals   = data_egs_merge[ej_col]

    label = ej_label or ej_col

    traces = [
        _choropleth_trace(gj_ws,   'properties.NAME',  ws_vals.index.tolist(),   ws_vals.tolist(),   'Watersheds',          _SCALE_WATERSHED, label, visible=True),
        _choropleth_trace(gj_town, 'properties.TOWN',  town_vals.index.tolist(), town_vals.tolist(), 'Municipalities',      _SCALE_MUNI,      label, visible=False),
        _choropleth_trace(gj_bg,   'properties.GEOID', [str(x) for x in bg_vals.index.tolist()],   bg_vals.tolist(),   'Census Block Groups', _SCALE_CBG,       label, visible=False),
        _cso_point_trace(data_cso, lat_col, lon_col, vol_col, count_col, loc_col, waterbody_col, muni_col, operator_col, period_label),
    ]

    fig = go.Figure(traces)
    fig.update_layout(
        mapbox=dict(style=_MAP_STYLE, center=_MAP_CENTER, zoom=_MAP_ZOOM),
        margin={'r': 0, 't': 0, 'l': 0, 'b': 0},
        height=_MAP_HEIGHT,
        width=_MAP_WIDTH,
        updatemenus=[dict(
            type='buttons',
            direction='right',
            x=0.01, y=0.99, xanchor='left', yanchor='top',
            bgcolor='rgba(255,255,255,0.85)',
            buttons=_layer_buttons(3, ['Watersheds', 'Municipalities', 'Census Block Groups']),
            showactive=True,
        )],
        showlegend=False,
    )
    _save_map(fig, outpath)


def make_inspection_map(
    data_ins_g_t: pd.Series,
    geo_towns_path: str,
    outpath: str,
    label: str = 'Total # of inspections recorded',
) -> None:
    """Write a single-layer choropleth of inspection counts by municipality."""
    gj_town = _load_geojson(geo_towns_path)
    fig = go.Figure(go.Choroplethmapbox(
        geojson=gj_town,
        featureidkey='properties.TOWN',
        locations=data_ins_g_t.index.tolist(),
        z=data_ins_g_t.values.tolist(),
        colorscale=_SCALE_MUNI,
        marker_opacity=0.65,
        marker_line_width=0.5,
        showscale=True,
        colorbar=dict(
            orientation='h', x=0.5, xanchor='center',
            y=0.01, yanchor='bottom', thickness=12, len=0.55,
            tickfont=dict(size=11),
            title=dict(text=label, side='top', font=dict(size=12)),
        ),
        hovertemplate='<b>%{location}</b><br>' + label + ': %{z:.0f}<extra></extra>',
    ))
    fig.update_layout(
        mapbox=dict(style=_MAP_STYLE, center=_MAP_CENTER, zoom=_MAP_ZOOM),
        margin={'r': 0, 't': 0, 'l': 0, 'b': 0},
        height=_MAP_HEIGHT, width=_MAP_WIDTH, showlegend=False,
    )
    _save_map(fig, outpath)


def make_enforcement_map(
    town_count: pd.Series,
    enforcement_df: pd.DataFrame,
    geo_towns_path: str,
    outpath: str,
    town_col: str = 'municipality',
    date_col: str = 'Date',
    fine_col: str = 'Fine',
    text_col: str = 'Text',
) -> None:
    """Write a choropleth of DEP enforcement counts by municipality.

    Overlays a scatter marker at each town centroid; hovering shows the top 3
    enforcement actions (by penalty) for that town.
    """
    gj_town = _load_geojson(geo_towns_path)
    centroids = _town_centroids(gj_town)

    label = 'Total # of MA DEP enforcements reported'
    choropleth = go.Choroplethmapbox(
        geojson=gj_town,
        featureidkey='properties.TOWN',
        locations=town_count.index.tolist(),
        z=town_count.values.tolist(),
        colorscale=_SCALE_MUNI,
        marker_opacity=0.65,
        marker_line_width=0.5,
        showscale=True,
        colorbar=dict(
            orientation='h', x=0.5, xanchor='center',
            y=0.01, yanchor='bottom', thickness=12, len=0.55,
            tickfont=dict(size=11),
            title=dict(text=label, side='top', font=dict(size=12)),
        ),
        hovertemplate='<b>%{location}</b><br>' + label + ': %{z:.0f}<extra></extra>',
        name='',
    )

    # Per-town marker overlay with top-3 enforcement hover
    towns_with_data = [t for t in town_count.index if t in centroids and town_count[t] > 0]
    lats, lons, hovers = [], [], []
    for town in towns_with_data:
        lat, lon = centroids[town]
        lats.append(lat)
        lons.append(lon)
        top3 = (
            enforcement_df[
                enforcement_df[town_col].apply(
                    lambda x: town in x if isinstance(x, list) else False
                )
            ]
            .sort_values(fine_col, ascending=False)
            [[date_col, fine_col, text_col]]
            .head(3)
        )
        lines = [
            f'<b>{town}</b><br>Total enforcements: {int(town_count[town])}'
            '<br>Top actions (by penalty):'
        ]
        for _, row in top3.iterrows():
            fine_str = f'${row[fine_col]:,.0f}' if pd.notna(row[fine_col]) else '$0'
            lines.append(f'{row[date_col]}, {fine_str}: {str(row[text_col])[:80]}')
        hovers.append('<br>'.join(lines) + '<extra></extra>')

    scatter = go.Scattermapbox(
        lat=lats, lon=lons,
        mode='markers',
        marker=dict(size=6, color='#2ca02c', opacity=0.8),
        hovertemplate=hovers,
        name='Towns with enforcements',
        visible=True,
    )

    fig = go.Figure([choropleth, scatter])
    fig.update_layout(
        mapbox=dict(style=_MAP_STYLE, center=_MAP_CENTER, zoom=_MAP_ZOOM),
        margin={'r': 0, 't': 0, 'l': 0, 'b': 0},
        height=_MAP_HEIGHT, width=_MAP_WIDTH, showlegend=False,
    )
    _save_map(fig, outpath)
