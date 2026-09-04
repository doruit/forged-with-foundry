"""Foundry agent that explains deterministic PRI-PRE-001 decisions."""

from __future__ import annotations

import json
import os

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential

from .models import GateDecision


class DpiaGateAgent:
    """Non-authoritative agent: explain and guide, never decide or trigger a go-live attempt."""

    def __init__(self) -> None:
        self._agent = Agent(
            client=FoundryChatClient(
                project_endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
                model=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"],
                credential=AzureCliCredential(),
            ),
            name="DpiaGateAssistant",
            instructions=(
                "You explain PRI-PRE-001 DPIA-required-but-missing decisions to a DPO. "
                "The supplied decisions were made by deterministic code and are authoritative. "
                "You only see metadata: a risk factor count, whether a DPIA is required, and "
                "whether evidence is complete. You never see the requestor's email, the DPIA "
                "approver's name, or the case id. Never claim a go-live attempt happened or "
                "invent its result; "
                "that is a separate, guarded action backed by a real Azure Policy evaluation, not "
                "something you can trigger. For blocked_unknown records, explain that the risk "
                "factors themselves could not be determined, so the gate fails closed rather than "
                "assuming low risk. Be concise and use plain language."
            ),
        )

    async def explain(self, decisions: list[GateDecision]) -> str:
        safe_payload = [decision.safe_dict() for decision in decisions]
        result = await self._agent.run(
            "Explain this metadata-only PRI-PRE-001 scan. Separate allowed, blocked, and "
            "blocked_unknown outcomes. Do not infer any project name or business content.\n\n"
            + json.dumps(safe_payload, indent=2)
        )
        return result.text
