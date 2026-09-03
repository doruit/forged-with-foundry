"""Foundry agent that explains deterministic PRI-003 decisions."""

from __future__ import annotations

import json
import os

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential

from .models import DSRDecision


class DSROperationsAgent:
    """Non-authoritative agent: explain and guide, never decide, escalate, or extend."""

    def __init__(self) -> None:
        self._agent = Agent(
            client=FoundryChatClient(
                project_endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
                model=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"],
                credential=AzureCliCredential(),
            ),
            name="DSROperationsAssistant",
            instructions=(
                "You explain PRI-003 data subject request SLA decisions to a DPO. "
                "The supplied decisions were made by deterministic code and are authoritative. "
                "Never change a decision, invent a due date, grant an extension, request "
                "requester content, or claim an escalation happened. For at_risk or breached, "
                "explain that DPO escalation is required and, for eligible request types, that a "
                "guarded one-time extension may be requested. Erasure requests never permit an "
                "extension. Be concise and use plain language."
            ),
        )

    async def explain(self, decisions: list[DSRDecision]) -> str:
        safe_payload = [decision.safe_dict() for decision in decisions]
        result = await self._agent.run(
            "Explain this metadata-only PRI-003 scan. Separate on_track, at_risk, "
            "breached, and blocked outcomes. Do not infer any requester identity or "
            "request content.\n\n" + json.dumps(safe_payload, indent=2)
        )
        return result.text
