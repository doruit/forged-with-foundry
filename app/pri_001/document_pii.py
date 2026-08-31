"""Native Azure AI Language Document PII enforcement.

PDF, DOCX, and TXT files are sent through Microsoft's asynchronous native-file
pipeline. This module intentionally performs no PDF/DOCX text extraction and no
document reconstruction.
"""

from __future__ import annotations

import asyncio
import json
import mimetypes
import os
import uuid
from pathlib import Path
from typing import Any

import httpx
from azure.storage.blob import ContentSettings
from azure.identity.aio import AzureCliCredential
from azure.storage.blob.aio import BlobClient, BlobServiceClient

from .models import DocumentEnforcementResult, PiiFinding
from .policy import evaluate_pii_policy
from .text_pii import PiiEnforcementError

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024


def _safe_blob_name(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return f"{uuid.uuid4()}/source{suffix}"


def _collect_findings(node: Any) -> tuple[PiiFinding, ...]:
    findings: list[PiiFinding] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            category = value.get("category")
            if isinstance(category, str):
                confidence = value.get("confidenceScore")
                findings.append(
                    PiiFinding(
                        category=category,
                        confidence=round(float(confidence), 3)
                        if isinstance(confidence, (int, float))
                        else None,
                    )
                )
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(node)
    return tuple(findings)


def _target_locations(status: dict[str, Any]) -> list[str]:
    locations: list[str] = []
    for task in status.get("tasks", {}).get("items", []):
        for document in task.get("results", {}).get("documents", []):
            for target in document.get("targets", []):
                location = target.get("location")
                if isinstance(location, str):
                    locations.append(location)
    return locations


def _error_codes(status: dict[str, Any]) -> tuple[str, ...]:
    """Collect service error codes without exposing content, values, or URLs."""
    codes: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            code = value.get("code")
            if isinstance(code, str) and code:
                codes.add(code)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(status.get("errors", []))
    walk(status.get("tasks", {}))
    return tuple(sorted(codes))


async def _download_blob(url: str, credential: AzureCliCredential) -> bytes:
    blob = BlobClient.from_blob_url(url, credential=credential)
    async with blob:
        stream = await blob.download_blob()
        return await stream.readall()


async def enforce_document_pii(
    filename: str,
    content: bytes,
    language: str = "en",
) -> DocumentEnforcementResult:
    """Upload, natively redact, inspect structured results, and return output."""
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise PiiEnforcementError("Only PDF, DOCX, and TXT uploads are supported.")
    if not content or len(content) > MAX_DOCUMENT_BYTES:
        raise PiiEnforcementError("Document must be non-empty and no larger than 10 MB.")

    language_endpoint = os.environ["AZURE_LANGUAGE_ENDPOINT"].rstrip("/")
    blob_endpoint = os.environ["PII_STORAGE_BLOB_ENDPOINT"].rstrip("/")
    source_container = os.getenv("PII_SOURCE_CONTAINER", "pii-source")
    target_container = os.getenv("PII_TARGET_CONTAINER", "pii-redacted")
    api_version = os.getenv("PII_DOCUMENT_API_VERSION", "2026-05-01")
    poll_seconds = max(float(os.getenv("PII_DOCUMENT_POLL_SECONDS", "2")), 1.0)
    timeout_seconds = float(os.getenv("PII_DOCUMENT_TIMEOUT_SECONDS", "120"))
    blob_name = _safe_blob_name(filename)
    source_url = f"{blob_endpoint}/{source_container}/{blob_name}"
    target_url = f"{blob_endpoint}/{target_container}"

    async with AzureCliCredential() as credential:
        storage = BlobServiceClient(account_url=blob_endpoint, credential=credential)
        source_blob = storage.get_blob_client(source_container, blob_name)
        try:
            await source_blob.upload_blob(
                content,
                overwrite=False,
                content_settings=ContentSettings(
                    content_type=mimetypes.guess_type(filename)[0]
                    or "application/octet-stream"
                ),
            )

            token = await credential.get_token(
                "https://cognitiveservices.azure.com/.default"
            )
            headers = {
                "Authorization": f"Bearer {token.token}",
                "Content-Type": "application/json",
            }
            request = {
                "displayName": "PRI-001 native document redaction",
                "analysisInput": {
                    "documents": [
                        {
                            "id": "1",
                            "language": language,
                            "source": {"kind": "AzureBlob", "location": source_url},
                            "target": {
                                "kind": "AzureContainer",
                                "location": target_url,
                            },
                        }
                    ]
                },
                "tasks": [
                    {
                        "kind": "PiiEntityRecognition",
                        "taskName": "PRI-001 deterministic PII detection",
                        "parameters": {
                            "loggingOptOut": True,
                            "modelVersion": "latest",
                            "stringIndexType": "UnicodeCodePoint",
                            "redactionPolicies": [
                                {
                                    "policyKind": "characterMask",
                                    "isDefault": True,
                                    "redactionCharacter": "*",
                                }
                            ],
                        },
                    }
                ],
            }

            submit_url = (
                f"{language_endpoint}/language/analyze-documents/jobs"
                f"?api-version={api_version}"
            )
            async with httpx.AsyncClient(timeout=30) as http:
                response = await http.post(submit_url, headers=headers, json=request)
                response.raise_for_status()
                operation_url = response.headers.get("Operation-Location")
                if not operation_url:
                    raise PiiEnforcementError(
                        "Document PII did not return an operation location."
                    )

                deadline = asyncio.get_running_loop().time() + timeout_seconds
                while True:
                    if asyncio.get_running_loop().time() >= deadline:
                        raise PiiEnforcementError(
                            "Document PII timed out; document blocked."
                        )
                    await asyncio.sleep(poll_seconds)
                    poll = await http.get(operation_url, headers=headers)
                    poll.raise_for_status()
                    status = poll.json()
                    state = str(status.get("status", "")).lower()
                    if state == "succeeded":
                        break
                    if state in {"failed", "cancelled"}:
                        error_codes = _error_codes(status)
                        code_suffix = (
                            f" Service codes: {', '.join(error_codes)}."
                            if error_codes
                            else ""
                        )
                        raise PiiEnforcementError(
                            f"Document PII ended with status '{state}'; document blocked."
                            f"{code_suffix}"
                        )

            locations = _target_locations(status)
            result_url = next(
                (url for url in locations if url.lower().endswith(".result.json")),
                None,
            )
            redacted_url = next(
                (url for url in locations if url.lower().endswith(suffix)),
                None,
            )
            if not result_url or not redacted_url:
                raise PiiEnforcementError(
                    "Document PII output artifacts were incomplete; document blocked."
                )

            result_bytes = await _download_blob(result_url, credential)
            structured_result = json.loads(result_bytes)
            findings = _collect_findings(structured_result)
            redacted_bytes = await _download_blob(redacted_url, credential)

            # The UI receives the Microsoft-generated artifact in memory. Remove
            # both target artifacts after download to minimize PII retention.
            for target_url in (result_url, redacted_url):
                target_blob = BlobClient.from_blob_url(target_url, credential=credential)
                async with target_blob:
                    await target_blob.delete_blob(delete_snapshots="include")

            # Uploaded filenames can contain PII, so expose only a generic name.
            redacted_name = f"redacted-document{suffix}"
            safe_text = (
                redacted_bytes.decode("utf-8", errors="replace")
                if suffix == ".txt"
                else None
            )

            return DocumentEnforcementResult(
                decision=evaluate_pii_policy(findings),
                redacted_name=redacted_name,
                redacted_bytes=redacted_bytes,
                findings=findings,
                safe_text_for_agent=safe_text,
            )
        except PiiEnforcementError:
            raise
        except Exception as exc:
            raise PiiEnforcementError(
                "Native Document PII failed; original document was blocked."
            ) from exc
        finally:
            try:
                await source_blob.delete_blob(delete_snapshots="include")
            except Exception:
                pass
            await storage.close()
