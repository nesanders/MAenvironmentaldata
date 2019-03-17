# Archive of Mass ENvironmental Data Site

The Archive of Mass ENvironmental Data (AMEND) is a project to assemble and analyze data related to environmental regulation, focused on water policy in Massachusetts.

The website for the project can be [viewed here](https://nesanders.github.io/MAenvironmentaldata/).

This git repository contains code for data acquisition (see get_data subdirectory), analysis (see analysis subdirectory), and the [jekyll](https://jekyllrb.com/) site for this project (see docs subdirectory).

You can run the single convenience script *update_all.sh* (for bash) to (re)generate all content associated with the site.

## Hosting the site

The python3 scripts in this repository automatically feed content to a static website generated with jekyll.  The website is hosted via [GitHub Pages](https://help.github.com/articles/using-jekyll-as-a-static-site-generator-with-github-pages/) or can be [run locally with the proper Ruby configuration](https://help.github.com/articles/setting-up-your-github-pages-site-locally-with-jekyll/).

## Python dependencies

Several python3 packages are required to execute the scripts needed to generate this website:

* BeautifulSoup4-4.7.1
* census-0.8.13
* folium-0.8.3
* lxml-4.3.2
* matplotlib-3.0.2
* numpy-1.16.2
* pandas-0.24.2
* requests-2.21.0
* scipy-1.2.1
* shapely-1.6.4.post1
* sodapy-1.5.2
* sqlalchemy-1.3.1
* unidecode-1.0.23
* us-1.0.0

## Other tools used

* [chart.js](http://www.chartjs.org/) was used to generate interactive charts for the website.

* [Leaflet](http://leafletjs.com) for interactive map display.

* [MapShaper](http://mapshaper.org/) was used to convert MA's Office of Geographic Information (MassGIS) shapefiles ([Towns](http://www.mass.gov/anf/research-and-tech/it-serv-and-support/application-serv/office-of-geographic-information-massgis/datalayers/townsurvey.html), [Watersheds](http://www.mass.gov/anf/research-and-tech/it-serv-and-support/application-serv/office-of-geographic-information-massgis/datalayers/watrshds.html)) into a simplified geo-json format for web display.

* [sql.js](https://github.com/kripken/sql.js/blob/master/README.md) is used to enable interactive querying of the site's integrated database.

* [Tabula](http://tabula.technology/) was used to extract tables from PDF files. 

