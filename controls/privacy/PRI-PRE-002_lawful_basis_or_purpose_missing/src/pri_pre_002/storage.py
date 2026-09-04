"""Azure Table Storage adapter for the isolated PRI-PRE-002 project register."""

from __future__ import annotations

import os
from datetime import UTC, datetime

from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from azure.data.tables.aio import TableServiceClient
from azure.identity.aio import DefaultAzureCredential

from .models import GateDecision, ProjectRecord
from .policy import evaluate_lawful_basis_gate, fail_closed

PARTITION_KEY = "pripre002-demo"


class LawfulBasisStoreError(RuntimeError):
    """Raised when PRI-PRE-002 cannot safely inspect its scope."""


def _entity_to_record(entity: dict) -> ProjectRecord:
    return ProjectRecord(
        project_id=entity["RowKey"],
        environment=entity.get("Environment", "production"),
        processes_personal_data=bool(entity.get("ProcessesPersonalData", False)),
        lawful_basis_raw=entity.get("LawfulBasis", ""),
        purpose_id=entity.get("PurposeId", ""),
        etag=str(entity.metadata["etag"]),
    )


class LawfulBasisStore:
    def __init__(self) -> None:
        self.account_url = os.getenv("PRIPRE002_TABLE_ENDPOINT", "").strip().rstrip("/")
        if not self.account_url:
            raise LawfulBasisStoreError(
                "PRI-PRE-002 storage is not configured; deploy the control infrastructure."
            )
        self.table_name = os.getenv("PRIPRE002_TABLE_NAME", "pripre002projects").strip()

    def _client(self, credential: DefaultAzureCredential) -> TableServiceClient:
        return TableServiceClient(self.account_url, credential=credential)

    async def seed_scenarios(self) -> None:
        """Create four synthetic project records covering every decision outcome."""
        scenarios = [
            {
                "RowKey": "non-personal-data-analytics-dashboard",
                "Environment": "production",
                "ProcessesPersonalData": False,
                "LawfulBasis": "",
                "PurposeId": "",
            },
            {
                "RowKey": "customer-support-chatbot-basis-and-purpose-on-file",
                "Environment": "production",
                "ProcessesPersonalData": True,
                "LawfulBasis": "contract",
                "PurposeId": "PURPOSE-2026-009",
            },
            {
                "RowKey": "marketing-segmentation-tool-missing-basis",
                "Environment": "production",
                "ProcessesPersonalData": True,
                "LawfulBasis": "",
                "PurposeId": "",
            },
            {
                "RowKey": "legacy-recommendation-engine-invalid-basis",
                "Environment": "production",
                "ProcessesPersonalData": True,
                "LawfulBasis": "business_need",
                "PurposeId": "",
            },
        ]
        async with DefaultAzureCredential() as credential:
            service = self._client(credential)
            table = service.get_table_client(self.table_name)
            try:
                await service.create_table_if_not_exists(self.table_name)
                async for entity in table.query_entities(f"PartitionKey eq '{PARTITION_KEY}'"):
                    await table.delete_entity(entity["PartitionKey"], entity["RowKey"])
                for scenario in scenarios:
                    await table.create_entity({"PartitionKey": PARTITION_KEY, **scenario})
            except HttpResponseError as exc:
                raise LawfulBasisStoreError(
                    "Seeding the PRI-PRE-002 demo register failed."
                ) from exc
            finally:
                await service.close()

    async def scan(self, evaluated_at: datetime | None = None) -> list[GateDecision]:
        """List entities and evaluate deterministic lawful-basis-gate outcomes."""
        evaluated_at = (evaluated_at or datetime.now(UTC)).astimezone(UTC)
        decisions: list[GateDecision] = []
        async with DefaultAzureCredential() as credential:
            service = self._client(credential)
            table = service.get_table_client(self.table_name)
            try:
                async for entity in table.query_entities(f"PartitionKey eq '{PARTITION_KEY}'"):
                    try:
                        record = _entity_to_record(entity)
                    except (KeyError, ValueError):
                        decisions.append(
                            fail_closed(
                                entity.get("RowKey", "unknown-project"),
                                "Required project metadata is missing or invalid.",
                            )
                        )
                        continue
                    decisions.append(evaluate_lawful_basis_gate(record, evaluated_at))
            except ResourceNotFoundError as exc:
                raise LawfulBasisStoreError(
                    "PRI-PRE-002 table is missing; deploy infrastructure or seed the demo."
                ) from exc
            except HttpResponseError as exc:
                raise LawfulBasisStoreError("Scan failed; no result can be trusted.") from exc
            finally:
                await service.close()
        return decisions

    async def cleanup(self) -> None:
        """Delete only synthetic PRI-PRE-002 demo entities."""
        async with DefaultAzureCredential() as credential:
            service = self._client(credential)
            table = service.get_table_client(self.table_name)
            try:
                async for entity in table.query_entities(f"PartitionKey eq '{PARTITION_KEY}'"):
                    await table.delete_entity(entity["PartitionKey"], entity["RowKey"])
            except ResourceNotFoundError:
                return
            finally:
                await service.close()
