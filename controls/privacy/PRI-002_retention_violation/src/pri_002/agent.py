"""Foundry agent that explains deterministic PRI-002 decisions."""

from __future__ import annotations

import json
import os

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential

from .models import RetentionDecision


class RetentionOperationsAgent:
    """Non-authoritative agent: explain and guide, never decide or delete."""

    def __init__(self) -> None:
        self._agent = Agent(
            client=FoundryChatClient(
                project_endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
                model=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"],
                credential=AzureCliCredential(),
            ),
            name="RetentionOperationsAssistant",
            instructions=(
                "You explain PRI-002 retention decisions to a Privacy Officer. "
                "The supplied decisions were made by deterministic code and are authoritative. "
                "Never change a decision, invent content, request Blob contents, or claim deletion. "
                "For remediation_required, explain that explicit human approval and a guarded "
                "ETag-conditional tool are required. For protected or blocked, state that deletion "
                "is prohibited. Be concise and use plain language."
            ),
        )

    async def explain(self, decisions: list[RetentionDecision]) -> str:
        safe_payload = [decision.safe_dict() for decision in decisions]
        result = await self._agent.run(
            "Explain this metadata-only PRI-002 scan. Separate compliant, actionable, "
            "protected, and blocked outcomes. Do not infer any record content.\n\n"
            + json.dumps(safe_payload, indent=2)
        )
        return result.text
