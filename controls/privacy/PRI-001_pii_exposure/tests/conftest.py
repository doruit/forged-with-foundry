"""Make the self-contained control package importable from any working directory."""

import sys
from pathlib import Path


CONTROL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CONTROL_ROOT))
