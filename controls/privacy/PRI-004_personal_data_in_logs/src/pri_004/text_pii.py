"""Azure AI Language Text PII detection for PRI-004 log scanning and mask previews."""

from __future__ import annotations

import os

from azure.ai.textanalytics.aio import TextAnalyticsClient
from azure.identity.aio import AzureCliCredential

from .models import PiiScanResult


class PiiDetectionError(RuntimeError):
    """Raised when PII detection cannot complete; callers must fail closed (BLOCKED)."""


async def scan_message(message: str, language: str = "en") -> PiiScanResult:
    """Detect PII categories and produce a redacted preview in a single API call."""
    endpoint = os.environ["AZURE_LANGUAGE_ENDPOINT"]
    if not message.strip():
        return PiiScanResult(categories=(), redacted_text=message)

    try:
        async with AzureCliCredential() as credential:
            async with TextAnalyticsClient(endpoint, credential=credential) as client:
                response = await client.recognize_pii_entities(
                    documents=[message],
                    language=language,
                )
    except Exception as exc:
        raise PiiDetectionError("Text PII service unavailable; record blocked.") from exc

    document = response[0]
    if document.is_error:
        raise PiiDetectionError(
            f"Text PII analysis failed ({document.error.code}); record blocked."
        )

    categories = tuple(sorted({entity.category for entity in document.entities}))
    return PiiScanResult(categories=categories, redacted_text=document.redacted_text)
