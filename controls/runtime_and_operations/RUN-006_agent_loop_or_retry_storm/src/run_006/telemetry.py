"""Export ACS's own decision metrics to Application Insights with Entra authentication.

ACS's `OtelMetricsTelemetrySink` emits `acs_intervention_<decision>_total`
counters with `policy_id`, `reason_code` and `intervention_point` dimensions.
The Azure Monitor alert for RUN-006 queries those counters; this module adds
no metric or log of its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent_control_specification import OtelMetricsTelemetrySink


def _recording_exporter(connection_string: str, credential: Any) -> Any:
    from azure.monitor.opentelemetry.exporter import AzureMonitorMetricExporter
    from opentelemetry.sdk.metrics.export import MetricExportResult

    class RecordingExporter(AzureMonitorMetricExporter):
        """Remember each export result: the SDK's force_flush always reports True."""

        results: list[Any]

        def export(self, metrics_data, timeout_millis: float = 10_000, **kwargs):  # type: ignore[override]
            try:
                result = super().export(metrics_data, timeout_millis=timeout_millis, **kwargs)
            except Exception:  # noqa: BLE001
                result = MetricExportResult.FAILURE
            self.results.append(result)
            return result

    exporter = RecordingExporter(
        connection_string=connection_string, credential=credential, enable_local_storage=False
    )
    exporter.results = []
    return exporter


@dataclass
class TelemetryExport:
    sink: Any
    provider: Any | None
    exporter: Any | None = None

    def flush(self) -> str:
        """Push metrics before the short-lived runner exits; never raise.

        Returns `exported` only when the final export reported success,
        `not_confirmed` when no successful export can be shown, and
        `not_configured` when no notification path is deployed.
        """
        if self.provider is None:
            return "not_configured"
        try:
            self.provider.force_flush(timeout_millis=30_000)
            self.provider.shutdown()
        except Exception:  # noqa: BLE001 - notification must not change the inline stop
            return "not_confirmed"
        from opentelemetry.sdk.metrics.export import MetricExportResult

        results = getattr(self.exporter, "results", [])
        return "exported" if results and results[-1] == MetricExportResult.SUCCESS else "not_confirmed"


def telemetry_export(connection_string: str | None) -> TelemetryExport:
    if not connection_string:
        return TelemetryExport(sink=None, provider=None)
    from azure.identity import AzureCliCredential
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

    exporter = _recording_exporter(connection_string, AzureCliCredential())
    provider = MeterProvider(metric_readers=[PeriodicExportingMetricReader(exporter, export_interval_millis=60_000)])
    return TelemetryExport(sink=OtelMetricsTelemetrySink(meter_provider=provider), provider=provider, exporter=exporter)
