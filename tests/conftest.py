"""Test configuration for control-local Python packages."""

import sys
from pathlib import Path


PRI_001_SRC = (
    Path(__file__).resolve().parents[1]
    / "controls"
    / "privacy"
    / "PRI-001_pii_exposure"
    / "src"
)
sys.path.insert(0, str(PRI_001_SRC))
