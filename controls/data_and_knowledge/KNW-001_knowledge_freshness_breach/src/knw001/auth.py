"""Read the authenticated Entra object ID supplied by App Service Easy Auth."""

from __future__ import annotations

import base64
import binascii
import json
from uuid import UUID

_OBJECT_ID_CLAIMS = {
    "oid",
    "http://schemas.microsoft.com/identity/claims/objectidentifier",
}


def authenticated_object_id(client_principal: str | None) -> str:
    if not client_principal:
        raise PermissionError("An authenticated Entra principal is required.")
    try:
        principal = json.loads(base64.b64decode(client_principal, validate=True))
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError, TypeError):
        raise PermissionError("The authenticated principal is malformed.") from None

    claims = principal.get("claims") if isinstance(principal, dict) else None
    if not isinstance(claims, list) or any(not isinstance(claim, dict) for claim in claims):
        raise PermissionError("The authenticated principal claims are malformed.")
    object_ids = []
    for claim in claims:
        claim_type = claim.get("typ")
        if isinstance(claim_type, str) and claim_type.lower() in _OBJECT_ID_CLAIMS:
            value = claim.get("val")
            if not isinstance(value, str):
                raise PermissionError("The authenticated principal object ID is invalid.")
            object_ids.append(value)
    if len(set(object_ids)) != 1:
        raise PermissionError("The authenticated principal has no unique Entra object ID.")
    try:
        return str(UUID(object_ids[0]))
    except ValueError:
        raise PermissionError("The authenticated principal object ID is invalid.") from None