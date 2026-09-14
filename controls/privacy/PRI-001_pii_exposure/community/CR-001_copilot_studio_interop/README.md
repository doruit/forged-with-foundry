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

## Limitations

- Local-first only: no Azure deployment, Entra ID auth, or live Copilot
  Studio tenant is required or validated in this pass.
- The optional Entra ID bearer-token boundary in `mcp_server.py`
  (`CR001_ENTRA_TENANT_ID`/`CR001_ENTRA_AUDIENCE`) is documented but not
  exercised against a real tenant here.
- Wiring this into a **live** Copilot Studio tenant (Entra app registration +
  `pac connector create` + `pac copilot init`) is further optional work, not
  part of this extension's completion criteria; ask if you want the CLI-first
  steps for that path.
- This demo does not claim production-grade or tenant-wide enforcement.

## Cleanup

This folder creates no Azure resources and no external state beyond the
local `interop_evidence.jsonl` file (gitignored). Delete it directly if you
want a clean slate:

```bash
rm -f interop_evidence.jsonl
```
