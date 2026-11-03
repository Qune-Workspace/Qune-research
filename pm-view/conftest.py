"""Put this folder and the repository root on the path so that the tests import
pm_lib, fetch and score the way the scripts run from here."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for p in (str(HERE), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)
