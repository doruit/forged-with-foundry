"""PII escalation abstraction with a safe webhook-compatible implementation."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import UTC, datetime

import httpx

from .models import PolicyDecision

logger = logging.getLogger("pri_001.escalation")


async def escalate(decision: PolicyDecision, source_type: str) -> str:
    """Emit a metadata-only escalation event and optionally post it to a webhook."""
    event_id = str(uuid.uuid4())
    payload = {
        "event_id": event_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "control_id": decision.control_id,
        "action": decision.action.value,
        "accountable_role": decision.accountable_role,
        "source_type": source_type,
        "pii_count": decision.pii_count,
        "categories": list(decision.categories),
    }

    # Never include source text, entity values, filenames, or document contents.
    logger.warning("PRI-001 escalation event=%s metadata=%s", event_id, payload)

    webhook_url = os.getenv("PII_ESCALATION_WEBHOOK_URL", "").strip()
    if webhook_url:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(webhook_url, json=payload)
            response.raise_for_status()

    return event_id
