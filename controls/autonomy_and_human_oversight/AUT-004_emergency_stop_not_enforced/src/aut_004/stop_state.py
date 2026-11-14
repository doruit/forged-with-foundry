"""Read the authoritative stop switch: one App Configuration feature flag.

`enabled` means the protected action may run. Every other outcome — the flag
switched off, missing, malformed, throttled or unreadable — is reported as
such and treated by the ACS policy as stopped. Reads are never cached.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from azure.core.exceptions import HttpResponseError, ResourceNotFoundError

from . import FLAG_PREFIX

READ_TIMEOUT_SECONDS = 2
READ_RETRIES = 1


@dataclass(frozen=True)
class StopState:
    status: str  # enabled | disabled | missing | invalid | throttled | unavailable
    flag_name: str
    etag: str | None
    last_modified: str | None
    read_at: str

    def as_snapshot(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "flag_name": self.flag_name,
            "etag": self.etag,
            "last_modified": self.last_modified,
            "read_at": self.read_at,
        }


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _parse(flag_name: str, value: Any) -> str:
    try:
        flag = json.loads(value) if isinstance(value, str) else None
    except ValueError:
        return "invalid"
    if not isinstance(flag, dict) or flag.get("id") != flag_name or type(flag.get("enabled")) is not bool:
        return "invalid"
    return "enabled" if flag["enabled"] else "disabled"


def read_stop_state(client: Any, flag_name: str) -> StopState:
    """Read the flag once, bounded by the client's timeout and retry settings."""
    try:
        setting = client.get_configuration_setting(key=FLAG_PREFIX + flag_name)
    except ResourceNotFoundError:
        return StopState("missing", flag_name, None, None, _now())
    except HttpResponseError as error:
        status = "throttled" if error.status_code == 429 else "unavailable"
        return StopState(status, flag_name, None, None, _now())
    except Exception:  # noqa: BLE001 - any read failure means the stop cannot be ruled out
        return StopState("unavailable", flag_name, None, None, _now())
    modified = getattr(setting, "last_modified", None)
    return StopState(
        _parse(flag_name, getattr(setting, "value", None)),
        flag_name,
        getattr(setting, "etag", None),
        modified.isoformat() if isinstance(modified, datetime) else None,
        _now(),
    )


def app_configuration_client(endpoint: str, credential: Any) -> Any:
    from azure.appconfiguration import AzureAppConfigurationClient

    return AzureAppConfigurationClient(
        base_url=endpoint,
        credential=credential,
        connection_timeout=READ_TIMEOUT_SECONDS,
        read_timeout=READ_TIMEOUT_SECONDS,
        retry_total=READ_RETRIES,
        retry_backoff_factor=0.2,
    )


def attempt_to_lift_stop(client: Any, flag_name: str) -> dict[str, Any]:
    """Try to switch the flag back on with the caller's identity.

    Used to show that the agent runtime cannot clear its own stop: its
    managed identity holds App Configuration Data Reader only.
    """
    from azure.appconfiguration import FeatureFlagConfigurationSetting

    try:
        client.set_configuration_setting(FeatureFlagConfigurationSetting(flag_name, enabled=True))
    except HttpResponseError as error:
        return {"lifted": False, "http_status": error.status_code}
    except Exception as error:  # noqa: BLE001
        return {"lifted": False, "http_status": None, "error_class": type(error).__name__}
    return {"lifted": True, "http_status": 200}
