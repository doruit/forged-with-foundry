"""Read the approved tool-call budget from the validated governance contract."""

from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass, field
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

DEFAULT_CONTRACT = (
    Path(__file__).resolve().parents[2] / "workload" / ".fwf" / "agents" / AGENT_ID / "governance.yaml"
)


@dataclass(frozen=True)
class BudgetDeclaration:
    status: str
    reference: str
    sha256: str | None
    budgets: dict[str, int] = field(default_factory=dict)

    def budget_for(self, task_type: str) -> int | None:
        return self.budgets.get(task_type)


def load_budgets(path: Path = DEFAULT_CONTRACT) -> BudgetDeclaration:
    """Return the declaration; never raise, so ACS decides on the result.

    `status` is `valid` only when the shared validator accepts the contract and
    the TOOL-003 entry, and task types are unique.
    """

    reference = f".fwf/agents/{AGENT_ID}/governance.yaml"
    try:
        raw = read_contract_bytes(path)
        data = parse_contract_bytes(raw, source="TOOL-003 contract")
    except (ContractReadError, OSError, ValueError):
        return BudgetDeclaration("unreadable", reference, None)
    digest = hashlib.sha256(raw).hexdigest()
    errors = validate_contract(data, agent_dir_name=AGENT_ID)
    entry, entry_errors = validate_control_entry(CONTROL_ID, data)
    if errors or entry_errors or entry is None:
        return BudgetDeclaration("invalid", reference, digest)
    budgets: dict[str, int] = {}
    for item in entry["evidence"]["taskBudgets"]:
        if item["taskType"] in budgets:
            return BudgetDeclaration("invalid", reference, digest)
        budgets[item["taskType"]] = item["maxToolCalls"]
    return BudgetDeclaration("valid", reference, digest, budgets)
