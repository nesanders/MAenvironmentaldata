# Run this script to update all automated data downloads, chart generations, and database files
#
# This script WILL NOT:
# * Update ECOS budget records
# * Update SSA wage table

cd get_data

## Get data
python3 get_EPARegion1_NPDES_permits.py
python3 get_MassBudget_environmental.py
python3 get_DEP_staff_SODA.py
python3 get_DEP_staff.py
python3 get_Census_ACS.py
python3 get_Census_statepop.py
# python3 get_DEP_enforcement_actions.py # Deprecated
python3 get_EEA_data_portal.py

## Transformations - only need to be run once
# python3 transform_ECOS_data.py
# python3 transform_NECIR_CSO_data.py

## Assemble DB
python3 assemble_db.py

cd ..
cd analysis

## Update charts
python3 SSA_wages_viz.py
python3 MADEP_staff.py
python3 MADEP_budget_viz.py
python3 MADEP_enforcements_viz.py
python3 ECOS_budgets_viz.py

## Exclude large files from git repository
cd ..
sh ignore_large_files.sh
