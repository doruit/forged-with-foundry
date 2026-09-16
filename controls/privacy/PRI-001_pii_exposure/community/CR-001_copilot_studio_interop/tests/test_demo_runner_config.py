"""Tests for demo_runner.py's configuration preflight check.

This does not run the demo itself (that requires real, live Azure AI
Language access, per the module's own docstring) -- it only verifies that
missing configuration fails with one clear, actionable message before any
run starts, instead of a bare ``KeyError`` mid-scenario.
"""

from __future__ import annotations

import pytest

import src.cr001_interop.demo_runner as demo_runner


def test_missing_azure_language_endpoint_fails_with_clear_message(monkeypatch) -> None:
    monkeypatch.delenv("AZURE_LANGUAGE_ENDPOINT", raising=False)

    with pytest.raises(SystemExit) as excinfo:
        demo_runner._check_required_configuration()

    assert "AZURE_LANGUAGE_ENDPOINT" in str(excinfo.value)
    assert "not Azure-free" in str(excinfo.value)


def test_configured_azure_language_endpoint_passes_preflight(monkeypatch) -> None:
    monkeypatch.setenv("AZURE_LANGUAGE_ENDPOINT", "https://example-language.cognitiveservices.azure.com/")

    demo_runner._check_required_configuration()  # Must not raise.
