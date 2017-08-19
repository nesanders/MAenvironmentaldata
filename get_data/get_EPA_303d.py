"""
Clean Water Act Section 303(d) relates to Impaired Waters and Total Maximum Daily Loads (TMDLs).  See https://www.epa.gov/tmdl for more details

The US EPA ATTAINS program published data related to 303(d).  

For more information on ATTAINS, see: https://www.epa.gov/waterdata/assessment-and-total-maximum-daily-load-tracking-and-implementation-system-attains

For more information on the ATTAINS data assets, see https://www.epa.gov/waterdata/waters-geospatial-data-downloads#303dListedImpairedWaters for more details.

The best way to obtain up-to-date information from ATTAINS is to query EPA's WATERS web services.

WATERS is described here: https://www.epa.gov/waterdata/waters-watershed-assessment-tracking-environmental-results-system

The web services for WATERS are described here: https://www.epa.gov/waterdata/waters-web-services
"""

import pandas as pd
import sodapy
import datetime
import os
