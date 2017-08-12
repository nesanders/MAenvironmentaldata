# Run this script to update all automated data downloads, chart generations, and database files
#
# This script WILL NOT:
# * Update ECOS budget records
# * Update SSA wage table

cd get_data

## Get data
python get_EPARegion1_NPDES_permits.py
python get_MassBudget_environmental.py
python get_DEP_staff_SODA.py
python get_DEP_staff.py
python get_Census_ACS.py
python get_Census_statepop.py
python get_DEP_enforcement_actions.py

## Transformations
python transform_ECOS_data.py

## Assemble DB
python assemble_db.py

cd ..
cd analysis

## Update charts
python SSA_wages_viz.py
python MADEP_staff.py
python MADEP_budget_viz.py
python MADEP_enforcements_viz.py
python ECOS_budgets_viz.py

## Exclude large files from git repository
cd ..
sh ignore_large_files.sh
