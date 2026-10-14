import asyncio
import hashlib
import json
from pathlib import Path

from agent_control_specification import AgentControlBlocked

from src.aut_002 import acs_gate


def test_checked_mandate_controls_allowed_and_prohibited_calls(monkeypatch, tmp_path):
    source = Path(__file__).resolve().parents[2] / "AUT-PRE-001_autonomy_boundary_undefined/candidate/.fwf/agents/aut-002-irreversible-action/mandate.yaml"
    raw = source.read_bytes()
    target = tmp_path / "mandate.json"
    target.write_bytes(raw)
    monkeypatch.setattr(acs_gate, "_MANDATE_PATH", target)
    monkeypatch.setenv("AUT002_MANDATE_SHA256", hashlib.sha256(raw).hexdigest())
    acs_gate.load_mandate.cache_clear()
    acs_gate.get_control.cache_clear()

    async def run():
        async def execute(args):
            return {"present": True}

        result = await acs_gate.get_control().run_tool("read_demo_record", {"record_id": "synthetic-record-001"}, execute)
        assert result.value == {"present": True}
        for name in ["publish_demo_record", "permanently_delete_demo_record"]:
            try:
                await acs_gate.get_control().run_tool(name, {"record_id": "synthetic-record-001"}, execute)
            except AgentControlBlocked:
                pass
            else:
                raise AssertionError("protected/prohibited action unexpectedly executed")

    try:
        asyncio.run(run())
    finally:
        acs_gate.load_mandate.cache_clear()
        acs_gate.get_control.cache_clear()