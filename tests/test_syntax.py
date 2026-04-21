"""Syntax-check every Python script in get_data/ and analysis/.

Catches broken imports and syntax errors without executing anything.
Runs in ~2s, no dependencies beyond stdlib.
"""
import py_compile
import glob
import os
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

scripts = sorted(
    glob.glob(os.path.join(REPO_ROOT, "get_data", "*.py"))
    + glob.glob(os.path.join(REPO_ROOT, "analysis", "*.py"))
)


@pytest.mark.parametrize("path", scripts, ids=[os.path.basename(p) for p in scripts])
def test_compiles(path):
    py_compile.compile(path, doraise=True)
