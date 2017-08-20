"""
Supporting class for choropleth popups in folium via https://nbviewer.jupyter.org/gist/BibMartin/4b9784461d2fa0d89353
"""


from branca.utilities import _locations_mirror
from folium.features import *
from folium.features import _locations_tolist
from matplotlib.colors import rgb2hex
from matplotlib import cm

class MultiPolygon(MacroElement):
    """
    !! This is hacked from folium.features.MultiPolyLine !! 
    
    """
    def __init__(self, locations, color=None, weight=None,
                 opacity=None, latlon=True, popup=None):
        super(MultiPolygon, self).__init__()
        self._name = 'MultiPolygon'
        self.data = (_locations_mirror(locations) if not latlon else
                     _locations_tolist(locations))
        self.color = color
        self.weight = weight
        self.opacity = opacity
        if isinstance(popup, text_type) or isinstance(popup, binary_type):
            self.add_children(Popup(popup))
        elif popup is not None:
            self.add_children(popup)

        self._template = Template(u"""
            {% macro script(this, kwargs) %}
                var {{this.get_name()}} = L.multiPolygon(
                    {{this.data}},
                    {
                        {% if this.color != None %}color: '{{ this.color }}',{% endif %}
                        {% if this.weight != None %}weight: {{ this.weight }},{% endif %}
                        {% if this.opacity != None %}opacity: {{ this.opacity }},{% endif %}
                        });
                {{this._parent.get_name()}}.addLayer({{this.get_name()}});
            {% endmacro %}
            """)  # noqa

    def _get_self_bounds(self):
        """Computes the bounds of the object itself (not including it's children)
        in the form [[lat_min, lon_min], [lat_max, lon_max]]
        """
        bounds = [[None, None], [None, None]]
        for point in iter_points(self.data):
            bounds = [
                [
                    none_min(bounds[0][0], point[0]),
                    none_min(bounds[0][1], point[1]),
                ],
                [
                    none_max(bounds[1][0], point[0]),
                    none_max(bounds[1][1], point[1]),
                ],
            ]
        return bounds
