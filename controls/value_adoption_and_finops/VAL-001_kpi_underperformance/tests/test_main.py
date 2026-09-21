"""Protect the single explicit, Entra-authenticated telemetry path."""

import importlib.util
import os
from pathlib import Path
import sys
from unittest.mock import MagicMock

CONTROL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CONTROL))
SPEC = importlib.util.spec_from_file_location("val001_main", CONTROL / "main.py")
host = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(host)


def test_given_host_start_when_configured_then_automatic_exporter_disabled(monkeypatch):
    server = MagicMock()
    provider = MagicMock()
    monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://example.test/api/projects/test")
    monkeypatch.setenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "test")
    monkeypatch.setattr(host, "DefaultAzureCredential", MagicMock())
    monkeypatch.setattr(host, "FoundryChatClient", MagicMock())
    monkeypatch.setattr(host, "build_agent", MagicMock(return_value="agent"))
    monkeypatch.setattr(host, "create_event_logger", lambda credential: (MagicMock(), provider))
    monkeypatch.setattr(host, "ResponsesHostServer", server)

    host.main()

    server.assert_called_once_with("agent", configure_observability=None)
    provider.shutdown.assert_called_once_with()


def test_given_platform_variable_when_logger_created_then_control_binding_used(monkeypatch):
    exporter = MagicMock()
    credential = MagicMock()
    monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "platform-managed")
    monkeypatch.setenv("VAL001_APPLICATIONINSIGHTS_CONNECTION_STRING", "control-owned")
    monkeypatch.setattr(host, "AzureMonitorLogExporter", exporter)
    monkeypatch.setattr(host, "SimpleLogRecordProcessor", MagicMock())
    monkeypatch.setattr(host, "LoggerProvider", MagicMock())
    monkeypatch.setattr(host, "LoggingHandler", MagicMock())

    host.create_event_logger(credential)

    exporter.assert_called_once_with(connection_string="control-owned", credential=credential,
                                     disable_offline_storage=True)
    assert "APPLICATIONINSIGHTS_CONNECTION_STRING" not in os.environ