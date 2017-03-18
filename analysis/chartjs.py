#
# Python ChartJS - (C) 2015 Patrick Lambert - Provided under the MIT License - https://github.com/dendory/chartjs
# Uses the ChartJS JavaScript implementation by Nick Downie
#
# Updated by nesanders to support chart.js 2.5
#
ctypes = ["Bar", "Pie", "Doughnut", "PolarArea", "Radar", "Line"]

class chart:
	# Set labels for all chart types
	def set_labels(self, labels):
		self.labels = labels

	# Set individual colors for pie, doughnut and polar charts
	def set_colors(self, colors):
		self.colors = colors

	# Set individual highlights for pie, doughnut and polar charts
	def set_highlights(self, highlights):
		self.highlights = highlights

	# Set global parameters, and color parameters for a whole line, radar or bar chart
	def set_params(self, 
		fillColor = None, strokeColor = None, 
		highlightFill = None, highlightStroke = None, 
		barValueSpacing = None, 
		scaleShowGridLines = None, pointColor = None, pointStrokeColor = None, 
		pointHighlightFill = None, pointHighlightStroke = None, 
		JSinline = None, scaleBeginAtZero = None,
		xlabel = None, ylabel = None):
		
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
		if scaleShowGridLines != None:
			self.scaleShowGridLines = scaleShowGridLines
		if pointColor:
			self.pointColor = pointColor
		if pointStrokeColor:
			self.pointStrokeColor = pointStrokeColor
		if pointHighlightFill:
			self.pointHighlightFill = pointHighlightFill
		if pointHighlightStroke:
			self.pointHighlightStroke = pointHighlightStroke
		if JSinline != None:
			if JSinline:
				self.js = jsinline
			else:
				self.js = jsurl
		if scaleBeginAtZero != None:
			self.scaleBeginAtZero = scaleBeginAtZero
		if xlabel != None:
			self.xlabel = xlabel
		if ylabel != None:
			self.ylabel = ylabel

	# Add a dataset to the chart
	def add_dataset(self, data, dataset_label = ''):
		if self.ctype == "Bar" or self.ctype == "Radar" or self.ctype == "Line": # Line, radar or bar charts
			if len(data) != len(self.labels):
				raise ValueError("Data must be the same size as labels.")
			self.data.append({
				"data": data, 
				"fillColor": self.fillColor, "strokeColor": self.strokeColor, 
				"highlightFill": self.highlightFill, "highlightStroke": self.highlightStroke, 
				"pointColor": self.pointColor, "pointStrokeColor": self.pointStrokeColor, 
				"pointHighlightFill": self.pointHighlightFill, "pointHighlightStroke": self.pointHighlightStroke,
				"label": dataset_label,
				
				})
		else: # Pie, doughnut or polar charts
			if len(data) != len(self.labels) or len(data) != len(self.highlights) or len(data) != len(self.colors):
				raise ValueError("Data, labels, colors and highlights should all have the same number of values for Pie, Doughnut and PolarArea charts.")
			self.data = [] # Only one dataset can be present for these charts
			for i, d in enumerate(data):
				self.data.append({'value': int(d), 'color': str(self.colors[i]), 'highlight': str(self.highlights[i]), 'label': str(self.labels[i])})

	# Make a chart canvas part
	def make_chart_canvas(self):
		if self.ctype == "Bar" or self.ctype == "Radar" or self.ctype == "Line":  
			dataset = """{{
				
					data: {{
						labels: {0},
						datasets: {1}
					}},
					type: '{2}',
					options: {{
						scales: {{
							yAxes: [{{
								scaleLabel: {{
									display: true,
									labelString: '{3}'
								}}
							}}],
							xAxes: [{{
								scaleLabel: {{
									display: true,
									labelString: '{4}'
								}}
							}}]
						}}
					}}
				}}""".format(str(self.labels), str(self.data), str(self.ctype).lower(), self.ylabel, self.xlabel)
		else:
			dataset = """
			{0}
""".format(str(self.data))
		output = """
			<canvas id="{0}" height="{1}" width="{2}"></canvas>
			<script>
				var chart_data = {3}
			</script>
""".format(str(self.canvas), str(self.height), str(self.width), dataset)
		return output

	# Make onload function
	def make_chart_onload(self):
		output = """
					var ctx = document.getElementById("{0}").getContext("{1}");
					var mychart = new Chart(ctx, chart_data);
""".format(str(self.canvas), str(self.context), str(self.ctype), str(self.barValueSpacing), str(self.scaleShowGridLines).lower(), str(self.scaleBeginAtZero).lower())
		return output

	# Make a chart based on datasets
	def make_chart(self):
		output = self.make_chart_canvas()
		#output += """			<script>
				#window.onload = function()
				#{{"""
		output += """			<script>
				{{"""
		output += self.make_chart_onload()
		output += """				}}
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

	# Initialize default values
	def __init__(self, title = "Untitled chart", ctype = "Bar", width = 640, height = 480):
		if ctype not in ctypes:
			raise ValueError("Invalid chart type specified.")
		self.title = title
		self.canvas = "canvas"
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
		self.xlabel = ''
		self.ylabel = ''

# JavaScript (URL and inline)
jsurl = "<script src='https://cdnjs.cloudflare.com/ajax/libs/Chart.js/2.5.0/Chart.bundle.min.js'></script>"
jsinline = ''
