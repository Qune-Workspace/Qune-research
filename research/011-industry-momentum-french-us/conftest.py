"""Make the study folder importable as the package root for pytest, so that
``from src import ...`` works (copied from Study 010)."""
import sys
from pathlib import Path

STUDY_DIR = str(Path(__file__).resolve().parent)
if STUDY_DIR not in sys.path:
    sys.path.insert(0, STUDY_DIR)

# the repository root, for the shared library (qune_research) in the tests that compare with it
ROOT = str(Path(__file__).resolve().parents[2])
if ROOT not in sys.path:
    sys.path.append(ROOT)
