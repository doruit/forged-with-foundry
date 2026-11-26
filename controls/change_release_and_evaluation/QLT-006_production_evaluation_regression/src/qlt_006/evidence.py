"""Minimized QLT-006 evidence: versions, rates, deltas, decision; never prompts or answers."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from . import ACCOUNTABLE_ROLE, CONTROL_ID, POLICY_VERSION

EVIDENCE_DIR = Path(__file__).resolve().parents[2] / "evidence"


def envelope(body: dict) -> dict:
    return {
        "control_id": CONTROL_ID,
        "policy_version": POLICY_VERSION,
        "kind": "production_regression_check",
        "timestamp": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "correlation_id": str(uuid.uuid4()),
        "accountable_role": ACCOUNTABLE_ROLE,
        **body,
    }


def write(record: dict, directory: Path = EVIDENCE_DIR) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"check-{record['correlation_id']}.json"
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return path
