---
title: Upstream feedback draft — Continuous Evaluation and hosted agents
description: Draft status check and blocker evidence prepared while building QLT-001; not yet submitted anywhere. Review before sharing.
ms.date: 2026-09-23
---

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
