# CR-001 — Copilot Studio interoperability (community request extension)

> **Optional.** Nothing in this folder is required to run or understand the
> core [PRI-001 — PII exposure](../../README.md) demo. Skip this folder
> entirely if you only want the core lesson.

## The community question

In the comments of the Forged with Foundry LinkedIn launch post, a community
member asked:

> "I like the PII governance. Can we deploy this and test on a Copilot
> Studio agent via A2A communications?"

This folder answers that question with a small, runnable, **local-first**
demo: it does not just expose PRI-001's PII gate over MCP and A2A, it also
measures whether the gate was actually invoked for every agent run — because
an endpoint log alone only proves a call happened, not that every required
run went through it.

## Core principle: measurement needs an independent denominator

For every in-scope run, three events are recorded independently:

1. `agent.run.started` — emitted by [`demo_runner.py`](src/cr001_interop/demo_runner.py), never by the endpoint itself.
2. `pii.control.evaluated` — emitted by the MCP or A2A adapter, exactly once per run.
3. `agent.run.completed` — emitted by `demo_runner.py`.

**One run = one inbound agent request or user turn.** A run with no matching,
valid `pii.control.evaluated` event is visible as non-compliant —
[`compliance_evaluator.py`](src/cr001_interop/compliance_evaluator.py) is
what actually proves this, not narration.

## Shared evidence

[`evidence.py`](src/cr001_interop/evidence.py) defines one schema used by
both adapters and the evaluator. It has no field for prompts, messages,
detected PII values, redacted text, or tool arguments — that is a structural
guarantee, not a redaction step. Events are written, unsampled, to a local
JSONL file (`interop_evidence.jsonl`, gitignored). An optional
OpenTelemetry/Application Insights exporter activates only when
`APPLICATIONINSIGHTS_CONNECTION_STRING` is set — the JSONL sink stays the
authoritative source either way.

## MCP variant

[`mcp_server.py`](src/cr001_interop/mcp_server.py) exposes `redact_text` and
`redact_document` as MCP tools (Streamable HTTP transport), reusing core
PRI-001's detection/redaction/escalation unchanged. Both tools accept
`agent_id`/`run_id`/`trace_id` as explicit arguments for correlation.

MCP is the right protocol when an agent needs a governed tool or protected
action. But offering an optional `redact_pii` tool does not *force* an agent
to use it — this measurement layer detects a missing invocation, it does not
by itself prevent bypass. Preventive enforcement would require making the
MCP route the only path to the protected action.

Run locally:

```bash
cd community/CR-001_copilot_studio_interop
../../../../../.venv/bin/python -m pip install -r requirements.txt
PYTHONPATH="../..:." ../../../../../.venv/bin/uvicorn src.cr001_interop.mcp_server:create_app --factory --port 8001
```

## A2A variant

[`a2a_server.py`](src/cr001_interop/a2a_server.py) uses the official
[`a2a-sdk`](https://pypi.org/project/a2a-sdk/) (`a2aproject/a2a-python`) to
expose the existing PII-governed Foundry agent (core `agent.py`, unchanged)
as an A2A server. It derives `run_id`/`trace_id` from the A2A task/context
IDs where the SDK provides them, gates the inbound message through the same
Shape-B ACS boundary as MCP, and forwards only the sanitized text to the
Foundry agent.

A2A is the right protocol when Copilot Studio delegates a complete task to a
specialized, governed agent — it protects the *receiving* agent only when
all delegation actually reaches it through this endpoint.

Run locally:

```bash
cd community/CR-001_copilot_studio_interop
PYTHONPATH="../..:." ../../../../../.venv/bin/uvicorn src.cr001_interop.a2a_server:create_app --factory --port 9999
```

## Policy scope

[`policy/agent_scope.yaml`](policy/agent_scope.yaml) declares which agents
require PRI-001, on which platform, over which protocols. Validated at load
time by [`policy_scope.py`](src/cr001_interop/policy_scope.py): duplicate
`agent_id`, unsupported protocols, and missing required fields all raise
rather than silently skipping an agent.

## Compliance evaluator

```bash
cd community/CR-001_copilot_studio_interop
PYTHONPATH="../..:." ../../../../../.venv/bin/python -m src.cr001_interop.demo_runner
PYTHONPATH="../..:." ../../../../../.venv/bin/python -m src.cr001_interop.compliance_evaluator
```

`demo_runner.py` simulates a few synthetic runs and deliberately skips the
MCP call for one of them, so the evaluator has a real gap to report:

```text
Agent                 Platform        Required  Valid   Missing  Failed  Coverage  Status
-----------------------------------------------------------------------------------------
copilot-pii-demo      copilot_studio  2         1       1        0       50%       NON_COMPLIANT
foundry-pii-demo      foundry         0         0       0        0       0%        NO_ACTIVITY
```

A valid attestation must match `agent_id` and `run_id`, reference `PRI-001`,
use an allowed protocol, carry a known policy version, have `decision` in
`{allow, redact, deny}` (never `error`), fall between the run's start and
completion, and — by construction — contain no raw PII.
`deny` counts as a **successful** control execution, not a failure. Coverage
is `distinct required runs with a valid attestation / all distinct required
runs` — never derived from raw endpoint-call counts. Statuses:
`COMPLIANT`, `NON_COMPLIANT`, `CONTROL_FAILED` (attestation exists but
errored), `UNVERIFIABLE` (telemetry incomplete/uncorrelatable), and
`NO_ACTIVITY`.

## MCP vs. A2A vs. no endpoint call

| Pattern | Use when | What is measured | Runtime governance meaning |
|---|---|---|---|
| MCP | An agent invokes a governed tool or protected action | Whether each required run invoked and completed the PII control | Preventive only when the protected action has no bypass path; otherwise detective |
| A2A | One agent delegates a task to a specialized governed agent | Whether each delegated run received a valid PII evaluation | Protects the receiving agent when all delegation reaches the governed endpoint |
| No endpoint call | The agent processes a run without MCP/A2A evidence | A started run exists without a matching control attestation | Reported as non-compliant or unverifiable |

## What this proves — and does not

- Measurement is a **detective** control; it does not by itself force tool or
  agent selection.
- A policy owner can measure control coverage for every observed run.
- 100% endpoint coverage demonstrates execution of PRI-001 within this
  technical scope, not general GDPR or legal compliance.
- When Copilot Studio is the entry point, the original prompt has already
  reached Copilot Studio before MCP or A2A selection happens. This demo
  proves protection *before* the external Foundry agent or downstream
  action — not before Copilot Studio itself.
- Missing telemetry is never interpreted as compliant.

## Copilot Studio and Foundry telemetry guidance

**Copilot Studio:** agent-level Application Insights/OpenTelemetry telemetry
would provide the independent run inventory in a live tenant; the MCP/A2A
calls above provide the matching control evidence. Distributed trace
correlation is preferred. **Exact per-run trace-context propagation from a
live Copilot Studio tenant into MCP/A2A tool inputs has not been validated
in this pass** — if reliable correlation cannot be established, the
evaluator must return `UNVERIFIABLE`, never a false compliant result. Where
propagation isn't available, pass a correlation value explicitly through
configured tool inputs or the A2A `messageId`/`contextId`, as this demo does.

**Foundry:** instrument the demo application (here, `demo_runner.py`) so
every run emits `agent.run.started`/`agent.run.completed` independently of
the MCP/A2A call, sharing the same `run_id` and trace context — kept outside
the PII policy logic itself.

## Live Copilot Studio walkthrough (optional)

The MCP server in this folder is deployed to Azure App Service
(`fwf-cr001-mcp.azurewebsites.net`, see [`infra/`](infra/)) and was wired
into a real Copilot Studio agent. Screenshots are in
[`media/copilot-studio-setup/`](media/copilot-studio-setup/).

**Prerequisites** for wiring a live agent this way:

- A Power Platform Sandbox or Production environment (Developer
  environments don't support pay-as-you-go billing).
- Either prepaid Copilot Studio message capacity, or an Azure subscription
  linked to the environment through a Power Platform billing policy with
  the Copilot Studio message meter enabled — see
  [Pay-as-you-go plan overview](https://learn.microsoft.com/power-platform/admin/pay-as-you-go-overview).

Steps:

1. Build a new agent and give it instructions that require the PII tool
   before forwarding any user-supplied text.

   <img src="media/copilot-studio-setup/00-agent-build-page.png" width="2370" alt="Copilot Studio agent build page with PRI-001 redaction instructions">

2. **Add a tool** — the built-in **Model Context Protocol (MCP)** tab only
   lists curated first-party MCP servers (Dataverse, SharePoint, Fabric,
   and similar); there's no entry for an arbitrary MCP endpoint here.

   <img src="media/copilot-studio-setup/01-add-tool-dialog.png" width="2370" alt="Add a tool dialog in Copilot Studio">
   <img src="media/copilot-studio-setup/02-mcp-tab-gallery.png" width="2370" alt="MCP tab showing only curated first-party servers">

3. Use **Add → Model Context Protocol (MCP)** instead, which creates a new,
   custom MCP server registration pointed at the deployed endpoint's
   `/mcp` route. This is the native way to register a custom MCP server as
   of this pass — it replaces the custom-connector-plus-OpenAPI-definition
   workaround an earlier attempt used.

   <img src="media/copilot-studio-setup/03-add-mcp-server-form.png" width="2370" alt="Add custom MCP server form pointed at the deployed /mcp endpoint">

4. Select and create a connection for the new server; the tool then
   appears attached to the agent.

   <img src="media/copilot-studio-setup/04-select-connection.png" width="2370" alt="Selecting a connection for the new MCP server">
   <img src="media/copilot-studio-setup/05-create-connection-dialog.png" width="2370" alt="Create connection dialog for the MCP server">
   <img src="media/copilot-studio-setup/06-tool-added-to-agent.png" width="2370" alt="FWF CR-001 PII MCP tool attached to the agent">

5. In **Preview**, send a message containing synthetic PII (e.g. a name,
   email, and phone number) and **Allow** the tool-permission prompt. The
   agent calls `redact_text` and answers using only the redacted content.
   Expanding the tool call in the Preview trace shows the real MCP
   response — `redacted_text` with the PII spans masked, `pii_count: 3`,
   `categories: ["Email", "Person", "PhoneNumber"]`,
   `action: "redact_and_escalate"`. This confirms the deployed MCP server,
   the Copilot Studio tool wiring, and the Azure AI Language redaction all
   work end to end.

   <img src="media/copilot-studio-setup/07-live-preview-redaction-success.png" width="1554" alt="Live Preview chat showing the redacted summary response">
   <img src="media/copilot-studio-setup/08-live-preview-tool-trace.png" width="1554" alt="Expanded redact_text tool call trace with masked redacted_text output">

## Limitations

- Local-first only: no Azure deployment, Entra ID auth, or live Copilot
  Studio tenant is required or validated in this pass.
- **The deployed MCP endpoint in the live walkthrough runs with no
  authentication** — the custom Copilot Studio connector uses the `NoAuth`
  connection template, and `mcp_server.py`'s optional
  `BearerAuthMiddleware` (`CR001_ENTRA_TENANT_ID`/`CR001_ENTRA_AUDIENCE`)
  is left disabled so the walkthrough stays reproducible without a second
  Entra app registration and OAuth connection. This is an intentional
  demo simplification, not a production posture: a real deployment should
  set both env vars to enable the bearer-token boundary and register the
  Copilot Studio connector with a matching Entra ID OAuth 2.0 connection
  instead of `NoAuth`, so only the intended Copilot Studio agent (and
  nothing else on the public internet) can call `redact_text`/
  `redact_document`.
- The [live Copilot Studio walkthrough](#live-copilot-studio-walkthrough-optional)
  above confirms the agent build, MCP tool wiring, and an end-to-end
  **Preview** message that triggers `redact_text` and returns correctly
  redacted content — this required both usable Copilot Studio message
  capacity (see Prerequisites) and the deployed MCP server's `policy/`
  folder being included in its App Service package (an earlier deploy
  omitted it, causing every tool call to fail with a missing-manifest
  error; `infra/deploy.sh` now copies it).
- This demo does not claim production-grade or tenant-wide enforcement.

## Cleanup

Running the MCP/A2A servers and the compliance evaluator locally creates no
Azure resources — only the local `interop_evidence.jsonl` file (gitignored):

```bash
rm -f interop_evidence.jsonl
```

If you also deployed the optional MCP server via [`infra/deploy.sh`](infra/),
remove it directly (it does not share a resource group with, or require
deleting, any other control's resources):

```bash
az webapp delete --name "${CR001_APP_SERVICE_NAME:-fwf-cr001-mcp}" --resource-group "${AZURE_RESOURCE_GROUP}"
az appservice plan delete --name "${CR001_APP_SERVICE_PLAN_NAME:-fwf-cr001-plan}" --resource-group "${AZURE_RESOURCE_GROUP}" --yes
```
