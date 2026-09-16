"""Make both the core PRI-001 package and this CR-001 extension importable."""

import os
import sys
from pathlib import Path

_EXTENSION_ROOT = Path(__file__).resolve().parents[1]
_CONTROL_ROOT = Path(__file__).resolve().parents[3]

os.environ.setdefault("CHAINLIT_APP_ROOT", str(_CONTROL_ROOT))
sys.path.insert(0, str(_CONTROL_ROOT))
sys.path.insert(0, str(_EXTENSION_ROOT))
