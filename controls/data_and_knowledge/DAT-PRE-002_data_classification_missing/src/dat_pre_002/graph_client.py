"""Microsoft Graph adapter: read and guarded-assign real Purview sensitivity labels.

Uses delegated, least-privilege Microsoft Graph permissions (Files.ReadWrite.All,
User.Read) against the signed-in demo user's own OneDrive. No Azure resource is
owned by this control; the only external dependency is Microsoft Graph itself.
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime

import httpx
from azure.identity.aio import DeviceCodeCredential

from .evidence import blocked_result, record_evidence
from .models import ClassificationAction, ClassificationDecision, ClassifyResult, DemoFile
from .policy import evaluate_classification, evaluate_classify_request, infer_content_category

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPES = ("https://graph.microsoft.com/Files.ReadWrite.All", "https://graph.microsoft.com/User.Read")
DEMO_FOLDER_NAME = "DAT-PRE-002-demo"
FILE_PREFIX = "datpre002-demo-"
# Demo-only sentinel; simulates an extraction failure (e.g. a locked or double-key
# encrypted file) without depending on a real, reliably reproducible Graph error.
BLOCKED_SENTINEL_NAME = f"{FILE_PREFIX}blocked-simulated-extraction-failure.txt"
SEED_FILES = {
    f"{FILE_PREFIX}confidential-customer-record.txt": "This is synthetic demo content only.",
    f"{FILE_PREFIX}public-faq-draft.txt": "This is synthetic demo content only.",
    BLOCKED_SENTINEL_NAME: "This is synthetic demo content only.",
}
POLL_ATTEMPTS = 6
POLL_INTERVAL_SECONDS = 2.0


class GraphControlError(RuntimeError):
    """Raised when DAT-PRE-002 cannot safely read or assign a sensitivity label."""


class SensitivityLabelStore:
    def __init__(self) -> None:
        client_id = os.getenv("DAT_PRE_002_ENTRA_CLIENT_ID", "").strip()
        tenant_id = os.getenv("DAT_PRE_002_ENTRA_TENANT_ID", "").strip() or "organizations"
        self.confidential_label_id = os.getenv("DAT_PRE_002_CONFIDENTIAL_LABEL_ID", "").strip()
        self.public_label_id = os.getenv("DAT_PRE_002_PUBLIC_LABEL_ID", "").strip()
        if not client_id or not self.confidential_label_id or not self.public_label_id:
            raise GraphControlError(
                "DAT-PRE-002 is not configured; copy .env.example, register the Entra app, "
                "and set the two published sensitivity label IDs."
            )
        self._credential = DeviceCodeCredential(client_id=client_id, tenant_id=tenant_id)
        self._client = httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30.0)
        self._folder_id: str | None = None

    async def aclose(self) -> None:
        await self._client.aclose()
        await self._credential.close()

    async def _headers(self) -> dict[str, str]:
        token = await self._credential.get_token(*GRAPH_SCOPES)
        return {"Authorization": f"Bearer {token.token}"}

    async def _ensure_folder(self) -> str:
        if self._folder_id:
            return self._folder_id
        headers = await self._headers()
        response = await self._client.get(
            f"/me/drive/root:/{DEMO_FOLDER_NAME}", headers=headers
        )
        if response.status_code == 200:
            self._folder_id = response.json()["id"]
            return self._folder_id
        if response.status_code != 404:
            raise GraphControlError(
                f"Could not look up the DAT-PRE-002 demo folder (HTTP {response.status_code})."
            )
        create = await self._client.post(
            "/me/drive/root/children",
            headers=headers,
            json={
                "name": DEMO_FOLDER_NAME,
                "folder": {},
                "@microsoft.graph.conflictBehavior": "fail",
            },
        )
        if create.status_code not in (200, 201):
            raise GraphControlError(
                f"Could not create the DAT-PRE-002 demo folder (HTTP {create.status_code})."
            )
        self._folder_id = create.json()["id"]
        return self._folder_id

    async def _extract_label_ids(self, item_id: str) -> tuple[str, ...]:
        headers = await self._headers()
        response = await self._client.post(
            f"/me/drive/items/{item_id}/extractSensitivityLabels", headers=headers
        )
        if response.status_code != 200:
            raise GraphControlError(
                f"Sensitivity-label extraction failed for item {item_id} "
                f"(HTTP {response.status_code})."
            )
        labels = response.json().get("value", {}).get("labels", [])
        return tuple(label["sensitivityLabelId"] for label in labels)

    async def _assign_label(self, item_id: str, label_id: str, justification: str) -> str | None:
        headers = await self._headers()
        response = await self._client.post(
            f"/me/drive/items/{item_id}/assignSensitivityLabel",
            headers=headers,
            json={
                "sensitivityLabelId": label_id,
                "assignmentMethod": "standard",
                "justificationText": justification,
            },
        )
        if response.status_code != 202:
            raise GraphControlError(
                f"assignSensitivityLabel was refused for item {item_id} "
                f"(HTTP {response.status_code})."
            )
        return response.headers.get("Location")

    async def _wait_for_operation(self, location: str | None) -> bool:
        """Best-effort poll of the Graph long-running-operation Location URL.

        Returns True only if the operation reported "succeeded" within the poll
        window. A False result never blocks the mandatory re-verification step
        that follows — it only means completion could not be confirmed quickly.
        """
        if not location:
            return False
        async with httpx.AsyncClient(timeout=15.0) as monitor_client:
            for _ in range(POLL_ATTEMPTS):
                try:
                    response = await monitor_client.get(location)
                except httpx.HTTPError:
                    return False
                if response.status_code == 200:
                    status = response.json().get("status")
                    if status == "succeeded":
                        return True
                    if status == "failed":
                        return False
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
        return False

    async def seed_scenarios(self) -> None:
        """Create three synthetic files; the public-category file starts pre-classified."""
        folder_id = await self._ensure_folder()
        headers = await self._headers()
        item_ids: dict[str, str] = {}
        for name, content in SEED_FILES.items():
            response = await self._client.put(
                f"/me/drive/items/{folder_id}:/{name}:/content",
                headers=headers,
                content=content.encode("utf-8"),
            )
            if response.status_code not in (200, 201):
                raise GraphControlError(
                    f"Could not seed synthetic file '{name}' (HTTP {response.status_code})."
                )
            item_ids[name] = response.json()["id"]

        # Pre-classify the public-category file so the scan can show a COMPLIANT baseline.
        public_name = next(n for n in SEED_FILES if "public" in n)
        location = await self._assign_label(
            item_ids[public_name], self.public_label_id, "DAT-PRE-002 seed baseline"
        )
        await self._wait_for_operation(location)

    async def scan(self) -> list[ClassificationDecision]:
        folder_id = await self._ensure_folder()
        headers = await self._headers()
        response = await self._client.get(
            f"/me/drive/items/{folder_id}/children", headers=headers
        )
        if response.status_code != 200:
            raise GraphControlError(
                f"Could not list the DAT-PRE-002 demo folder (HTTP {response.status_code})."
            )
        items = [
            item for item in response.json().get("value", []) if item["name"].startswith(FILE_PREFIX)
        ]
        if not items:
            return []

        evaluated_at = datetime.now(UTC)
        decisions: list[ClassificationDecision] = []
        for item in items:
            name = item["name"]
            item_id = item["id"]
            is_sentinel = name == BLOCKED_SENTINEL_NAME
            file = DemoFile(
                name=name,
                item_id=item_id,
                content_category=infer_content_category(name),
                extraction_failed=is_sentinel,
            )
            if is_sentinel:
                decisions.append(
                    evaluate_classification(
                        file, None, self.confidential_label_id, self.public_label_id, evaluated_at
                    )
                )
                continue
            try:
                label_ids = await self._extract_label_ids(item_id)
            except GraphControlError:
                file = DemoFile(
                    name=name, item_id=item_id, content_category=file.content_category, extraction_failed=True
                )
                decisions.append(
                    evaluate_classification(
                        file, None, self.confidential_label_id, self.public_label_id, evaluated_at
                    )
                )
                continue
            decisions.append(
                evaluate_classification(
                    file, label_ids, self.confidential_label_id, self.public_label_id, evaluated_at
                )
            )
        return decisions

    async def classify(self, decision: ClassificationDecision) -> ClassifyResult:
        """Guarded classify action: re-check state, assign the label, poll, then re-verify."""
        if decision.action is not ClassificationAction.FLAGGED or decision.required_label_id is None:
            return blocked_result(decision, "Only flagged files are eligible for a classify action.")

        current_label_ids = await self._extract_label_ids(decision.item_id)
        allowed, reason = evaluate_classify_request(decision, current_label_ids)
        if not allowed:
            return blocked_result(decision, reason)

        location = await self._assign_label(
            decision.item_id,
            decision.required_label_id,
            "DAT-PRE-002 guided classification demo",
        )
        await self._wait_for_operation(location)

        # Authoritative re-verification: never trust the 202 response alone.
        final_label_ids = await self._extract_label_ids(decision.item_id)
        resolved = decision.required_label_id in final_label_ids
        evidence_id = record_evidence(
            decision,
            action_taken="classified" if resolved else "classify_pending",
            operation_id=location,
        )
        return ClassifyResult(
            decision_id=decision.decision_id,
            item_id=decision.item_id,
            status="resolved" if resolved else "pending",
            operation_id=location,
            evidence_id=evidence_id,
            message=(
                "The required sensitivity label is now confirmed on the file."
                if resolved
                else (
                    "The classify request was accepted but is not yet confirmed. Purview label "
                    "assignment is asynchronous; rescan shortly to re-verify."
                )
            ),
        )

    async def cleanup(self) -> int:
        """Delete only files and the folder created by this demo; returns items removed."""
        headers = await self._headers()
        response = await self._client.get(f"/me/drive/root:/{DEMO_FOLDER_NAME}", headers=headers)
        if response.status_code == 404:
            return 0
        if response.status_code != 200:
            raise GraphControlError(
                f"Could not look up the DAT-PRE-002 demo folder for cleanup "
                f"(HTTP {response.status_code})."
            )
        folder_id = response.json()["id"]
        delete = await self._client.delete(f"/me/drive/items/{folder_id}", headers=headers)
        if delete.status_code not in (204, 404):
            raise GraphControlError(
                f"Could not delete the DAT-PRE-002 demo folder (HTTP {delete.status_code})."
            )
        self._folder_id = None
        return 1
