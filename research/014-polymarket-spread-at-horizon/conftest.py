"""Make the study folder importable as the package root for pytest, so that ``from src import ...`` and
``from tests import ...`` resolve from any working directory (this study has no collector; the convention
is Studies 009–013's)."""
import sys
from pathlib import Path

STUDY_DIR = str(Path(__file__).resolve().parent)
if STUDY_DIR not in sys.path:
    sys.path.insert(0, STUDY_DIR)
