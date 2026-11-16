"""App Service authenticated identity adapter (Microsoft Entra via Easy Auth)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Mapping
from uuid import UUID

ROLE = "SupportOperator"


def operator_reference(headers: Mapping[str, str], *, tenant: str, secret: str) -> str | None:
    """Return an opaque reference for a signed-in SupportOperator, or None."""
    if not tenant or len(secret) < 32:
        return None
    try:
        lowered = {key.lower(): value for key, value in headers.items()}
        principal = json.loads(base64.b64decode(lowered["x-ms-client-principal"], validate=True))
        if principal["auth_typ"] != "aad":
            return None
        claims: dict[str, list[str]] = {}
        for claim in principal["claims"]:
            claims.setdefault(claim["typ"], []).append(claim["val"])
        tenants = claims.get("http://schemas.microsoft.com/identity/claims/tenantid", claims.get("tid", []))
        subjects = claims.get("http://schemas.microsoft.com/identity/claims/objectidentifier", claims.get("oid", []))
        if tenants != [tenant] or len(subjects) != 1:
            return None
        UUID(subjects[0])
        if ROLE not in claims.get(principal["role_typ"], []):
            return None
        return hmac.new(secret.encode(), f"{tenant}:{subjects[0]}".encode(), hashlib.sha256).hexdigest()[:16]
    except (KeyError, TypeError, ValueError, AttributeError):
        return None
