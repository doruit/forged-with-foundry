"""Foundry agent that explains deterministic DAT-PRE-002 decisions (optional in the core demo)."""

from __future__ import annotations

import json
import os

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential

from .models import ClassificationDecision


class ClassificationAgent:
    """Non-authoritative agent: explain and guide, never decide or classify."""

    def __init__(self) -> None:
        self._agent = Agent(
            client=FoundryChatClient(
                project_endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
                model=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"],
                credential=AzureCliCredential(),
            ),
            name="DataClassificationAssistant",
            instructions=(
                "You explain DAT-PRE-002 data-classification decisions to a Data Owner. "
                "The supplied decisions were made by deterministic code, reading a file's real "
                "Microsoft Purview sensitivity-label state through Microsoft Graph — you never "
                "see file content, only a file name, its synthetic content category, and the "
                "decision. Never invent file content or claim a classify action completed; that "
                "is a separate guarded action the human must explicitly request, and its outcome "
                "is only confirmed after Microsoft Graph re-verifies the label was actually "
                "applied. For flagged files, explain that a classify action can be requested. For "
                "blocked files, explain that label extraction could not complete safely, so the "
                "file cannot be cleared automatically. Be concise and use plain language."
            ),
        )

    async def explain(self, decisions: list[ClassificationDecision]) -> str:
        safe_payload = [decision.safe_dict() for decision in decisions]
        result = await self._agent.run(
            "Explain this metadata-only DAT-PRE-002 scan. Separate compliant, flagged, and "
            "blocked outcomes. Do not infer or repeat any file content.\n\n"
            + json.dumps(safe_payload, indent=2)
        )
        return result.text
