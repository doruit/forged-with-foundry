"""Metadata-only evidence generation for PRI-004 outcomes."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from .models import LogDecision, LogRemediationResult

logger = logging.getLogger("pri_004.evidence")


def record_evidence(
    decision: LogDecision,
    action_taken: str,
    operation_id: str | None = None,
) -> str:
    evidence_id = str(uuid.uuid4())
    payload = {
        "evidence_id": evidence_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "control_id": decision.control_id,
        "decision_id": decision.decision_id,
        "field_name": decision.field_name,
        "action": decision.action.value,
        "pii_categories": list(decision.pii_categories),
        "action_taken": action_taken,
        "operation_id": operation_id,
        "accountable_role": "Privacy Officer",
    }
    logger.warning("PRI-004 evidence=%s metadata=%s", evidence_id, payload)
    return evidence_id


def blocked_result(decision: LogDecision, message: str) -> LogRemediationResult:
    evidence_id = record_evidence(decision, action_taken="blocked")
    return LogRemediationResult(
        decision_id=decision.decision_id,
        record_id=decision.record_id,
        status="blocked",
        operation_id=None,
        evidence_id=evidence_id,
        message=message,
    )
