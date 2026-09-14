"""Loader for the CR-001 agent-scope policy file (``policy/agent_scope.yaml``).

Defines which agents require PRI-001, on which platform, over which
protocols. Fails closed on any malformed entry -- a policy owner should see a
loud error, not a silently-skipped agent.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

_ALLOWED_PROTOCOLS = frozenset({"mcp", "a2a"})
_DEFAULT_PATH = Path(__file__).resolve().parents[2] / "policy" / "agent_scope.yaml"


class AgentScopeValidationError(ValueError):
    """Raised for duplicate agent IDs, unsupported protocols, or missing fields."""


@dataclass(frozen=True)
class AgentScope:
    agent_id: str
    platform: str
    required_control: str
    coverage_scope: str
    allowed_protocols: tuple[str, ...]


def load_agent_scope(path: Path | str | None = None) -> list[AgentScope]:
    """Load and validate ``agent_scope.yaml``. Raises on any invalid entry."""
    target = Path(path) if path else _DEFAULT_PATH
    raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    entries = raw.get("agents") or []

    scopes: list[AgentScope] = []
    seen_ids: set[str] = set()
    for index, entry in enumerate(entries):
        for required in (
            "agent_id",
            "platform",
            "required_control",
            "coverage_scope",
            "allowed_protocols",
        ):
            if not entry.get(required):
                raise AgentScopeValidationError(
                    f"agents[{index}] is missing required field {required!r}"
                )

        agent_id = entry["agent_id"]
        if agent_id in seen_ids:
            raise AgentScopeValidationError(f"duplicate agent_id: {agent_id!r}")
        seen_ids.add(agent_id)

        allowed_protocols = tuple(entry["allowed_protocols"])
        unsupported = set(allowed_protocols) - _ALLOWED_PROTOCOLS
        if unsupported:
            raise AgentScopeValidationError(
                f"agent_id {agent_id!r} declares unsupported protocol(s): {sorted(unsupported)}"
            )

        scopes.append(
            AgentScope(
                agent_id=agent_id,
                platform=entry["platform"],
                required_control=entry["required_control"],
                coverage_scope=entry["coverage_scope"],
                allowed_protocols=allowed_protocols,
            )
        )
    return scopes
