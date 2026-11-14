"""Chainlit interface for the AUT-004 demo, hosted on App Service.

The red button is not in this app: it is the feature flag in Azure Portal.
This app is the agent runtime, and its managed identity can only read that flag.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

import chainlit as cl
from azure.identity import ManagedIdentityCredential

from .agent import FoundryAgentSession
from .auth import operator_reference
from .evidence import write_evidence
from .policy import get_control
from .service import Scope, StopService
from .stop_state import app_configuration_client, attempt_to_lift_stop, read_stop_state

EVIDENCE_DIR = Path(os.environ.get("AUT004_EVIDENCE_DIR", "evidence"))
ORDER_BUTTONS = [("ORD-1001", "Refund ORD-1001 (damaged)"), ("ORD-1006", "Refund ORD-1006 (slow gateway, 30 s)")]


@lru_cache(maxsize=1)
def credential() -> ManagedIdentityCredential:
    return ManagedIdentityCredential(client_id=os.environ["AZURE_CLIENT_ID"])


@lru_cache(maxsize=1)
def config_client():
    return app_configuration_client(os.environ["AUT004_APPCONFIG_ENDPOINT"], credential())


@lru_cache(maxsize=1)
def service() -> StopService:
    scope = Scope(
        protected_tool=os.environ.get("AUT004_PROTECTED_TOOL", ""),
        flag_name=os.environ.get("AUT004_FLAG_NAME", ""),
        contract_sha256=os.environ.get("AUT004_CONTRACT_SHA256", ""),
    )
    return StopService(get_control(), scope, lambda: read_stop_state(config_client(), scope.flag_name))


def _evidence(kind: str, body: dict) -> Path:
    user = cl.user_session.get("user")
    return write_evidence(
        EVIDENCE_DIR, kind, body, scope=service().scope.metadata(), actor_reference=user.identifier if user else None
    )


def _block(data: dict) -> str:
    return "```json\n" + json.dumps(data, indent=2) + "\n```"


@cl.header_auth_callback
def authenticate(headers: dict[str, str]) -> cl.User | None:
    reference = operator_reference(
        headers, tenant=os.environ.get("AUT004_TENANT_ID", ""), secret=os.environ.get("CHAINLIT_AUTH_SECRET", "")
    )
    return cl.User(identifier=reference) if reference else None


def _actions() -> list[cl.Action]:
    actions = [cl.Action(name="refund", payload={"order_id": order}, label=label) for order, label in ORDER_BUTTONS]
    return actions + [
        cl.Action(name="probe", payload={}, label="Verify the stop (probe)"),
        cl.Action(name="lift", payload={}, label="Agent tries to lift its own stop"),
        cl.Action(name="report", payload={}, label="In-flight report"),
    ]


@cl.on_chat_start
async def start() -> None:
    startup = await service().startup()
    if startup["decision"] != "allow":
        await cl.Message(content=f"**ACS agent_startup denied** (`{startup['reason']}`). The agent will not run.").send()
        return
    state = read_stop_state(config_client(), service().scope.flag_name)
    await cl.Message(
        content=(
            "# AUT-004 — Emergency stop\n\n"
            f"Protected action: `{service().scope.protected_tool}` · stop switch `{state.flag_name}` "
            f"reads **{state.status}**.\n\nLookups and ticket replies are outside the stop scope. "
            "Press the red button in Azure Portal → App Configuration → Feature management → Feature flags."
        ),
        actions=_actions(),
    ).send()


async def _run(prompt: str) -> None:
    if (await service().startup())["decision"] != "allow":
        await cl.Message(content="ACS agent_startup denied; the agent will not run.").send()
        return
    session = FoundryAgentSession.from_environment(credential(), dict(os.environ))

    async def emit(line: str) -> None:
        await cl.Message(content=f"`{line}`", author="ACS").send()

    reply = await service().handle_request(session, prompt, emit)
    await cl.Message(content=reply, actions=_actions()).send()


@cl.on_message
async def message(incoming: cl.Message) -> None:
    await _run(incoming.content)


@cl.action_callback("refund")
async def refund(action: cl.Action) -> None:
    order = action.payload["order_id"]
    await _run(f"Ticket TCK-4001: The customer reports that order {order} arrived damaged and asks for a refund.")


@cl.action_callback("probe")
async def probe(_action: cl.Action) -> None:
    result = await service().probe()
    path = _evidence("verification_probe", result)
    await cl.Message(content="**Verification probe**\n" + _block(result) + f"\nEvidence: `{path.name}`", actions=_actions()).send()


@cl.action_callback("lift")
async def lift(_action: cl.Action) -> None:
    result = attempt_to_lift_stop(config_client(), service().scope.flag_name)
    result["identity"] = "agent runtime managed identity (App Configuration Data Reader)"
    path = _evidence("self_recovery_attempt", result)
    await cl.Message(content="**Agent runtime tried to switch refunds back on**\n" + _block(result) + f"\nEvidence: `{path.name}`", actions=_actions()).send()


@cl.action_callback("report")
async def report(_action: cl.Action) -> None:
    state = read_stop_state(config_client(), service().scope.flag_name)
    result = service().in_flight_report(state)
    path = _evidence("in_flight_report", result)
    await cl.Message(content="**In-flight report**\n" + _block(result) + f"\nEvidence: `{path.name}`", actions=_actions()).send()
