"""Metadata-only evidence generation for DAT-PRE-002 outcomes."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from .models import ClassificationDecision, ClassifyResult

logger = logging.getLogger("dat_pre_002.evidence")


def record_evidence(
    decision: ClassificationDecision,
    action_taken: str,
    operation_id: str | None = None,
) -> str:
    evidence_id = str(uuid.uuid4())
    payload = {
        "evidence_id": evidence_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "control_id": decision.control_id,
        "decision_id": decision.decision_id,
        "file_name": decision.file_name,
        "content_category": decision.content_category,
        "action": decision.action.value,
        "action_taken": action_taken,
        "required_label_id": decision.required_label_id,
        "operation_id": operation_id,
        "accountable_role": "Data Owner",
    }
    logger.warning("DAT-PRE-002 evidence=%s metadata=%s", evidence_id, payload)
    return evidence_id


def blocked_result(decision: ClassificationDecision, message: str) -> ClassifyResult:
    evidence_id = record_evidence(decision, action_taken="blocked")
    return ClassifyResult(
        decision_id=decision.decision_id,
        item_id=decision.item_id,
        status="blocked",
        operation_id=None,
        evidence_id=evidence_id,
        message=message,
    )
