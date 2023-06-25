# Archive of Mass ENvironmental Data Site

The Archive of Mass ENvironmental Data (AMEND) is a project to assemble and analyze data related to environmental regulation, focused on water policy in Massachusetts.

The website for the project can be [viewed here](https://nesanders.github.io/MAenvironmentaldata/).

This git repository contains code for data acquisition (see `get_data` subdirectory), analysis (see analysis subdirectory), and the [`jekyll`](https://jekyllrb.com/) site for this project (see docs subdirectory).


## Updating data from the sources

You can run the `bash` convenience script `update_all.sh` to (re)generate all content associated with the site.

## Hosting the site

The `python3` (3.7) scripts in this repository automatically feed content to a static website generated with `jekyll`.  The website is hosted via [GitHub Pages](https://help.github.com/articles/using-jekyll-as-a-static-site-generator-with-github-pages/) or can be [run locally with the proper Ruby configuration](https://help.github.com/articles/setting-up-your-github-pages-site-locally-with-jekyll/).

To install the local `jekyll` server, you can follow this multi-step process:

```
conda create --name amend_jekyll
conda activate amend_jekyll
conda install -c conda-forge ruby=3.2.2
conda install -c conda-forge rb-bundler
gem install commonmarker -v '0.17.13' --source 'https://rubygems.org/'
conda install gxx_linux-64
cd docs
bundle install
```

Alternatively, use the premade `yml` file to instantiate teh conda environemnt like,

```
conda env create -f amend_jekyll_env.yml
```

To launch the server, run the following from the `docs` directory:

```
bundle exec jekyll serve
```

## Python dependencies

Several `python3` packages are required to execute the `python` scripts needed to generate this website, specified in `amend_python_env.yml`. You can install this environment with,

```
conda env create -f amend_python_env.yml
```


## Other tools used

* [chart.js](http://www.chartjs.org/) was used to generate interactive charts for the website.

* [Leaflet](http://leafletjs.com) for interactive map display.

* [MapShaper](http://mapshaper.org/) was used to convert MA's Office of Geographic Information (MassGIS) shapefiles ([Towns](http://www.mass.gov/anf/research-and-tech/it-serv-and-support/application-serv/office-of-geographic-information-massgis/datalayers/townsurvey.html), [Watersheds](http://www.mass.gov/anf/research-and-tech/it-serv-and-support/application-serv/office-of-geographic-information-massgis/datalayers/watrshds.html)) into a simplified geo-json format for web display.

* [sql.js](https://github.com/kripken/sql.js/blob/master/README.md) is used to enable interactive querying of the site's integrated database.

* [Tabula](http://tabula.technology/) was used to extract tables from PDF files. 



# TODO
* Take average over nearby census blocks
