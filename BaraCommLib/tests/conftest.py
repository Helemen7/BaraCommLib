import os, sys
# Ensure the package source directory is on PYTHONPATH.
import os
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..','src'))
sys.path.insert(0, base_dir)