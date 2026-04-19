"""Python wrapper for Chart.js 4.x chart generation.

Original: (C) 2015 Patrick Lambert - https://github.com/dendory/chartjs (MIT License)
Updated by nesanders for Chart.js 4.x.
"""
from __future__ import annotations

import json
import math
from typing import Any

import numpy as np


class _NumpyEncoder(json.JSONEncoder):
    """JSON encoder that converts numpy scalars and NaN/Inf to JS-safe values."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return None if math.isnan(float(obj)) else float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

    def encode(self, obj: Any) -> str:
        # Override to handle nan/inf in plain Python floats too
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return "null"
        return super().encode(obj)

    def iterencode(self, obj: Any, **kwargs: Any):  # type: ignore[override]
        # Patch floats inside containers via default chunked encoding
        for chunk in super().iterencode(obj, **kwargs):
            yield chunk


def _to_json(value: Any) -> str:
    """Serialize *value* to a JSON string safe for embedding in JS literals."""
    return json.dumps(value, cls=_NumpyEncoder)


CHART_TYPES = [
    "Bar", "HorizontalBar", "Pie", "Doughnut",
    "PolarArea", "Radar", "Line", "Scatter",
]

# CDN <script> tag inserted into the page <head> when js_inline=False.
JS_URL = (
    "<script src='https://cdn.jsdelivr.net/npm/chart.js@4.4.4"
    "/dist/chart.umd.min.js'></script>"
)
# Empty string: caller is responsible for loading Chart.js (default).
JS_INLINE = ""


def _js_obj(d: dict[str, Any]) -> str:
    """Render a Python dict as a JavaScript object literal string."""
    parts = [(", " if i > 0 else "") + f"'{k}': {v}" for i, (k, v) in enumerate(d.items())]
    return "{" + "".join(parts) + "}"


class Chart:
    """Generate Chart.js 4.x chart HTML snippets for embedding in Jekyll pages.

    Usage pattern::

        mychart = Chart("My title", "Bar", width=640, height=400)
        mychart.set_labels(["2020", "2021", "2022"])
        mychart.add_dataset([10, 20, 30], "Series A", backgroundColor="'blue'")
        mychart.set_params(js_inline=False, ylabel="Count", xlabel="Year")
        mychart.jekyll_write("../docs/_includes/charts/my_chart.html")
    """

    def __init__(
        self,
        title: str = "Untitled chart",
        ctype: str = "Bar",
        width: int = 640,
        height: int = 480,
    ) -> None:
        if ctype not in CHART_TYPES:
            raise ValueError(
                f"Invalid chart type '{ctype}'. Valid types: {CHART_TYPES}"
            )
        self.title = title
        self.canvas = title.strip()
        self.context = "2d"
        self.ctype = ctype
        self.width = int(width)
        self.height = int(height)

        # Dataset storage
        self.data: list = []
        self.labels: list[str] = []
        self.colors: list = []
        self.highlights: list = []

        # Legacy Chart.js 1.x colour knobs (no effect on rendered output in 4.x)
        self.fill_color = "rgba(151,187,205,0.5)"
        self.stroke_color = "rgba(151,187,205,0.8)"
        self.highlight_fill = "rgba(151,187,205,0.75)"
        self.highlight_stroke = "rgba(151,187,205,1)"
        self.point_color = "rgba(220,220,220,1)"
        self.point_stroke_color = "rgba(250,250,250,1)"
        self.point_highlight_fill = "rgba(250,250,250,1)"
        self.point_highlight_stroke = "rgba(220,220,220,1)"
        self.bar_value_spacing = 5
        self.scale_show_grid_lines = True

        # JS loading
        self.js = JS_INLINE

        # Axis / scale options (stored as JS literal strings where needed)
        self.scale_begin_at_zero = False
        self.y_min: float | None = None
        self.y_max: float | None = None
        self.y2nd = "false"        # JS boolean string
        self.y2nd_title = ""
        self.xlabel = ""
        self.ylabel = ""
        self.stacked = "false"     # JS boolean string
        self.yaxis_type: str | None = None
        self.x_autoskip = "true"   # JS boolean string

        # Plugin options (stored as JS literal strings where needed)
        self.legend = "true"       # JS boolean string
        self.tooltips = "true"     # JS boolean string
        self.custom_tooltips = ""  # injected verbatim after 'enabled: ...'

        # Per-axis ticks.callback bodies (plain JS, no function wrapper)
        self.tick_callbacks: dict[str, str] = {}

        # Extra JS appended inside the chart's <script> block
        self.extra_code = ""
        self.fontsize = 12

    # -------------------------------------------------------------------------
    # Data configuration
    # -------------------------------------------------------------------------

    def set_labels(self, labels: list) -> None:
        """Set category labels for all chart types."""
        # str() converts numpy scalars and other types to JS-safe strings
        self.labels = [str(c) for c in labels]

    def set_colors(self, colors: list) -> None:
        """Set slice colors for Pie / Doughnut / PolarArea charts."""
        self.colors = colors

    def set_highlights(self, highlights: list) -> None:
        """Set slice highlight colors for Pie / Doughnut / PolarArea charts."""
        self.highlights = highlights

    def add_dataset(
        self,
        data: list | np.ndarray,
        dataset_label: str = "",
        **kwargs: Any,
    ) -> None:
        """Append a dataset to the chart.

        Parameters
        ----------
        data:
            Sequence of numeric values.  For Scatter charts, a 2-D array/list
            of ``[x, y]`` pairs.  ``nan`` values are serialised as ``null``.
        dataset_label:
            Legend label for this dataset.
        **kwargs:
            Any additional Chart.js dataset properties, passed verbatim as
            JavaScript object keys.  String values that should appear as JS
            strings must be pre-quoted, e.g. ``backgroundColor="'red'"``.
        """
        if self.ctype != "Scatter":
            # Coerce numpy scalars to Python natives; map NaN/None → null
            clean: list[Any] = []
            for d in data:
                if d is None:
                    clean.append(None)
                elif isinstance(d, np.integer):
                    clean.append(int(d))
                elif isinstance(d, np.floating):
                    clean.append(None if math.isnan(float(d)) else float(d))
                elif isinstance(d, float) and math.isnan(d):
                    clean.append(None)
                else:
                    clean.append(d)
            data = clean

        if self.ctype in ("Bar", "HorizontalBar", "Radar", "Line"):
            if len(data) != len(self.labels):
                raise ValueError("Data length must match labels length.")
            args: dict[str, Any] = {"data": _to_json(data), "label": f"'{dataset_label}'"}
            args.update(kwargs)
            self.data.append(_js_obj(args))

        elif self.ctype in ("Pie", "Doughnut", "Polar"):
            if not (len(data) == len(self.labels) == len(self.highlights) == len(self.colors)):
                raise ValueError(
                    "Data, labels, colors, and highlights must all have the same length "
                    "for Pie, Doughnut, and PolarArea charts."
                )
            self.data = []  # Only one dataset is supported for these types
            for i, d in enumerate(data):
                self.data.append({
                    "value": int(d),
                    "color": str(self.colors[i]),
                    "highlight": str(self.highlights[i]),
                    "label": str(self.labels[i]),
                })

        elif self.ctype == "Scatter":
            arr = np.array(data).astype(str)
            arr[arr == "nan"] = "null"
            if arr.ndim == 2 and arr.shape[1] != 2:
                raise ValueError("Scatter data must be an (N, 2) array of [x, y] pairs.")
            points = ", ".join(
                f"{{x: {arr[i, 0]}, y: {arr[i, 1]}}}" for i in range(len(arr))
            )
            args = {"data": f"[{points}]", "label": f"'{dataset_label}'"}
            args.update(kwargs)
            self.data.append(_js_obj(args))

    # -------------------------------------------------------------------------
    # Display configuration
    # -------------------------------------------------------------------------

    def set_params(
        self,
        fill_color: str | None = None,
        stroke_color: str | None = None,
        highlight_fill: str | None = None,
        highlight_stroke: str | None = None,
        bar_value_spacing: int | None = None,
        scale_show_grid_lines: bool | None = None,
        point_color: str | None = None,
        point_stroke_color: str | None = None,
        point_highlight_fill: str | None = None,
        point_highlight_stroke: str | None = None,
        js_inline: bool | None = None,
        scale_begin_at_zero: bool | None = None,
        y2nd: Any = None,
        y2nd_title: str | None = None,
        xlabel: str | None = None,
        ylabel: str | None = None,
        stacked: Any = None,
        legend: bool | None = None,
        tooltips: bool | None = None,
        custom_tooltips: str | None = None,
        yaxis_type: str | None = None,
        x_autoskip: bool | None = None,
        fontsize: int = 12,
    ) -> None:
        """Configure chart-level display options.

        Parameters
        ----------
        js_inline:
            ``True`` → embed Chart.js inline (no CDN tag);
            ``False`` → inject the CDN ``<script>`` tag into the page head.
        scale_begin_at_zero:
            Start the primary y-axis at zero.
        y2nd:
            Enable the secondary right-hand y-axis.
        y2nd_title:
            Label for the secondary y-axis.
        xlabel / ylabel:
            Axis title strings.
        stacked:
            Enable stacked bars/areas.
        legend:
            ``False`` hides the chart legend.
        tooltips:
            ``False`` disables hover tooltips.
        custom_tooltips:
            Raw JavaScript injected after ``enabled: true`` inside the
            ``plugins.tooltip`` config block.  Must begin with ``, ``.
        yaxis_type:
            Chart.js scale type for the primary y-axis, e.g. ``'logarithmic'``.
        x_autoskip:
            ``False`` forces all x-axis tick labels to be shown.
        fontsize:
            Default font size (px) applied via ``Chart.defaults.font.size``.
        """
        if fill_color:
            self.fill_color = fill_color
        if stroke_color:
            self.stroke_color = stroke_color
        if highlight_fill:
            self.highlight_fill = highlight_fill
        if highlight_stroke:
            self.highlight_stroke = highlight_stroke
        if bar_value_spacing:
            self.bar_value_spacing = bar_value_spacing
        if scale_show_grid_lines is not None:
            self.scale_show_grid_lines = scale_show_grid_lines
        if point_color:
            self.point_color = point_color
        if point_stroke_color:
            self.point_stroke_color = point_stroke_color
        if point_highlight_fill:
            self.point_highlight_fill = point_highlight_fill
        if point_highlight_stroke:
            self.point_highlight_stroke = point_highlight_stroke
        if js_inline is not None:
            self.js = JS_INLINE if js_inline else JS_URL
        if scale_begin_at_zero:
            self.scale_begin_at_zero = True
        if y2nd:
            self.y2nd = "true"
        if y2nd_title is not None:
            self.y2nd_title = y2nd_title
        if xlabel is not None:
            self.xlabel = xlabel
        if ylabel is not None:
            self.ylabel = ylabel
        if stacked is not None:
            self.stacked = "true"
        if legend is False:
            self.legend = "false"
        if tooltips is False:
            self.tooltips = "false"
        if custom_tooltips is None:
            self.custom_tooltips = ""
        else:
            self.custom_tooltips = ", " + custom_tooltips
        if yaxis_type is not None:
            self.yaxis_type = yaxis_type
        if x_autoskip is False:
            self.x_autoskip = "false"
        else:
            self.x_autoskip = "true"
        self.fontsize = fontsize

    def set_tick_wrap(self, max_chars: int = 28, axis: str = "y") -> None:
        """Word-wrap long axis tick labels by injecting a ``ticks.callback``.

        Chart.js renders an array return value from a tick callback as
        multi-line text.  Useful for HorizontalBar charts with long category
        names on the y-axis.

        Parameters
        ----------
        max_chars:
            Maximum characters per line before wrapping.
        axis:
            Scale key to apply the callback to (``'x'`` or ``'y'``).
        """
        self.tick_callbacks[axis] = (
            f"var words = String(value).split(' '); var lines = []; var line = '';"
            f" words.forEach(function(w) {{"
            f"  if ((line + ' ' + w).trim().length > {max_chars} && line) {{"
            f"   lines.push(line); line = w;"
            f"  }} else {{ line = (line ? line + ' ' : '') + w; }}"
            f" }});"
            f" if (line) lines.push(line);"
            f" return lines;"
        )

    def set_locale_ticks(self, axis: str = "y") -> None:
        """Format tick labels with locale-aware number formatting.

        Numbers are rendered via ``toLocaleString()`` (e.g. 1000 → "1,000").
        Non-numeric values are passed through unchanged.

        Parameters
        ----------
        axis:
            Scale key to apply the callback to (``'x'`` or ``'y'``).
        """
        self.tick_callbacks[axis] = (
            "return typeof value === 'number' ? value.toLocaleString() : value;"
        )

    def set_ticks_callback(self, axis: str, callback_body_js: str) -> None:
        """Inject a custom ``ticks.callback`` body for an axis scale.

        Parameters
        ----------
        axis:
            Scale key (``'x'`` or ``'y'``).
        callback_body_js:
            JavaScript function body — the statements that go *inside*
            ``function(value, index, ticks) { ... }``, including a
            ``return`` statement.
        """
        self.tick_callbacks[axis] = callback_body_js

    def add_extra_code(self, code: str) -> None:
        """Append raw JavaScript inside the chart's ``<script>`` block.

        Useful for injecting data variables (e.g. point label arrays,
        population lookups) that tooltip callbacks can reference.
        """
        self.extra_code += "\n\n" + code

    # -------------------------------------------------------------------------
    # HTML generation
    # -------------------------------------------------------------------------

    def _build_scale_ticks(self, axis: str) -> str:
        """Return a ``ticks: { callback: ... }`` sub-object for *axis*, or ``''``."""
        if axis not in self.tick_callbacks:
            return ""
        return (
            f",\n                            ticks: {{"
            f" callback: function(value, index, ticks)"
            f" {{ {self.tick_callbacks[axis]} }} }}"
        )

    def make_chart_canvas(self) -> str:
        """Return the ``<canvas>`` element and inline ``<script>`` block."""
        if self.ctype in ("Bar", "HorizontalBar", "Radar", "Line", "Scatter"):
            # ── y-axis range ─────────────────────────────────────────────────
            y_range_parts = []
            if self.scale_begin_at_zero:
                y_range_parts.append("beginAtZero: true")
            if self.y_min is not None:
                y_range_parts.append(f"min: {self.y_min}")
            if self.y_max is not None:
                y_range_parts.append(f"max: {self.y_max}")
            y_range = ""
            if y_range_parts:
                joined = ",\n                            ".join(y_range_parts)
                y_range = "\n                            " + joined + ","

            # ── y-axis type (logarithmic, etc.) ───────────────────────────────
            y_type = (
                f'\n                            type: "{self.yaxis_type}",'
                if self.yaxis_type is not None
                else ""
            )

            # ── per-axis tick callbacks ───────────────────────────────────────
            y_ticks = self._build_scale_ticks("y")
            x_ticks_cb = (
                f",\n                            callback: function(value, index, ticks)"
                f" {{ {self.tick_callbacks['x']} }}"
                if "x" in self.tick_callbacks
                else ""
            )

            # ── HorizontalBar → type='bar' + indexAxis='y' ────────────────────
            index_axis = "\n                        indexAxis: 'y'," if self.ctype == "HorizontalBar" else ""
            chart_type = "bar" if self.ctype == "HorizontalBar" else self.ctype.lower()

            dataset = """\
{{

                    data: {{
                        labels: {labels},
                        datasets: {datasets}
                    }},
                    type: '{ctype}',
                    options: {{{index_axis}
                        scales: {{
                            y: {{
                                display: true,
                                title: {{
                                    display: true,
                                    text: '{ylabel}'
                                }},{y_range}{y_type}
                                position: 'left',
                                stacked: {stacked}{y_ticks}
                            }},
                            y1: {{
                                display: {y2nd},
                                title: {{
                                    display: true,
                                    text: '{y2nd_title}'
                                }},
                                position: 'right'
                            }},
                            x: {{
                                title: {{
                                    display: true,
                                    text: '{xlabel}'
                                }},
                                stacked: {stacked},
                                ticks: {{
                                    autoSkip: {x_autoskip}{x_ticks_cb}
                                }}
                            }}
                        }},
                        plugins: {{
                            legend: {{
                                display: {legend}
                            }},
                            tooltip: {{
                                enabled: {tooltips}{custom_tooltips}
                            }}
                        }}
                    }}
                }}
                """.format(
                labels=_to_json(self.labels),
                datasets="[" + ",".join(str(c) for c in self.data) + "]",
                ctype=chart_type,
                index_axis=index_axis,
                ylabel=self.ylabel,
                xlabel=self.xlabel,
                y_range=y_range,
                y_type=y_type,
                stacked=self.stacked,
                y2nd=self.y2nd,
                y2nd_title=self.y2nd_title,
                y_ticks=y_ticks,
                x_autoskip=self.x_autoskip,
                x_ticks_cb=x_ticks_cb,
                legend=self.legend,
                tooltips=self.tooltips,
                custom_tooltips=self.custom_tooltips,
            )
        else:
            dataset = f"\n            {self.data}\n"

        return (
            f'\n            <canvas id="{self.canvas}"'
            f' height="{self.height}" width="{self.width}"></canvas>\n'
            f"            <script>\n"
            f"                Chart.defaults.font.size = {self.fontsize};\n"
            f"                var chart_data = {dataset}\n"
            f"                {self.extra_code}\n"
            f"            </script>\n"
        )

    def make_chart_onload(self) -> str:
        """Return the JS snippet that instantiates the Chart from ``chart_data``."""
        return (
            f'\n                    var ctx = document.getElementById("{self.canvas}")'
            f'.getContext("{self.context}");\n'
            f"                    var mychart = new Chart(ctx, chart_data);\n"
        )

    def make_chart(self) -> str:
        """Return canvas + initialisation script (no outer HTML page)."""
        return (
            self.make_chart_canvas()
            + "            <script>\n                {\n"
            + self.make_chart_onload()
            + "                }\n            </script>\n"
        )

    def make_chart_full_html(self) -> str:
        """Return a complete self-contained HTML page containing the chart."""
        return (
            f"<!doctype html>\n<html>\n    <head>\n"
            f"        <title>{self.title}</title>\n"
            f"        {self.js}\n    </head>\n    <body>\n"
            f'        <div style="width: {self.width}px; height: {self.height}px;'
            f' max-width: 99%" class="chartjs">\n'
            f"            <center><h2>{self.title}</h2></center>\n"
            + self.make_chart()
            + "        </div>\n    </body>\n</html>\n"
        )

    def make_chart_with_headers(self) -> str:
        """Return an HTTP/1.0 response string with the full HTML page."""
        return (
            "HTTP/1.0 200 OK\n"
            "Content-Type: text/html; charset=utf-8\n\n"
            + self.make_chart_full_html()
        )

    def jekyll_write(self, path: str, full: bool = True) -> None:
        """Write chart HTML to *path* wrapped in Jekyll ``{% raw %}`` tags.

        Parameters
        ----------
        path:
            Output file path.
        full:
            ``True`` (default) writes a complete HTML page; ``False`` writes
            only the ``<canvas>`` + ``<script>`` snippet for use inside an
            existing page layout.
        """
        mc = self.make_chart_full_html() if full else self.make_chart()
        if not full:
            indent = mc.split("<canvas id=")[0]
            mc = "\n".join(row.lstrip(indent) for row in mc.split("\n"))
        lines = [ln for ln in mc.split("\n") if "<h2>" not in ln and "doctype html" not in ln]
        with open(path, "w") as fh:
            fh.write("{% raw  %}\n")
            fh.write("\n".join(lines))
            fh.write("{% endraw  %}\n")


# ---------------------------------------------------------------------------
# Backward-compatible alias (callers that use ``chartjs.chart(...)`` continue
# to work without modification).
# ---------------------------------------------------------------------------
chart = Chart
