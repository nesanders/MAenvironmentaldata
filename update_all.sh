# Run this script to update all automated data downloads, chart generations, and database files
#
# This script WILL NOT:
# * Update ECOS budget records
# * Update SSA wage table

cd get_data

## Get data
python get_data/get_EPARegion1_NPDES_permits.py
python get_data/get_MassBudget_environmental.py
python get_data/get_DEP_staff_SODA.py
python get_data/get_DEP_staff.py
python get_data/get_Census_ACS.py
python get_data/get_DEP_enforcement_actions.py

## Transformations
python get_data/transform_ECOS_data.py

## Assemble DB
python get_data/assemble_db.py

cd ..
cd analysis

## Update charts
python analysis/SSA_wages_viz.py
python analysis/MADEP_staff.py
python analysis/MADEP_budget_viz.py
python analysis/MADEP_enforcements_viz.py

