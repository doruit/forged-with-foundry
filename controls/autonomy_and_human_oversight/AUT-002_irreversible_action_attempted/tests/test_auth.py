import base64
import json
from unittest.mock import patch

import pytest

from src.aut_002.auth import operator_from_headers

TENANT = "00000000-0000-0000-0000-000000000001"
SECRET = "synthetic-signing-secret-for-tests-only"


def headers(role: str = "OpsManager", tenant: str = TENANT) -> dict[str, str]:
    principal = {"auth_typ": "aad", "role_typ": "roles", "claims": [
        {"typ": "tid", "val": tenant},
        {"typ": "oid", "val": "00000000-0000-0000-0000-000000000002"},
        {"typ": "roles", "val": role},
    ]}
    return {"X-MS-CLIENT-PRINCIPAL": base64.b64encode(json.dumps(principal).encode()).decode()}


def test_authenticated_role_and_session_expiry() -> None:
    operator = operator_from_headers(headers(), tenant=TENANT, secret=SECRET)
    assert operator is not None and operator.can_approve()
    assert "00000000" not in operator.reference
    with patch("src.aut_002.auth.time.time", return_value=operator.authenticated_at + 301):
        assert not operator.can_approve()


def test_authenticated_demo_user_cannot_approve() -> None:
    operator = operator_from_headers(headers("DemoUser"), tenant=TENANT, secret=SECRET)
    assert operator is not None and not operator.can_approve()


@pytest.mark.parametrize("incoming", [{}, {"x-ms-client-principal": "bad"}, headers("Unknown"), headers(tenant="other-tenant")])
def test_missing_invalid_or_untrusted_claims_fail_closed(incoming: dict[str, str]) -> None:
    assert operator_from_headers(incoming, tenant=TENANT, secret=SECRET) is None