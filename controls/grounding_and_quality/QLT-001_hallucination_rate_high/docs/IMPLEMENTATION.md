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

### A real, still-live, unfiled Microsoft SDK bug in the non-streaming tracing path

**Corrected 2026-09-25** (see `ASSESSMENT.md` revision note 6): this was
first misattributed to
[azure-sdk-for-python#46544](https://github.com/Azure/azure-sdk-for-python/issues/46544),
which describes a similar-looking crash. Re-checking before this control's
public announcement found that issue is actually **closed as fixed**
(2026-06-12, shipped in `azure-ai-projects` 2.2.0) — confirmed by reading
the installed 2.3.0 package's source: every one of the 15 call sites #46544
named now correctly calls `is_recording()` as a method.

The real, still-reproducible bug is different, in the same file:
`_ResponsesInstrumentorPreview._append_to_message_attribute` (around line
561 in the installed 2.3.0 package) has no `is_recording()` guard of its
own — it unconditionally reads `span.span_instance.attributes`. Its callers
in `trace_responses_create`/`trace_responses_create_async` (the
**non-streaming** `responses.create()` path — the one this control's
`demo.py` actually calls) invoke it with no guard either, unlike the
streaming cleanup path in the same file, which does check
`is_recording()` first. Confirmed by direct reproduction: constructing a
real `NonRecordingSpan` (via `opentelemetry.trace`, wrapped in
`azure.core.tracing.ext.opentelemetry_span.OpenTelemetrySpan`) and calling
`_append_to_message_attribute` on it raises the identical
`AttributeError: 'NonRecordingSpan' object has no attribute 'attributes'`
on the currently-installed package — no live Azure call needed to
reproduce it. This is a genuinely new, unfiled bug that happens to produce
the same error text as the old, already-fixed one; searched for an
existing report of it specifically and found none. Not filed by this
project — per this repository's `upstream-contributions.local.instructions.md`,
filing requires the user's explicit approval.

## Assumed per-item result schema, borrowed from batch mode and not yet confirmed for Continuous Evaluation

**This is an assumption, not a confirmed fact about Continuous Evaluation.**
`evaluator.py`'s per-agent aggregation (`measure_agent`) expects the same
per-criterion shape observed from **batch-mode** evals (confirmed live
2026-09-23, before this control switched to Continuous Evaluation). Since
Continuous Evaluation has never returned a real score on any run (see
"Known gap" below), whether its actual result payload uses this same
`passed`/`score`/`threshold` shape, a different structure entirely, or lives
in a different field than `EvaluationExplanation`, is genuinely unknown.
Treat `measure_agent`'s current implementation as a best guess to be
corrected once a real populated result is finally observed, not as a
verified integration:

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

## Resolved: Continuous Evaluation's own computed score, and how to read it

**Confirmed live 2026-09-25** (see `docs/UPSTREAM-FEEDBACK.md`'s "Fifth
pass"): the real read path is the same `openai_client.evals.runs`/
`output_items` API batch evaluation already used — not the
`AppGenAIContent`/`EvaluationExplanation` Log Analytics column an earlier
pass suspected (that column is still empty; it was never the real path).
The missing piece was latency: real scores took roughly a day to appear,
not the 20 minutes originally tested.

`fetch_fleet_results()` correlates each fleet agent to its own eval by
looking up `client.evaluation_rules.get(f"{agent_id}-rule").action.eval_id`
(a shared `Eval` can have multiple attached rules, so this is looked up
per agent, not assumed to be one fixed id), then matches real runs to this
window's own recorded `resp_...` ids via each run's
`data_source.item_generation_params["source"]["content"]` — note
`item_generation_params` is a plain dict, not an attribute-accessible
model, unlike `data_source` itself. Each real tool-calling conversation
produces **two** `responseCompleted` events (the tool-call-only turn, then
the final answer); only the final-answer run has a populated `groundedness`
result, so the tool-call-only run's `null` result is filtered out rather
than treated as a failure.

**A real, separate bug this surfaced, now fixed:** `setup_fleet()` used to
call `openai_client.evals.create()` unconditionally on every invocation,
creating a brand-new `Eval` each time. Since each agent's rule points at
one specific `eval_id`, re-running `setup` (for example, after an
instructions change) silently repointed every rule at the new `Eval`,
orphaning all of the previous `Eval`'s real historical runs — with no
error, and no way to tell without specifically checking. `setup_fleet()`
now reuses an already-attached rule's own `eval_id` if one exists, and
only creates a new `Eval` on a genuine first-ever setup. This was found the
hard way: a routine mid-session re-run to update the Contractor Team's
instructions orphaned that day's real Continuous Evaluation history before
the fix landed.

`demo.py history --agent <agent_id>` reads every real, scored result for
one fleet agent across all time (not scoped to one window, unlike
`fetch_fleet_results`) and `evaluator.daily_trend()` buckets it by day —
the real, multi-day view `README.md`'s "Further exploration" describes.
