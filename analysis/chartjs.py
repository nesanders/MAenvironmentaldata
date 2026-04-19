#
# Python ChartJS - (C) 2015 Patrick Lambert - Provided under the MIT License - https://github.com/dendory/chartjs
# Uses the ChartJS JavaScript implementation by Nick Downie
#
# Updated by nesanders to support Chart.js 4.x
#
import numpy as np

ctypes = ["Bar", "HorizontalBar", "Pie", "Doughnut", "PolarArea", "Radar", "Line", "Scatter"]

def js_str(x):
    out = '{'
    for i, key in enumerate(x.keys()):
        out += (", " if i > 0 else '') + "'"+key+"': " + str(x[key])
    return out + '}'


class chart:
    # Set labels for all chart types
    def set_labels(self, labels):
        self.labels = [str(c) for c in labels]  # convert from e.g. unicode type, which js will not recognize

    # Set individual colors for pie, doughnut and polar charts
    def set_colors(self, colors):
        self.colors = colors

    # Set individual highlights for pie, doughnut and polar charts
    def set_highlights(self, highlights):
        self.highlights = highlights

    # Set global parameters, and color parameters for a whole line, radar or bar chart
    def set_params(self,
        fillColor=None, strokeColor=None,
        highlightFill=None, highlightStroke=None,
        barValueSpacing=None,
        scaleShowGridLines=None, pointColor=None, pointStrokeColor=None,
        pointHighlightFill=None, pointHighlightStroke=None,
        JSinline=None, scaleBeginAtZero=None,
        y2nd=None, y2nd_title=None,
        xlabel=None, ylabel=None, stacked=None,
        legend=None, tooltips=None, custom_tooltips=None, yaxis_type=None, x_autoskip=None,
        fontsize=12):

        if fillColor:
            self.fillColor = fillColor
        if strokeColor:
            self.strokeColor = strokeColor
        if highlightFill:
            self.highlightFill = highlightFill
        if highlightStroke:
            self.highlightStroke = highlightStroke
        if barValueSpacing:
            self.barValueSpacing = barValueSpacing
        if scaleShowGridLines is not None:
            self.scaleShowGridLines = scaleShowGridLines
        if pointColor:
            self.pointColor = pointColor
        if pointStrokeColor:
            self.pointStrokeColor = pointStrokeColor
        if pointHighlightFill:
            self.pointHighlightFill = pointHighlightFill
        if pointHighlightStroke:
            self.pointHighlightStroke = pointHighlightStroke
        if JSinline is not None:
            if JSinline:
                self.js = jsinline
            else:
                self.js = jsurl
        if scaleBeginAtZero:
            self.scaleBeginAtZero = True
        if y2nd:
            self.y2nd = 'true'
        if y2nd_title is not None:
            self.y2nd_title = y2nd_title
        if xlabel is not None:
            self.xlabel = xlabel
        if ylabel is not None:
            self.ylabel = ylabel
        if stacked is not None:
            self.stacked = 'true'
        if legend is False:
            self.legend = 'false'
        if tooltips is False:
            self.tooltips = 'false'
        if custom_tooltips is None:
            self.custom_tooltips = ''
        else:
            self.custom_tooltips = ", " + custom_tooltips
        if yaxis_type is not None:
            self.yaxis_type = yaxis_type
        if x_autoskip is False:
            self.x_autoskip = 'false'
        else:
            self.x_autoskip = 'true'
        self.fontsize = fontsize

    def set_tick_wrap(self, max_chars=28, axis='y'):
        """Word-wrap long axis tick labels by injecting a ticks.callback.

        Useful for HorizontalBar charts with long category names on the y-axis.
        Chart.js renders an array return value as multi-line tick text.

        Parameters
        ----------
        max_chars : int
            Maximum characters per line before wrapping.
        axis : str
            Scale key to apply the callback to ('x' or 'y').
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

    def set_locale_ticks(self, axis='y'):
        """Format axis tick labels with locale-aware number formatting (toLocaleString).

        Replaces numbers with comma-separated strings (e.g. 1000 → "1,000").
        Passes non-numeric values through unchanged.

        Parameters
        ----------
        axis : str
            Scale key to apply the callback to ('x' or 'y').
        """
        self.tick_callbacks[axis] = (
            "return typeof value === 'number' ? value.toLocaleString() : value;"
        )

    def set_ticks_callback(self, axis, callback_body_js):
        """Inject a custom ticks.callback for an axis scale.

        Parameters
        ----------
        axis : str
            Scale key ('x' or 'y').
        callback_body_js : str
            JavaScript function body (without the ``function(value, index, ticks) {``
            wrapper — just the body statements, including a ``return`` statement).
        """
        self.tick_callbacks[axis] = callback_body_js

    # Add a dataset to the chart
    def add_dataset(self, data, dataset_label='', **kwargs):

        ## Other data types expect data as list; scatter expects array and is handled separately below
        if self.ctype != 'Scatter':
            data = ['null' if np.isnan(d) else d for d in data]

        if self.ctype in ["Bar", "HorizontalBar", "Radar", "Line"]:  # Line, radar or bar charts
            if len(data) != len(self.labels):
                raise ValueError("Data must be the same size as labels.")

            appendargs = {'data': data, 'label': "'" + dataset_label + "'"}
            appendargs.update(kwargs.items())

            self.data.append(js_str(appendargs))

        elif self.ctype in ["Pie", "Doughnut", "Polar"]:  # Pie, doughnut or polar charts
            if len(data) != len(self.labels) or len(data) != len(self.highlights) or len(data) != len(self.colors):
                raise ValueError("Data, labels, colors and highlights should all have the same number of values for Pie, Doughnut and PolarArea charts.")
            self.data = []  # Only one dataset can be present for these charts
            for i, d in enumerate(data):
                self.data.append({'value': int(d), 'color': str(self.colors[i]), 'highlight': str(self.highlights[i]), 'label': str(self.labels[i])})

        elif self.ctype == 'Scatter':
            data = np.array(data).astype(str)
            data[data == 'nan'] = 'null'
            if len(np.shape(data)) == 2 and np.shape(data)[1] != 2:
                raise ValueError("Data must be two-dimensional for Scatter charts.")
            appendargs = {
                'data': '[' + ', '.join(['{x: ' + str(data[i, 0]) + ', y: ' + str(data[i, 1]) + '}' for i in range(len(data))]) + ']',
                'label': "'" + dataset_label + "'"}
            appendargs.update(kwargs.items())

            self.data.append(js_str(appendargs))

    def _build_scale_ticks(self, axis):
        """Return a ticks sub-object string for the given axis, or empty string if none needed."""
        if axis not in self.tick_callbacks:
            return ''
        return (
            f",\n                            ticks: {{"
            f" callback: function(value, index, ticks) {{ {self.tick_callbacks[axis]} }} }}"
        )

    # Make a chart canvas part
    def make_chart_canvas(self):
        if self.ctype in ["Bar", "HorizontalBar", "Radar", "Line", "Scatter"]:
            # ── y-axis range options ──────────────────────────────────────────
            y_range_parts = []
            if self.scaleBeginAtZero:
                y_range_parts.append('beginAtZero: true')
            if self.y_min is not None:
                y_range_parts.append(f'min: {self.y_min}')
            if self.y_max is not None:
                y_range_parts.append(f'max: {self.y_max}')
            y_range = (',\n                            '.join(y_range_parts))
            if y_range:
                y_range = '\n                            ' + y_range + ','

            # ── y-axis type (log, etc.) ───────────────────────────────────────
            y_type = ''
            if self.yaxis_type is not None:
                y_type = f'\n                            type: "{self.yaxis_type}",'

            # ── per-axis tick callbacks ───────────────────────────────────────
            y_ticks  = self._build_scale_ticks('y')
            x_ticks_cb = ''
            if 'x' in self.tick_callbacks:
                x_ticks_cb = (
                    f",\n                            callback: function(value, index, ticks) "
                    f"{{ {self.tick_callbacks['x']} }}"
                )

            # ── HorizontalBar: type='bar' + indexAxis='y' ─────────────────────
            index_axis = ''
            if self.ctype == 'HorizontalBar':
                index_axis = "\n                        indexAxis: 'y',"
            chart_type = 'bar' if self.ctype == 'HorizontalBar' else self.ctype.lower()

            dataset = """{{

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
                labels=str(self.labels),
                datasets='[' + ','.join([str(c) for c in self.data]) + ']',
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
            dataset = """
            {0}
""".format(str(self.data))
        output = """
            <canvas id="{0}" height="{1}" width="{2}"></canvas>
            <script>
                Chart.defaults.font.size = {5};
                var chart_data = {3}

                {4}
            </script>
""".format(str(self.canvas), str(self.height), str(self.width), dataset, self.extra_code, self.fontsize)
        return output

    # Make onload function
    def make_chart_onload(self):
        output = """
                    var ctx = document.getElementById("{0}").getContext("{1}");
                    var mychart = new Chart(ctx, chart_data);
""".format(str(self.canvas), str(self.context))
        return output

    # Make a chart based on datasets
    def make_chart(self):
        output = self.make_chart_canvas()
        output += """            <script>
                {{"""
        output += self.make_chart_onload()
        output += """                }}
            </script>
"""
        return output

    # Make a full HTML page
    def make_chart_full_html(self):
        output = """<!doctype html>
<html>
    <head>
        <title>{0}</title>
        {1}
    </head>
    <body>
        <div style="width: {2}px; height: {3}px; max-width: 99%" class="chartjs">
            <center><h2>{0}</h2></center>
""".format(str(self.title), self.js, str(self.width), str(self.height))
        output += self.make_chart()
        output += """
        </div>
    </body>
</html>
"""
        return output

    # Return full headers along with the HTML
    def make_chart_with_headers(self):
        output = "HTTP/1.0 200 OK\n"
        output += "Content-Type: text/html; charset=utf-8\n\n"
        output += self.make_chart_full_html()
        return output

    def jekyll_write(self, path, full=1):
        """
        Write out in a way appropriate to include in jekyll sites
        """
        with open(path, 'w') as f:
            f.write("{% raw  %}\n")
            if full:
                mc = self.make_chart_full_html()
            else:
                mc = self.make_chart()
            if full == 0:
                indents = mc.split('<canvas id=')[0]
                mc = '\n'.join([row.lstrip(indents) for row in mc.split('\n')])
            out = mc.split('\n')
            out = [o for o in out if '<h2>' not in o and 'doctype html' not in o]
            out = '\n'.join(out)
            f.write(out)
            f.write("{% endraw  %}\n")

    def add_extra_code(self, code):
        """
        Add extra JavaScript to the end of the chart's <script> block, e.g. to inject
        data variables (point labels, population arrays) accessible to tooltip callbacks.
        """
        self.extra_code += '\n\n' + code

    # Initialize default values
    def __init__(self, title="Untitled chart", ctype="Bar", width=640, height=480):
        if ctype not in ctypes:
            raise ValueError("Invalid chart type specified.")
        self.title = title
        self.canvas = title.strip()
        self.context = "2d"
        self.ctype = ctype
        self.width = int(width)
        self.height = int(height)
        self.data = []
        self.labels = []
        self.colors = []
        self.highlights = []
        self.fillColor = "rgba(151,187,205,0.5)"
        self.strokeColor = "rgba(151,187,205,0.8)"
        self.highlightFill = "rgba(151,187,205,0.75)"
        self.highlightStroke = "rgba(151,187,205,1)"
        self.pointColor = "rgba(220,220,220,1)"
        self.pointStrokeColor = "rgba(250,250,250,1)"
        self.pointHighlightFill = "rgba(250,250,250,1)"
        self.pointHighlightStroke = "rgba(220,220,220,1)"
        self.barValueSpacing = 5
        self.scaleShowGridLines = True
        self.js = jsinline
        self.scaleBeginAtZero = False
        self.y_min = None
        self.y_max = None
        self.y2nd = 'false'
        self.y2nd_title = ""
        self.xlabel = ''
        self.ylabel = ''
        self.stacked = 'false'
        self.legend = 'true'
        self.tooltips = 'true'
        self.custom_tooltips = ''
        self.yaxis_type = None
        self.tick_callbacks = {}
        self.extra_code = ''


# JavaScript (URL and inline)
jsurl = "<script src='https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js'></script>"
jsinline = ''
