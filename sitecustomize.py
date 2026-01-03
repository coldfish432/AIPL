"""Redirect .pyc output into a local cache to avoid restricted __pycache__ dirs."""
import os
import sys

prefix = os.path.join(os.path.dirname(__file__), "pyc_cache")
try:
    os.makedirs(prefix, exist_ok=True)
except OSError:
    prefix = None

if prefix:
    sys.pycache_prefix = prefix
