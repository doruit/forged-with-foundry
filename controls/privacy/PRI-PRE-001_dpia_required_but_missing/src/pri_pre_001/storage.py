"""Azure Table Storage adapter for the isolated PRI-PRE-001 project register."""

from __future__ import annotations

import os
from datetime import UTC, datetime

from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from azure.data.tables.aio import TableServiceClient
from azure.identity.aio import DefaultAzureCredential

from .models import GateDecision, ProjectRecord, RiskFactor
from .policy import evaluate_dpia_gate, fail_closed

PARTITION_KEY = "pripre001-demo"


class DpiaGateStoreError(RuntimeError):
    """Raised when PRI-PRE-001 cannot safely inspect its scope."""


def _entity_to_record(entity: dict) -> ProjectRecord:
    raw_factors = entity.get("RiskFactors", "UNKNOWN")
    if raw_factors == "UNKNOWN":
        risk_factors: tuple[RiskFactor, ...] | None = None
    elif raw_factors:
        risk_factors = tuple(RiskFactor(value) for value in raw_factors.split(","))
    else:
        risk_factors = ()
    return ProjectRecord(
        project_id=entity["RowKey"],
        environment=entity.get("Environment", "production"),
        risk_factors=risk_factors,
        dpia_required_declared=bool(entity.get("DpiaRequiredDeclared", False)),
        requestor_email=entity.get("RequestorEmail", ""),
        dpia_approver=entity.get("DpiaApprover", ""),
        dpia_case_id=entity.get("DpiaCaseId", ""),
        etag=str(entity.metadata["etag"]),
        go_live_requested=bool(entity.get("GoLiveRequested", False)),
    )


class DpiaGateStore:
    def __init__(self) -> None:
        self.account_url = os.getenv("PRIPRE001_TABLE_ENDPOINT", "").strip().rstrip("/")
        if not self.account_url:
            raise DpiaGateStoreError(
                "PRI-PRE-001 storage is not configured; deploy the control infrastructure."
            )
        self.table_name = os.getenv("PRIPRE001_TABLE_NAME", "pripre001projects").strip()

    def _client(self, credential: DefaultAzureCredential) -> TableServiceClient:
        return TableServiceClient(self.account_url, credential=credential)

    async def seed_scenarios(self) -> None:
        """Create five synthetic project records covering every decision outcome."""
        scenarios = [
            {
                "RowKey": "low-risk-marketing-chatbot",
                "Environment": "production",
                "RiskFactors": "",
                "DpiaRequiredDeclared": False,
                "RequestorEmail": "",
                "DpiaApprover": "",
                "DpiaCaseId": "",
            },
            {
                "RowKey": "high-risk-hiring-screener",
                "Environment": "production",
                "RiskFactors": (
                    f"{RiskFactor.AUTOMATED_DECISION_MAKING.value},"
                    f"{RiskFactor.VULNERABLE_SUBJECTS.value}"
                ),
                "DpiaRequiredDeclared": False,
                "RequestorEmail": "workload-owner@example.com",
                "DpiaApprover": "dpo@example.com",
                "DpiaCaseId": "DPIA-2026-014",
            },
            {
                "RowKey": "high-risk-fraud-detection",
                "Environment": "production",
                "RiskFactors": (
                    f"{RiskFactor.AUTOMATED_DECISION_MAKING.value},"
                    f"{RiskFactor.LARGE_SCALE_MONITORING.value}"
                ),
                "DpiaRequiredDeclared": False,
                "RequestorEmail": "",
                "DpiaApprover": "",
                "DpiaCaseId": "",
            },
            {
                "RowKey": "unknown-risk-legacy-system",
                "Environment": "production",
                "RiskFactors": "UNKNOWN",
                "DpiaRequiredDeclared": False,
                "RequestorEmail": "",
                "DpiaApprover": "",
                "DpiaCaseId": "",
            },
            {
                "RowKey": "high-risk-internal-tool-declared-not-required",
                "Environment": "production",
                "RiskFactors": (
                    f"{RiskFactor.AUTOMATED_DECISION_MAKING.value},"
                    f"{RiskFactor.LARGE_SCALE_MONITORING.value}"
                ),
                "DpiaRequiredDeclared": True,
                "RequestorEmail": "",
                "DpiaApprover": "",
                "DpiaCaseId": "",
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
                    await table.create_entity(
                        {
                            "PartitionKey": PARTITION_KEY,
                            "GoLiveRequested": False,
                            **scenario,
                        }
                    )
            except HttpResponseError as exc:
                raise DpiaGateStoreError("Seeding the PRI-PRE-001 demo register failed.") from exc
            finally:
                await service.close()

    async def scan(self, evaluated_at: datetime | None = None) -> list[GateDecision]:
        """List entities and evaluate deterministic DPIA-gate outcomes."""
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
                    decisions.append(evaluate_dpia_gate(record, evaluated_at))
            except ResourceNotFoundError as exc:
                raise DpiaGateStoreError(
                    "PRI-PRE-001 table is missing; deploy infrastructure or seed the demo."
                ) from exc
            except HttpResponseError as exc:
                raise DpiaGateStoreError("Scan failed; no go-live attempt is allowed.") from exc
            finally:
                await service.close()
        return decisions

    async def get_record(self, project_id: str) -> ProjectRecord:
        async with DefaultAzureCredential() as credential:
            service = self._client(credential)
            table = service.get_table_client(self.table_name)
            try:
                entity = await table.get_entity(PARTITION_KEY, project_id)
                return _entity_to_record(entity)
            except ResourceNotFoundError as exc:
                raise DpiaGateStoreError("The project record no longer exists.") from exc
            finally:
                await service.close()

    async def cleanup(self) -> None:
        """Delete only synthetic PRI-PRE-001 demo entities."""
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
