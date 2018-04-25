# Archive of Mass ENvironmental Data Site

The Archive of Mass ENvironmental Data (AMEND) is a project to assemble and analyze data related to environmental regulation, focused on water policy in Massachusetts.

The website for the project can be [viewed here](https://nesanders.github.io/MAenvironmentaldata/).

This git repository contains code for data acquisition (see get_data subdirectory), analysis (see analysis subdirectory), and the [jekyll](https://jekyllrb.com/) site for this project (see docs subdirectory).

You can run the single convenience script *update_all.sh* to (re)generate all content associated with the site.

## Hosting the site

The python scripts in this repository automatically feed content to a static website generated with jekyll.  The website is hosted via [GitHub Pages](https://help.github.com/articles/using-jekyll-as-a-static-site-generator-with-github-pages/) or can be [run locally with the proper Ruby configuration](https://help.github.com/articles/setting-up-your-github-pages-site-locally-with-jekyll/).

## Python dependencies

Several python packages are required to execute the scripts needed to generate this website:

* numpy 1.13.0
* matplotlib 2.0.0
* scipy 0.19.0
* pandas 0.20.0
* folium 0.5.0
* sqlalchemy 1.1.6
* census 0.8.1
* urllib2 2.7
* BeautifulSoup4 4.4.1
* unidecode 2.7.12
* requests 2.12.1
* sodapy 1.4.3
* shapely 1.6.4.post1

## Other tools used

* [chart.js](http://www.chartjs.org/) was used to generate interactive charts for the website.

* [Leaflet](http://leafletjs.com) for interactive map display.

* [MapShaper](http://mapshaper.org/) was used to convert MA's Office of Geographic Information (MassGIS) shapefiles ([Towns](http://www.mass.gov/anf/research-and-tech/it-serv-and-support/application-serv/office-of-geographic-information-massgis/datalayers/townsurvey.html), [Watersheds](http://www.mass.gov/anf/research-and-tech/it-serv-and-support/application-serv/office-of-geographic-information-massgis/datalayers/watrshds.html)) into a simplified geo-json format for web display.

* [sql.js](https://github.com/kripken/sql.js/blob/master/README.md) is used to enable interactive querying of the site's integrated database.

* [Tabula](http://tabula.technology/) was used to extract tables from PDF files. 

