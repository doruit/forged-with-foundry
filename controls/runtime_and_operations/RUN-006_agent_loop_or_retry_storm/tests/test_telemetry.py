"""Export status must reflect the exporter's real result, not the SDK's force_flush."""

from __future__ import annotations

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import MetricExporter, MetricExportResult, PeriodicExportingMetricReader

from src.run_006.telemetry import TelemetryExport


class StubExporter(MetricExporter):
    def __init__(self, result):
        super().__init__()
        self.result = result
        self.results = []

    def export(self, metrics_data, timeout_millis=10_000, **kwargs):
        self.results.append(self.result)
        return self.result

    def force_flush(self, timeout_millis=10_000):
        return True

    def shutdown(self, timeout_millis=30_000, **kwargs):
        return None


def _export(result):
    exporter = StubExporter(result)
    provider = MeterProvider(metric_readers=[PeriodicExportingMetricReader(exporter, export_interval_millis=60_000)])
    provider.get_meter("t").create_counter("acs_intervention_deny_total").add(1, {"reason_code": "x"})
    return TelemetryExport(sink=None, provider=provider, exporter=exporter).flush()


def test_successful_export_is_reported_as_exported():
    assert _export(MetricExportResult.SUCCESS) == "exported"


def test_failed_export_is_not_reported_as_success():
    assert _export(MetricExportResult.FAILURE) == "not_confirmed"


def test_no_notification_path_is_not_configured():
    assert TelemetryExport(sink=None, provider=None).flush() == "not_configured"
