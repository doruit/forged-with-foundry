"""Read the approved repeat threshold from the validated governance contract."""

from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

from . import AGENT_ID, CONTROL_ID

REPOSITORY = Path(__file__).resolve().parents[5]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

from scripts.validate_governance_contract import (  # noqa: E402
    ContractReadError,
    parse_contract_bytes,
    read_contract_bytes,
    validate_contract,
    validate_control_entry,
)

CONTROL_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_SUFFIX = Path(".fwf") / "agents" / AGENT_ID / "governance.yaml"
DEFAULT_CONTRACT = CONTROL_ROOT / "workload" / CONTRACT_SUFFIX
MISSING_THRESHOLD_CONTRACT = CONTROL_ROOT / "fixtures" / "missing-threshold" / CONTRACT_SUFFIX


@dataclass(frozen=True)
class ThresholdDeclaration:
    status: str
    reference: str
    sha256: str | None
    threshold: int | None = None


def load_threshold(path: Path = DEFAULT_CONTRACT) -> ThresholdDeclaration:
    """Return the declaration; never raise, so ACS decides on the result."""

    reference = f".fwf/agents/{AGENT_ID}/governance.yaml"
    try:
        raw = read_contract_bytes(path)
        data = parse_contract_bytes(raw, source="RUN-006 contract")
    except (ContractReadError, OSError, ValueError):
        return ThresholdDeclaration("unreadable", reference, None)
    digest = hashlib.sha256(raw).hexdigest()
    errors = validate_contract(data, agent_dir_name=AGENT_ID)
    entry, entry_errors = validate_control_entry(CONTROL_ID, data)
    if errors or entry_errors or entry is None:
        return ThresholdDeclaration("invalid", reference, digest)
    return ThresholdDeclaration("valid", reference, digest, entry["evidence"]["repeatThreshold"])
