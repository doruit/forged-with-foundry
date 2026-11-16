"""AUT-004 audit: callers are reduced to a role and an opaque reference."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location("aut_004_audit", Path(__file__).resolve().parents[1] / "infra" / "audit.py")
audit = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(audit)

STATE = {"operator_principal_id": "op-oid", "identityPrincipalId": "mi-oid"}


def _caller(object_id: str) -> str:
    return json.dumps([
        {"callerIdentityType": "ApplicationId", "callerIdentity": "cli-app"},
        {"callerIdentityType": "ObjectId", "callerIdentity": object_id},
        {"callerIdentityType": "UPN", "callerIdentity": "someone@contoso.example"},
    ])


def test_operator_and_runtime_identity_are_distinguished_without_leaking_ids():
    operator = audit.describe_actor(audit.caller_object_id(_caller("op-oid")), STATE)
    runtime = audit.describe_actor(audit.caller_object_id(_caller("mi-oid")), STATE)
    assert operator["role"] == "operator" and runtime["role"] == "runtime_identity"
    assert operator["actor"] != runtime["actor"]
    assert "op-oid" not in json.dumps(operator) and "contoso" not in json.dumps(operator)


def test_missing_or_malformed_caller_is_not_recorded():
    assert audit.describe_actor(audit.caller_object_id(""), STATE)["role"] == "not_recorded"
    assert audit.describe_actor(audit.caller_object_id("not json"), STATE)["role"] == "not_recorded"
    assert audit.describe_actor(audit.caller_object_id(_caller("someone-else")), STATE)["role"] == "other"
