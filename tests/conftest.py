import os
import sys

# Ensure repo root is on the path so tests can import from get_data/ if needed
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
