"""Metadata-only evidence generation for PRI-PRE-001 outcomes."""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime

from .models import GateDecision, GoLiveAttemptResult

logger = logging.getLogger("pri_pre_001.evidence")


def record_evidence(
    decision: GateDecision,
    azure_policy_denied: bool | None,
) -> str:
    evidence_id = str(uuid.uuid4())
    payload = {
        "evidence_id": evidence_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "control_id": decision.control_id,
        "decision_id": decision.decision_id,
        "project_reference": hashlib.sha256(decision.project_id.encode()).hexdigest(),
        "action": decision.action.value,
        "risk_factor_count": decision.risk_factor_count,
        "dpia_required": decision.dpia_required,
        "evidence_complete": decision.evidence_complete,
        "azure_policy_denied": azure_policy_denied,
        "accountable_role": "DPO",
    }
    logger.warning("PRI-PRE-001 evidence=%s metadata=%s", evidence_id, payload)
    return evidence_id


def blocked_result(decision: GateDecision, message: str) -> GoLiveAttemptResult:
    evidence_id = record_evidence(decision, azure_policy_denied=None)
    return GoLiveAttemptResult(
        decision_id=decision.decision_id,
        project_id=decision.project_id,
        status="blocked",
        azure_policy_denied=None,
        evidence_id=evidence_id,
        message=message,
    )
