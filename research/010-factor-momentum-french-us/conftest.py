"""Make the study folder importable as the package root for pytest, so that
``from src import ...`` works (copied from Study 009)."""
import sys
from pathlib import Path

STUDY_DIR = str(Path(__file__).resolve().parent)
if STUDY_DIR not in sys.path:
    sys.path.insert(0, STUDY_DIR)
