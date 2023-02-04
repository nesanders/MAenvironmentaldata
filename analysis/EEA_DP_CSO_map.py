"""Generate folium-based map visualizations and pystan regression model fits to CSO distributions using 
MA EEA Data Portal CSO data. This follows the same basic structure as NECIR_CSO_map.py

NOTE - this code was updated in 2023 to use pystan 3 conventions

NOTE - if you run into pystan errors when executing this script in a conda environment, try using 
[this solution](https://github.com/stan-dev/pystan/issues/294#issuecomment-988791438)
to update the C compilers in the env.
```
conda install -c conda-forge c-compiler cxx-compiler
```
"""

import pandas as pd
import numpy as np
import folium
import json
from shapely.geometry import shape, Point
from sqlalchemy import create_engine
import chartjs
import stan

import matplotlib as mpl
from matplotlib import pyplot as plt
from matplotlib import cm

from ./NECIR_CSO_MAP import 

## Establish file to export facts
FACT_FILE = '../docs/data/facts_EEA_DP_CSO.yml'
with open(FACT_FILE, 'w') as f: f.write('')

