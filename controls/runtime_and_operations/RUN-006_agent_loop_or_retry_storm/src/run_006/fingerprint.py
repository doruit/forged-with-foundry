"""Action fingerprints: the same tool with the same arguments is the same action."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def fingerprint(tool_name: str, args: Any) -> str:
    """SHA-256 over the tool name and canonical JSON arguments (key order ignored)."""
    canonical = json.dumps({"tool": tool_name, "args": args}, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
