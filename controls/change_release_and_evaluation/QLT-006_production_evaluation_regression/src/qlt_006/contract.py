"""Read the QA Lead's regression threshold from the validated governance contract."""

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

CONTROL_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = CONTROL_DIR / "workload" / ".fwf" / "agents" / AGENT_ID / "governance.yaml"


@dataclass(frozen=True)
class Declaration:
    status: str  # valid | invalid | unreadable
    sha256: str | None = None
    baseline_record: Path | None = None
    threshold_pp: float = 0.0
    min_scored_items: int = 0
    issue_repository: str = ""


def load(path: Path = DEFAULT_CONTRACT) -> Declaration:
    try:
        raw = read_contract_bytes(path)
        data = parse_contract_bytes(raw, source=f"{CONTROL_ID} contract")
    except (ContractReadError, OSError, ValueError):
        return Declaration("unreadable")
    digest = hashlib.sha256(raw).hexdigest()
    if validate_contract(data, agent_dir_name=AGENT_ID):
        return Declaration("invalid", digest)
    entry, errors = validate_control_entry(CONTROL_ID, data)
    if entry is None or errors:
        return Declaration("invalid", digest)
    evidence = entry["evidence"]
    return Declaration(
        "valid",
        digest,
        (CONTROL_DIR / evidence["baselineRecordPath"]).resolve(),
        float(evidence["regressionThresholdPp"]),
        int(evidence["minScoredItems"]),
        evidence["issueRepository"],
    )
