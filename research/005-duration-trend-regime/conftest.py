"""Put the repository root on the path so that ``src`` can import the shared
library ``qune_research`` when pytest runs from the study folder."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
