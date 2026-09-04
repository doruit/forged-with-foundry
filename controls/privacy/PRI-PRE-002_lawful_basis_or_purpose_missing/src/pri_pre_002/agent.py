"""Foundry agent that explains deterministic PRI-PRE-002 decisions."""

from __future__ import annotations

import json
import os

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential

from .models import GateDecision


class LawfulBasisAgent:
    """Non-authoritative agent: explain and guide, never decide or alter a flag."""

    def __init__(self) -> None:
        self._agent = Agent(
            client=FoundryChatClient(
                project_endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
                model=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"],
                credential=AzureCliCredential(),
            ),
            name="LawfulBasisAssistant",
            instructions=(
                "You explain PRI-PRE-002 lawful-basis/purpose decisions to a Privacy "
                "Officer. The supplied decisions were made by deterministic code and are "
                "authoritative. You only see metadata: whether a project processes "
                "personal data, whether its lawful basis is valid, and whether a purpose "
                "is documented. You never see the raw lawful-basis string or purpose id. "
                "This control's real enforcement is an Azure Policy audit assignment that "
                "flags non-compliant resources without blocking them; never claim it "
                "blocks a deployment or that you triggered a compliance scan yourself. "
                "For flagged_unknown records, explain that the declared lawful basis did "
                "not match a recognized GDPR Article 6(1) category, so the gate fails "
                "closed rather than assuming it is fine. Be concise and use plain language."
            ),
        )

    async def explain(self, decisions: list[GateDecision]) -> str:
        safe_payload = [decision.safe_dict() for decision in decisions]
        result = await self._agent.run(
            "Explain this metadata-only PRI-PRE-002 scan. Separate allowed, compliant, "
            "flagged, and flagged_unknown outcomes. Do not infer any project name or "
            "business content.\n\n" + json.dumps(safe_payload, indent=2)
        )
        return result.text
