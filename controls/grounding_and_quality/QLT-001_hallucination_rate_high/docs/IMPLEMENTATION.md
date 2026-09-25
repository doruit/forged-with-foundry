---
title: QLT-001 implementation notes
description: Current technical design for the prompt-agent fleet, Continuous Evaluation, evidence policy, and cleanup.
ms.date: 2026-09-25
---

# Current implementation

QLT-001 uses three Microsoft Foundry `kind: prompt` agents. A local caller
executes each function-tool request and returns the synthetic KB result to the
agent. Continuous Evaluation samples the completed responses and runs
`builtin.groundedness`, `builtin.relevance`, and `builtin.retrieval`.

Only `builtin.groundedness` feeds the QLT-001 decision. The other criteria are
available for diagnosis and future controls; combining them silently would
change the control contract.

## Why prompt agents

Continuous Evaluation rules accept the prompt-agent kind used here. Hosted and
external agents were rejected in the live environment used during development.
The prompt agent declares the tool schema but does not host the Python tool
implementation, so `demo.py` performs the normal client-side Responses API
function-call loop.

## Setup resources

`setup_fleet()`:

1. inspects all three expected evaluation rules;
2. reuses their shared Eval ID when they agree;
3. refuses conflicting Eval IDs;
4. creates the Eval only when no fleet rule exists;
5. registers a new version of each named prompt agent;
6. creates or updates one rule per agent.

Inspecting all rules prevents a missing first rule from orphaning history that
is still referenced by another fleet rule.

## Telemetry prerequisites

The live setup required all of the following:

- an Application Insights connection on the Foundry project;
- Foundry User for the project identity;
- Monitoring Reader on Application Insights;
- Log Analytics Reader on the linked workspace;
- `AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING=true`;
- `configure_azure_monitor(..., credential=...)`;
- Monitoring Metrics Publisher for the identity exporting telemetry;
- content recording enabled so the evaluator receives the synthetic input and
  output.

The demo uses `azure-monitor-opentelemetry==1.8.10`. Application Insights has
local authentication disabled; telemetry export uses the supplied Azure
credential.

## Score correlation and completeness

Each synthetic topic produces a tool-call response and a final-answer response.
Only the final response ID is written to the window manifest.

For every agent, `fetch_fleet_results()` requires exactly one populated
groundedness result for every recorded final response ID. The window fails
closed when it finds:

- no expected IDs;
- duplicate IDs in the manifest;
- no rule or unreadable runs;
- a run ambiguously matching multiple expected IDs;
- multiple populated groundedness rows for one response;
- a duplicate score for one response;
- one or more missing response scores.

A nonempty subset is not a complete window.

## Evaluator schema

The observed criterion shape is:

```json
{
  "name": "groundedness",
  "passed": true,
  "score": 5.0,
  "threshold": 3
}
```

QLT-001 uses `passed` for the ungrounded-response count and preserves the raw
numeric score only for aggregation and the threshold-relative severe-item
check. It does not assume a fixed numeric scale.

`measure_agent()` also rejects missing, empty, or duplicate run IDs, booleans
where numeric values are expected, nonnumeric values, and nonpositive
thresholds.

## Deterministic policy

For each agent:

```text
ungrounded rate = failed groundedness results / complete final responses × 100
```

A review is required when any agent exceeds 5% or has a score at or below half
of that result's own pass threshold. The fleet average is descriptive only and
cannot suppress an individual breach.

Measurement failure produces `cannot_evaluate` and assigns AI Governance
Operations. A valid quality result assigns the Product Owner.

## Evidence and notifications

The git-ignored evidence record contains window and correlation identifiers,
per-agent counts and scores, fleet summary, policy version, decision, reason,
role, and notification state. It excludes prompts, full answers, KB content,
tokens, and webhook URLs.

A Teams response in the 2xx range means the workflow endpoint accepted the
request. It is not recorded as delivered until an operator supplies matching
workflow and message receipt identifiers through `record-delivery`.

## Self-reported confidence

The structured agent response includes a self-reported 1–5 confidence and
optional follow-up questions. This field is intentionally:

- displayed only;
- excluded from the evidence record;
- excluded from the policy;
- described as a UX experiment, not a groundedness measurement.

## Known SDK limitation

With `azure-ai-projects==2.3.0`, the non-streaming Responses instrumentation
path has reproduced an `AttributeError` involving a `NonRecordingSpan`. The
failure appears in an internal message-attribute helper without a recording
guard. It is not the same as the older closed issue that produced similar
symptoms.

This repository has not filed the finding upstream. Do not cite the closed
issue as proof of this still-live path.

## Cleanup

`infra/cleanup.py` verifies before deletion:

- exact agent names and prompt kind;
- optional recorded principal IDs;
- exact rule IDs and agent filters;
- one shared Eval with the exact QLT-001 name;
- exact resource IDs, types, prefixes, linkage, and ownership tags.

With `--confirm`, it deletes rules, agent sessions, agents, the Eval,
Application Insights, and Log Analytics. The shared Foundry project and resource
group are never targets. This complete cleanup path still requires live
validation before the control can be marked Validated.
