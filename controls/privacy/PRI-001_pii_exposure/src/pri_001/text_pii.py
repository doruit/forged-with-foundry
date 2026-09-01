"""Azure AI Language Text PII enforcement for chat and plain text."""

from __future__ import annotations

import os

from azure.ai.textanalytics.aio import TextAnalyticsClient
from azure.identity.aio import AzureCliCredential

from .models import PiiFinding, TextEnforcementResult
from .policy import evaluate_pii_policy


class PiiEnforcementError(RuntimeError):
    """Raised when content cannot be governed; callers must fail closed."""


async def enforce_text_pii(text: str, language: str = "en") -> TextEnforcementResult:
    """Detect and redact PII before text crosses into the agent boundary."""
    endpoint = os.environ["AZURE_LANGUAGE_ENDPOINT"]
    if not text.strip():
        return TextEnforcementResult(
            decision=evaluate_pii_policy(()),
            redacted_text="",
        )

    try:
        async with AzureCliCredential() as credential:
            async with TextAnalyticsClient(endpoint, credential=credential) as client:
                response = await client.recognize_pii_entities(
                    documents=[text],
                    language=language,
                )
    except Exception as exc:
        raise PiiEnforcementError("Text PII service unavailable; input blocked.") from exc

    document = response[0]
    if document.is_error:
        raise PiiEnforcementError(
            f"Text PII analysis failed ({document.error.code}); input blocked."
        )

    findings = tuple(
        PiiFinding(
            category=entity.category,
            confidence=round(entity.confidence_score, 3),
        )
        for entity in document.entities
    )
    return TextEnforcementResult(
        decision=evaluate_pii_policy(findings),
        redacted_text=document.redacted_text,
        findings=findings,
    )
