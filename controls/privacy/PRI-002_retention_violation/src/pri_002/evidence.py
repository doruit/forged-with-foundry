"""Metadata-only evidence generation for PRI-002 outcomes."""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime

from .models import RemediationResult, RetentionDecision

logger = logging.getLogger("pri_002.evidence")


def record_evidence(
    decision: RetentionDecision,
    status: str,
    verified_absent: bool,
    human_approved: bool,
) -> str:
    evidence_id = str(uuid.uuid4())
    payload = {
        "evidence_id": evidence_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "control_id": decision.control_id,
        "decision_id": decision.decision_id,
        "record_reference": hashlib.sha256(decision.record_id.encode()).hexdigest(),
        "retention_class": decision.retention_class,
        "age_days": decision.age_days,
        "retention_days": decision.retention_days,
        "grace_days": decision.grace_days,
        "lifecycle_covered": decision.lifecycle_covered,
        "decision": decision.action.value,
        "human_approved": human_approved,
        "remediation_status": status,
        "verified_absent": verified_absent,
        "accountable_role": "Privacy Officer",
    }
    logger.warning("PRI-002 evidence=%s metadata=%s", evidence_id, payload)
    return evidence_id


def blocked_result(decision: RetentionDecision, message: str) -> RemediationResult:
    evidence_id = record_evidence(decision, "blocked", False, False)
    return RemediationResult(
        decision_id=decision.decision_id,
        record_id=decision.record_id,
        status="blocked",
        verified_absent=False,
        evidence_id=evidence_id,
        message=message,
    )
