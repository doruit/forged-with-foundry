---
title: Upstream feedback draft — Continuous Evaluation and hosted agents
description: Draft status check and blocker evidence prepared while building QLT-001; not yet submitted anywhere. Review before sharing.
ms.date: 2026-09-25
---

> **Update (2026-09-25): `kind: prompt` agents ARE accepted — and the trace
> path was later confirmed working too; see the "Resolution pass" below,
> which supersedes this note's second sentence.** Everything below this note was
> written against a `kind: hosted` agent and still stands as-is for that
> kind. A follow-up session confirmed live, for a `kind: prompt` agent
> specifically, that `evaluation_rules.create_or_update()` succeeds (once
> three real prerequisites are met — see below), so hosted-agent parity is
> no longer the only path to Continuous Evaluation. But getting a real,
> continuously-sampled score requires the agent's traffic to actually reach
> Application Insights as an OpenTelemetry GenAI trace, and **no
> auto-instrumentation path we could find covers a prompt agent invoked via
> the Responses API** — this is the new, concrete gap worth raising.
>
> **Three real prerequisites for `evaluation_rules.create_or_update()` to
> succeed at all** (undocumented as a checklist anywhere we found; each one
> produces a different, non-obvious error until satisfied):
> 1. The project's managed identity needs the **Foundry User** role on the
>    project itself — without it: `403, "Principal does not have access to
>    API/Operation"` (message text alone doesn't say which role or scope).
> 2. The project needs a real Foundry **connection** resource of category
>    `AppInsights` (`Microsoft.CognitiveServices/accounts/projects/connections`,
>    API version `2026-07-15-preview`) — an Application Insights resource
>    merely *co-located* in the same resource group is not enough;
>    `client.connections.list()` stays empty until this connection actually
>    exists, and rule creation keeps failing with the same generic 403 above
>    until it does.
> 3. The managed identity also needs **Monitoring Reader** on the
>    Application Insights resource itself, in addition to (1).
>
> **The trace-path gap, precisely reproduced:** a real `kind: prompt` agent
> was registered, a real enabled `ContinuousEvaluationRuleAction` rule was
> attached to it, and 9 real responses were sent through it via
> `openai_client.responses.create(extra_body={"agent_reference": {...}})`
> (the only documented way to invoke a registered Foundry agent by name).
> Checked every plausible destination over multiple hours: the Evals API's
> `evals.runs.list(eval_id=...)` (0 runs), and every relevant Log Analytics
> table in the connected workspace, both classic Application Insights
> (`AppTraces`, `AppRequests`, `AppDependencies`, ...) and the newer OTel/
> GenAI-specific tables (`OTelSpans`, `OTelTraces`, `OTelResources`,
> `AppGenAIContent`) — all showed zero rows. Root-caused, not just observed:
> - `azure-ai-projects`'s own `client.telemetry.get_application_insights_connection_string()`
>   confirms tracing export is the *caller's* responsibility (it only reads
>   the connection string; it configures nothing).
> - Manually wiring `azure-monitor-opentelemetry`'s `configure_azure_monitor()`
>   plus `opentelemetry-instrumentation-openai-v2`'s `OpenAIInstrumentor` (the
>   standard, documented combination for auto-instrumenting an `openai`
>   Python client) still produced zero rows. Reading that instrumentor's own
>   source (`opentelemetry/instrumentation/openai_v2/__init__.py`, version
>   `2.3b0`, the latest available) confirms why: it only wraps
>   `openai.resources.chat.completions.Completions.create` and
>   `openai.resources.embeddings.Embeddings.create` — **it does not wrap
>   `openai.resources.responses.Responses.create` at all**, which is the
>   only API surface that accepts `agent_reference`.
> - Microsoft's own `agent_framework`/`agent_framework_foundry` packages do
>   implement their own first-party GenAI OTel spans (real code found in
>   `agent_framework/observability.py`, `_agents.py`, `_tools.py`), but only
>   around their own `Agent`/`FoundryChatClient` abstraction — and that
>   abstraction has no `agent_reference`/`agent_name` concept at all, so it
>   cannot invoke an already-registered prompt agent either; it only calls a
>   model deployment directly.
>
> Net: as of this check, there is no combination of currently-published
> Microsoft or community tooling that traces a registered Foundry agent's
> `responses.create(agent_reference=...)` call into Application Insights.
> Either the Responses API needs coverage added to
> `opentelemetry-instrumentation-openai-v2` (or an equivalent first-party
> instrumentor), or `agent_framework`'s client abstraction needs an
> `agent_reference` invocation mode that carries its existing tracing with
> it, or there is a different, not-yet-found supported mechanism entirely —
> worth asking the PG directly rather than guessing further.
>
> **Second verification pass (2026-09-25), specifically to rule out our own
> mistakes before calling this a product gap.** Searched for and found a
> detailed, code-level community writeup (Monu Mishra, DEV Community,
> "Observability in Microsoft Foundry: Tracing Agent Runs, Continuous
> Evaluation, and the OpenTelemetry Data Plane") that describes exactly this
> scenario and claims server-side tracing "requires zero code changes" once
> an Application Insights connection exists. Its own troubleshooting section
> names the single most common failure mode as a **missing `Log Analytics
> Reader` role**, not a broken pipeline — a role we had not granted (we had
> `Monitoring Reader` on the Application Insights resource, which is a
> different built-in role). We also noticed its sample invocation passes
> `model=` explicitly alongside `agent_reference`, which we had omitted.
> Re-tested with both corrections: granted `Log Analytics Reader` on the Log
> Analytics workspace itself (to both the project's managed identity and
> our own querying identity), and re-sent traffic with
> `openai_client.responses.create(model="<the agent's real model deployment
> name>", extra_body={"agent_reference": {...}})` (the article's own
> `model=agent.name` line is itself slightly wrong -- the service rejects it
> with `"Model must match the agent's model '<deployment>' when agent is
> specified"`, so `model` must be the underlying model deployment, not the
> agent's own name; corrected before retrying). Result: still zero rows in
> every table checked, over multiple additional minutes. This makes it a
> considerably better-evidenced report than the first pass -- a genuine,
> real-world community source's own documented remedy did not resolve it in
> our environment -- rather than a weaker one; if anything, this raises the
> next question for the PG a level, from "how do we enable this" to "why
> doesn't the documented enablement path work here."

> **Resolution pass (2026-09-25): the trace path does work — the real gap
> was two more undocumented auth requirements, plus one real SDK bug.**
> Correcting the "no working trace path" conclusion above: enabling
> `azure.ai.projects.telemetry.AIProjectInstrumentor` (a real, first-party
> instrumentor with a dedicated `_ResponsesInstrumentorPreview` for exactly
> this API surface — previously unchecked in this investigation) does trace
> a `responses.create(agent_reference=...)` call, once two further, also
> undocumented requirements are met:
>
> 1. **`AIProjectInstrumentor().instrument()` silently no-ops** unless the
>    environment variable `AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING=true` is
>    set (case-insensitive exact match) — no exception, just a warning and a
>    return. Message content additionally requires
>    `enable_content_recording=True` (or the
>    `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` env var).
> 2. Even with that instrumentor active and exporting, ingestion into this
>    project's Application Insights resource (provisioned with
>    `DisableLocalAuth: true`, a deliberate security setting on our side, not
>    a Microsoft default) 401'd until `configure_azure_monitor()` was called
>    with an explicit `credential=` argument rather than
>    `connection_string=` alone — the connection-string-only call path is
>    instrumentation-key auth, which this resource type rejects once local
>    auth is disabled.
> 3. Once Entra ID auth was flowing, ingestion still 403'd — traced to a
>    third, distinct built-in role: **Monitoring Metrics Publisher**
>    (`3913510d-42f4-4e42-8a64-420c390055eb`) on the Application Insights
>    resource, needed by whichever identity performs the *export*. This is
>    separate from `Monitoring Reader` and `Log Analytics Reader` above,
>    which only cover *reading* results back — three genuinely different
>    roles for three genuinely different operations (rule creation, reading
>    sampled traces, publishing traces), none of it consolidated in one
>    documented checklist anywhere we found.
>
> With all three satisfied, real content was confirmed landing in
> `AppGenAIContent` within roughly 1-2 minutes of a live
> `responses.create(agent_reference=...)` call, including populated
> `AgentName`, `InputMessages`, `OutputMessages`, and
> `gen_ai.operation.name: invoke_agent` / `gen_ai.response.id` attributes —
> real, usable groundedness-scoring input, not a partial or metadata-only
> row.
>
> **A genuine, reproducible SDK bug found along the way, worth raising
> directly with the PG:** `azure/ai/projects/telemetry/_responses_instrumentor.py`,
> in `_append_to_message_attribute` (around line 561), assumes every span
> passed to it is a recording span and calls `span.span_instance.attributes`
> unconditionally. When OpenTelemetry's own sampler decides not to record a
> given span (a `NonRecordingSpan`, a normal and expected outcome of
> sampling, not an error condition), this raises an unhandled
> `AttributeError: 'NonRecordingSpan' object has no attribute 'attributes'`
> that crashes the caller's request instead of being silently skipped, which
> is the correct handling for a non-recording span. Reproduced consistently
> on a request-by-request basis (not every request triggers it — only those
> the sampler chooses not to record), on `azure-ai-projects` 2.3.0.
>
> **A documentation/framing gap, separate from the bug:** community and
> Microsoft materials describing this as requiring "zero code changes"
> (see the DEV Community article cited above) describe the steady state
> once instrumentation is wired up, not the actual setup — reaching that
> steady state required explicit, non-default client-side code
> (`AIProjectInstrumentor().instrument(...)`, the experimental env var, and
> the `credential=` argument), none of which is "zero code" from a cold
> start, and none of which is gathered in one place across Microsoft's own
> docs. Whether Foundry's server side is expected to emit these traces
> independently of any client-side instrumentation at all (i.e., without the
> calling application doing anything) is still an open question worth
> putting to the PG directly — our reproduction only ever produced trace
> data once the client added this instrumentation itself.
>
> **Still open, not yet re-verified:** whether a live Continuous Evaluation
> rule's own async sampling/scoring job actually consumes this now-landing
> trace data and produces a real score. The rule created during the
> `kind: prompt` verification pass above no longer exists in this project at
> the time of this update (`evaluation_rules.list()` returns zero rows), so
> confirming the last link in the chain requires recreating a rule and
> waiting out its sampling cycle — not yet done as of this update.

> **Fourth pass (2026-09-25): recreated the rule against the real fleet,
> waited a full 20 minutes, still no score observed anywhere checked.** A
> fresh `Eval` (multi-criterion: `builtin.groundedness`, `builtin.relevance`,
> `builtin.retrieval`, each with `initialization_parameters.deployment_name`)
> and three real `ContinuousEvaluationRuleAction` rules (one per fleet
> agent — `EvaluationRuleFilter` matches a single agent name, so one rule
> cannot cover multiple agents) were created against this control's actual
> three-agent fleet (see README.md's fleet redesign). Real, complete
> conversational turns (tool call executed, final structured answer
> produced) were sent through every fleet agent with instrumentation active
> (`AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING=true`,
> `AIProjectInstrumentor().instrument(enable_content_recording=True)`,
> `configure_azure_monitor(credential=...)`), confirmed landing in
> `AppGenAIContent` as before. Then polled every 60 seconds for 20 minutes
> against two candidate read surfaces:
> - `openai_client.evals.runs.list(eval_id=...)` — stayed at 0 runs the
>   entire time. Notably, this call takes no agent-name or filter parameter
>   at all, so even if it did populate, it is unclear how a caller would
>   attribute a given run back to one specific fleet agent without opening
>   each run's own contents.
> - `AppGenAIContent` filtered to `isnotempty(EvaluationExplanation)` — this
>   column exists in the table's schema (structural evidence Microsoft
>   intends it to hold a sampled trace's evaluation result) but stayed empty
>   on every row checked, including rows generated after the rule was
>   attached and enabled.
>
> This is a real, disclosed gap, not a configuration mistake we can find:
> every prerequisite this document identifies (three IAM roles, one
> connection resource, a working instrumentation recipe, `kind: prompt`
> agents) is satisfied, real trace content demonstrably reaches Application
> Insights, and a real, enabled rule is attached to the exact agents that
> traffic went through — yet nothing resembling a groundedness score has
> appeared anywhere we can find, after 20 minutes. Rather than guess further
> at a third candidate location, this is the point to ask the PG directly:
> where does a `ContinuousEvaluationRuleAction` rule's actual computed score
> surface, and what is the expected latency from a real `responseCompleted`
> event to a queryable result? `demo.py`'s `fetch_fleet_results()` function
> (see README.md and `evaluator.py`) is written to fail closed —
> `cannot_evaluate` — for exactly this reason, and was itself confirmed live
> against this real, still-open condition rather than a hypothetical one.

> **Status: draft, not submitted.** Prepared while implementing
> [QLT-001 — Hallucination rate high](../README.md) in Forged with Foundry, an
> OSS collection of AI-governance control demos. Nothing in this document has
> been posted publicly or sent to Microsoft. Review and edit before sharing
> it anywhere, including a private or NDA channel.

> **Reframed after a second check (2026-09-23).** The first draft of this
> note called this a "feature request," as if hosted-agent support for
> Continuous Evaluation were an unrecognized gap. A follow-up search found
> Microsoft's own public statement that tracing and evaluations reached GA
> "with hosted agents coming soon" — so this is already an acknowledged,
> planned item, not a novel ask. Presenting it as a fresh feature request
> would overstate the finding and read oddly to a program manager who
> already knows about it. What is still genuinely useful below is (a) a
> concrete, reproducible account of today's failure mode, (b) a direct
> timeline/priority question, and (c) a real documentation gap (the
> exclusion is not mentioned on the how-to page itself). The rest of this
> document is written on that basis.

## Summary

**Continuous Evaluation rules currently reject `kind: hosted` agents outright**,
with an explicit server-side error, not a silent no-op or a degraded mode.
Microsoft has already stated hosted-agent support is "coming soon" for
Foundry tracing/evaluations generally, so this is not a request to build the
capability — it is (1) confirmation of exactly what today's failure looks
like, for anyone hitting it before that ships, and (2) a direct question
about timeline and whether early/preview access is possible for this
scenario.

## Expected vs. observed behavior

- **Expected:** A `Microsoft.CognitiveServices` continuous-evaluation rule
  (`EvaluationRule` with a `ContinuousEvaluationRuleAction`) can be attached
  to any agent the project can already run built-in or cloud evaluations
  against — including a hosted agent, since batch/on-demand evaluation
  against the same hosted agent already works today (see reproduction).
- **Observed:** Creating the rule fails with a structural `400 Bad Request`
  business-rule rejection, not a permissions or configuration error:

  ```text
  UserError: The evaluation rule request failed with bad request
  The agent '<hosted-agent-name>' is of kind 'hosted', which is not
  supported for evaluation rules. Hosted and external agents are not
  supported.
  Target: filter.agentName
  ```

## Classification

**Already-acknowledged, planned gap** ("hosted agents coming soon" per
Microsoft's own GA announcement), not a genuine surprise feature gap and not
a local configuration error or SDK defect. What remains worth raising is the
documentation gap (the exclusion isn't stated on the how-to page a builder
would actually read first) and the concrete reproduction below, which gives
a precise, current data point for a timeline/priority conversation.
Confirmed reproducible against a real, freshly-deployed `kind: hosted` agent
on both:

- `azure-ai-projects` 2.3.0 (the version pinned in this project), and
- `azure-ai-projects` 2.7.0 (current latest at the time of this report),

so this is not an SDK-version lag — the same rejection comes back from the
service on the newest available client.

## Smallest reproduction

1. Deploy any `agent_framework_foundry_hosting`-based hosted agent via
   `azd ai agent` (`kind: hosted` in `azure.yaml`) — any minimal
   tool-calling agent reproduces this; no specific business logic is
   required.
2. Confirm batch/on-demand evaluation already works against it:
   `azd ai agent eval generate --agent <hosted-agent-name> --evaluator builtin.groundedness ...`
   followed by `azd ai agent eval run` completes successfully and returns
   real per-criteria pass/fail results (this succeeded in our reproduction).
3. Attempt to make that same agent's live traffic continuously evaluated:

   ```python
   from azure.ai.projects import AIProjectClient
   from azure.ai.projects.models import (
       EvaluationRule, ContinuousEvaluationRuleAction, EvaluationRuleFilter,
   )

   client = AIProjectClient(endpoint, credential, allow_preview=True)
   client.evaluation_rules.create_or_update(
       "continuous-groundedness",
       EvaluationRule(
           display_name="Continuous groundedness",
           action=ContinuousEvaluationRuleAction(eval_id="<eval-id-from-step-2>", sampling_rate=100),
           filter=EvaluationRuleFilter(agent_name="<hosted-agent-name>"),
           event_type="responseCompleted",
           enabled=True,
       ),
   )
   ```

4. Step 3 fails with the `400` shown above. Step 2's own Eval definition
   (created against the same hosted agent) is accepted without complaint —
   only the continuous *rule* rejects the hosted agent kind.

No credentials, tenant identifiers, subscription IDs, or resource names from
the reproduction environment are included above; `<hosted-agent-name>` and
`<eval-id-from-step-2>` are placeholders.

## Relevant documentation and related issues

- [Observability in Microsoft Foundry: Tracing Agent Runs, Continuous
  Evaluation, and the OpenTelemetry Data Plane — DEV Community (Monu
  Mishra)](https://dev.to/monuminu/observability-in-microsoft-foundry-tracing-agent-runs-continuous-evaluation-and-the-4gp)
  is the detailed, code-level community writeup used for the second
  verification pass above: it describes the same `agent_reference` pattern,
  claims server-side tracing needs "zero code changes," and names `Log
  Analytics Reader` as the most common missing-role fix. Its own sample
  line `model=agent.name` does not work as written against the API version
  this control uses (see above); the rest of its RBAC and architecture
  claims did not resolve our reproduction either. Not an official Microsoft
  source, but the most concrete third-party account we found, which is why
  it was worth a direct, careful re-test rather than dismissal.
- Microsoft's own public statement (found via search, exact source page not
  confirmed by direct fetch) says tracing and evaluations reached GA "with
  hosted agents coming soon" — this is the basis for treating the gap as
  already acknowledged rather than novel. Please verify this against the
  actual GA announcement/release notes before treating it as authoritative;
  it was not independently confirmed by opening the source page directly.
- [Continuously Evaluate your AI agents — Microsoft Learn](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/continuous-evaluation-agents?view=foundry&preserve-view=true)
  and the [Generally Available: Evaluations, Monitoring, and Tracing in Microsoft Foundry](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/generally-available-evaluations-monitoring-and-tracing-in-microsoft-foundry/4502760)
  announcement describe Continuous Evaluation in general terms; we could not
  confirm the hosted-agent exclusion is stated on the how-to page itself —
  if it genuinely isn't, that's the real, remaining documentation gap: a
  builder reads "GA" and "coming soon" in different places and has no single
  page telling them not to try this yet on a hosted agent.
- [Quickstart: Evaluate your hosted agent — Microsoft Learn](https://learn.microsoft.com/en-us/azure/foundry/observability/quickstarts/quickstart-evaluate-hosted-agent)
  confirms batch/on-demand evaluation is an intentionally supported,
  documented path for hosted agents specifically — reinforcing that the gap
  is narrowly about the *continuous rule* mechanism, not evaluation of
  hosted agents in general.
- [azure-sdk-for-python#45941 — support hosted agents on the application-scoped endpoint](https://github.com/Azure/azure-sdk-for-python/issues/45941)
  is a related but distinct hosted-agent gap (conversation-history
  duplication on the application-scoped Responses endpoint), suggesting
  hosted-agent parity work is an active, ongoing area rather than settled.
  We did not find an existing issue specifically about evaluation rules
  rejecting hosted agents in the searches we ran; this may not yet be filed,
  but that search was not exhaustive.

## Recommended channel and action

- **Primary (this report's actual destination):** direct MVP/NDA channel to
  the Microsoft Foundry Observability program group, since the reporter has
  that relationship already. Framed as a status/timeline question plus
  supporting reproduction, not a cold feature pitch.
- **Public alternates, if a public trail is also wanted:** the
  [`microsoft-foundry` / `azure-ai-foundry` GitHub Discussions "Product
  Feedback and Ideas" category](https://github.com/orgs/azure-ai-foundry/discussions/categories/product-feedback-and-ideas),
  or [feedback.azure.com](https://feedback.azure.com). Lower value here than
  the direct channel, precisely because the capability is already publicly
  acknowledged as planned — a public post would mostly be re-stating that.
- **Recommended action:** ask, not request — (1) what is the current
  timeline for hosted-agent support in Continuous Evaluation rules, (2) is
  early/preview access available for this scenario, and (3) separately,
  flag the documentation gap (the exclusion isn't stated on the how-to page)
  as a quick, low-effort fix regardless of the timeline answer.

## Relationship to QLT-001 and current workaround

QLT-001 ("Hallucination rate high") originally assumed Continuous Evaluation
as its authoritative, always-on groundedness signal for a hosted agent — the
architecture Microsoft's own marketing for the capability describes. This
gap forced a pivot to periodic **batch evaluation** (`azd ai agent eval
generate` / `eval run` per measurement window) as the control's actual
signal source instead (see `ASSESSMENT.md` and `README.md` for the revised
design).

This workaround is a legitimate, still-real signal (same underlying
groundedness evaluator, same hosted agent, real pass/fail results) but masks
one thing Continuous Evaluation would have given for free: automatic,
always-on sampling without an explicit trigger to run each window's
evaluation. QLT-001's periodic batch runs must be triggered — by a human, a
script, or a scheduler — rather than happening on every live response by
default.
