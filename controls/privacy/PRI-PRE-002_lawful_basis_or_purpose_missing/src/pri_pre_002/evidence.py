"""Metadata-only evidence generation for PRI-PRE-002 outcomes."""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime

from .models import GateDecision

logger = logging.getLogger("pri_pre_002.evidence")


def record_evidence(decision: GateDecision) -> str:
    evidence_id = str(uuid.uuid4())
    payload = {
        "evidence_id": evidence_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "control_id": decision.control_id,
        "decision_id": decision.decision_id,
        "project_reference": hashlib.sha256(decision.project_id.encode()).hexdigest(),
        "action": decision.action.value,
        "processes_personal_data": decision.processes_personal_data,
        "lawful_basis_valid": decision.lawful_basis_valid,
        "purpose_documented": decision.purpose_documented,
        "accountable_role": "Privacy Officer",
    }
    logger.warning("PRI-PRE-002 evidence=%s metadata=%s", evidence_id, payload)
    return evidence_id
