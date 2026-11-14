"""Minimized AUT-004 evidence: decisions, switch reads and timestamps; no prompts or model text."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import ACCOUNTABLE_ROLE, CONTROL_ID, POLICY_VERSION


def write_evidence(directory: Path, kind: str, body: dict[str, Any], *, scope: dict[str, str], actor_reference: str | None) -> Path:
    record = {
        "control_id": CONTROL_ID,
        "policy_version": POLICY_VERSION,
        "kind": kind,
        "timestamp": datetime.now(UTC).isoformat(),
        "correlation_id": str(uuid.uuid4()),
        "scope": scope,
        "requested_by": actor_reference,
        **body,
        "accountable_role": ACCOUNTABLE_ROLE,
    }
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{record['timestamp'][:19].replace(':', '')}-{kind}-{record['correlation_id'][:8]}.json"
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return path
