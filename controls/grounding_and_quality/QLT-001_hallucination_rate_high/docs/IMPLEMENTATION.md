---
title: QLT-001 implementation notes
description: How the fleet of kind:prompt agents, Continuous Evaluation, and the deterministic fleet-rollup policy fit together, the full IAM/instrumentation recipe Continuous Evaluation actually needs, and what is still unverified pending Microsoft's answer on the score-read path.
ms.date: 2026-09-25
---

## Why `kind: prompt`, and why Continuous Evaluation now works

`ASSESSMENT.md` records the full history of this decision (revision notes
1-5); this section is the technical how, not the history. In short: a real
deployment first showed `client.evaluation_rules.create_or_update()` rejects
`kind: hosted` and `kind: external` agents outright (`400 UserError: ... is
not supported for evaluation rules`), which pivoted this control to batch
evaluation for a time (see `docs/UPSTREAM-FEEDBACK.md`'s original findings).
A later session, prompted by this repository's maintainer asking for a
websearch on which deployment pattern actually supports Continuous
Evaluation, found and confirmed live that **`kind: prompt` agents are
accepted**. A `PromptAgentDefinition` (see `agent.py`) is server-side-only:
it can declare a `FunctionTool` schema, but cannot execute the underlying
Python itself — `demo.py` runs the client-side tool-call loop the Responses
API's function-calling contract already requires of any caller (send the
conversation, execute the tool locally when requested, send the result
back), not a QLT-001-specific mechanism.

## Core path: registering the fleet and its Continuous Evaluation rules

1. Deploy the shared infrastructure (`azd up`, see README.md "Deploy") — the
   Log Analytics workspace, Application Insights, the Foundry project's
   `AppInsights` connection, and the IAM roles below.
2. Register the fleet and its rules in one step:

   ```zsh
   .venv/bin/python demo.py setup
   ```

   `setup_fleet()` (in `demo.py`) creates one shared `Eval` definition
   (`builtin.groundedness`, `builtin.relevance`, `builtin.retrieval`, each
   requiring `initialization_parameters: {"deployment_name": "<model>"}` —
   confirmed live: omitting it fails with `400 MissingRequiredParameter`),
   registers each of the three `workload.FLEET` profiles as its own
   `kind: prompt` agent (`agent.register_agent()`), and attaches one
   `EvaluationRule`/`ContinuousEvaluationRuleAction` per agent —
   `EvaluationRuleFilter` matches a single agent name, so one rule cannot
   cover multiple fleet members.

### The four prerequisites Continuous Evaluation needs beyond the rule itself

None of these are mentioned together in one place in Microsoft's own
documentation; each was found by reproducing a distinct real error live
(see `docs/UPSTREAM-FEEDBACK.md` for the exact error text and dates):

1. **`Foundry User` role** (`53ca6127-db72-4b80-b1b0-d745d6d5456d`) on the
   Foundry project, for the project's managed identity — without it,
   `evaluation_rules.create_or_update()` 403s even for an accepted
   `kind: prompt` agent.
2. **A real Foundry `connection` resource of category `AppInsights`**
   (`Microsoft.CognitiveServices/accounts/projects/connections`, API version
   `2026-07-15-preview`) — an Application Insights resource merely
   *co-located* in the same resource group is not enough;
   `client.connections.list()` stays empty and rule creation keeps 403ing
   with a generic "Principal does not have access to API/Operation" until
   this connection actually exists.
3. **`Monitoring Reader` role** (`43d0d8ad-25c7-4714-9337-8ba259a9fe05`) on
   the Application Insights resource, in addition to (1) — without it, the
   same generic 403 persists even with the connection in place.
4. **`Log Analytics Reader` role** (`73c42c96-874c-492b-b04d-ab87d138a893`)
   on the Log Analytics workspace — distinct from (3); needed to read
   sampled results back out, not to create the rule.

All four are declared in `infra/main.bicep` for the project's managed
identity (`foundryProjectPrincipalId`).

### The telemetry recipe: getting real trace content into Application Insights at all

Confirmed live (2026-09-24/25): none of this is automatic, and skipping any
one piece results in silent zero rows everywhere, with no exception raised.
`demo.py`'s `instrument()` function does all three together:

1. **`AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING=true`** — without this exact
   env var,
   `azure.ai.projects.telemetry.AIProjectInstrumentor().instrument()` logs a
   warning and returns immediately, with no effect and no exception.
2. **`configure_azure_monitor(connection_string=..., credential=...)`** —
   this control's Application Insights resource has `DisableLocalAuth: true`
   (see `infra/main.bicep`), so ingestion requires Entra ID token
   authentication. Calling `configure_azure_monitor` with only
   `connection_string=` (the connection-string/instrumentation-key auth
   path) 401s; passing `credential=` explicitly is what makes ingestion
   authenticate correctly.
3. **`Monitoring Metrics Publisher` role**
   (`3913510d-42f4-4e42-8a64-420c390055eb`) on the Application Insights
   resource, for whichever identity actually performs the export — a fourth
   role, distinct from the three IAM roles above (those cover *reading*;
   this covers *publishing*). Without it, ingestion authenticates
   successfully via Entra ID but still 403s.

With all three satisfied, real content (`AgentName`, `InputMessages`,
`OutputMessages`, `gen_ai.operation.name: invoke_agent`) lands in Log
Analytics's `AppGenAIContent` table within roughly 1-2 minutes of a real
`responses.create(agent_reference=...)` call — confirmed by direct
inspection of real rows.

### A real, pre-existing Microsoft SDK bug found along the way

`azure/ai/projects/telemetry/_responses_instrumentor.py`'s
`_ResponsesInstrumentorPreview` checks `span.span_instance.is_recording`
without calling it (`is_recording` is a method, not a property), so the
check is always truthy and the code falls through to
`span.span_instance.attributes` on a `NonRecordingSpan` (a normal outcome of
OpenTelemetry sampling), crashing with `AttributeError: 'NonRecordingSpan'
object has no attribute 'attributes'`. Reproduced independently while
building this control; already filed as
[azure-sdk-for-python#46544](https://github.com/Azure/azure-sdk-for-python/issues/46544)
— not something this project needs to file itself, per this repository's
"prefer adding evidence to an existing issue" upstream-contribution rule.

## Confirmed real per-item result schema, reused from batch mode

`evaluator.py`'s per-agent aggregation (`measure_agent`) expects the same
per-criterion shape Continuous Evaluation's underlying evaluators share with
their batch-mode counterparts, confirmed live (2026-09-23, against real
batch-mode runs, before this control switched to Continuous Evaluation):

```json
{
  "passed": true,
  "score": 0.7413793103448276,
  "threshold": 0.5,
  "reason": "..."
}
```

The numeric range is evaluator-specific — one observed run used a 0.0-1.0
scale, another showed `builtin.groundedness` using roughly 1.0-4.0 for the
same named criterion — confirming the scale must never be hardcoded.
`evaluator.py`'s critical-item override compares each item's own `score`
against its own `threshold` (`score <= threshold * 0.5`) for exactly this
reason, so the same rule is correct regardless of which evaluator scale is
configured.

## Known gap: Continuous Evaluation's own computed score has not been found anywhere yet

This is the one part of the design that is **not** confirmed working, despite
every prerequisite above being satisfied and real trace content confirmed
reaching Application Insights. `demo.py`'s `fetch_fleet_results()` was
written to fail closed for exactly this reason:

- `openai_client.evals.runs.list(eval_id=...)` stayed at 0 runs after 20
  minutes of polling against real, rule-attached traffic. This call also
  takes no agent-name filter at all, so even if it populated, attributing a
  run back to one specific fleet agent is unclear without opening each run's
  own contents.
- `AppGenAIContent`'s `EvaluationExplanation` column exists in the table's
  schema (structural evidence Microsoft intends it to hold a sampled trace's
  evaluation result) but stayed empty on every row checked, including rows
  generated after a real, enabled rule was attached.

`fetch_fleet_results()`'s body is intentionally left unimplemented beyond
this check — it queries for a populated `EvaluationExplanation` and returns
`complete=False` when it finds nothing, rather than guessing at a parsing
format never actually observed. Update it once a real populated row is
found and its shape is known; see `docs/UPSTREAM-FEEDBACK.md`'s "Fourth
pass" for the full, dated repro, and README.md "Known limitations" for how
this affects the control's `Implemented`-not-`Validated` status.
