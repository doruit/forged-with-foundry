"""Metadata-only evidence generation for PRI-003 outcomes."""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime

from .models import DSRDecision, DSRExtensionResult

logger = logging.getLogger("pri_003.evidence")


def record_evidence(
    decision: DSRDecision,
    escalated: bool,
    extension_granted: bool,
) -> str:
    evidence_id = str(uuid.uuid4())
    payload = {
        "evidence_id": evidence_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "control_id": decision.control_id,
        "decision_id": decision.decision_id,
        "request_reference": hashlib.sha256(decision.request_id.encode()).hexdigest(),
        "request_type": decision.request_type,
        "action": decision.action.value,
        "due_date": decision.due_date.isoformat() if decision.due_date else None,
        "days_until_due": decision.days_until_due,
        "resolved": decision.resolved,
        "escalated": escalated,
        "extension_granted": extension_granted,
        "accountable_role": "DPO",
    }
    logger.warning("PRI-003 evidence=%s metadata=%s", evidence_id, payload)
    return evidence_id


def blocked_result(decision: DSRDecision, message: str) -> DSRExtensionResult:
    evidence_id = record_evidence(decision, escalated=False, extension_granted=False)
    return DSRExtensionResult(
        decision_id=decision.decision_id,
        request_id=decision.request_id,
        status="blocked",
        extension_granted=False,
        evidence_id=evidence_id,
        message=message,
    )
