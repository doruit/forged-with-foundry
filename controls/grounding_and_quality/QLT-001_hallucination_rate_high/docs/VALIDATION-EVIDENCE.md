---
title: QLT-001 validation evidence
description: The full real-run evidence behind the Validated status, and what it does and does not prove about the evaluator.
ms.date: 2026-09-27
---

# Validation evidence (2026-09-27)

This is the detailed evidence report behind the control README's `Validated`
status and its "What this demo does not prove" caveats. It is not required
reading to understand or run the demo -- see the [README](../README.md) for
that. Read this when you want the exact numbers, or when deciding whether to
trust this control's severity-override design for your own use.

## What was captured

All four requirements the README's Validation section lists were met by one
fresh run of the current fleet design, window 4, correlation
`cba18329-c890-42bc-b22a-e20952d6cc3c`:

1. **A complete window with exactly one score per recorded final response** —
   9 real responses (3 agents × 3 topics), all correlated, no missing or
   ambiguous results.
2. **A real `quality_review_required` decision** — reason
   `an_agent_breached_rate_or_critical_item`. Per-agent breakdown:

   | Agent | Responses | Ungrounded | Rate | Average score |
   |---|---|---|---|---|
   | Platform Team | 3 | 0 | 0% | 5.0 |
   | Regional Team | 3 | 0 | 0% | 5.0 |
   | Contractor Team | 3 | 1 | 33.3% | 4.0 |

3. **A current fleet-aware Product Owner card and verified delivery receipt** —
   HTTP 202 accepted, then marked `delivered` after an operator matched the
   Teams Workflow run ID and message ID against the actual posted card.
4. **Successful ownership-checked cleanup** — `infra/cleanup.py --confirm`
   deleted all three agents, their rules, the shared Eval, Application
   Insights, and the Log Analytics workspace; each was independently
   re-queried afterward and confirmed absent. The shared Foundry project and
   resource group were untouched.

## What this run does and does not show about the evaluator

Before this run, an earlier real window (window 3, 2026-09-25) came back
`no_review_required`: every response, including the Contractor Team's
confident fabrications, scored as fully grounded. The tool's "no article"
result was then a bare token with no content for a groundedness check to
weigh the answer against. It was changed to explicit natural-language text
naming the exact claim categories (VPN client, portal URL, approval policy,
ticket queue, renewal cadence) as undocumented, so a confident, specific
fabrication in those categories now contradicts real premise text instead of
filling an information void (see [workload.py](../workload.py) and
[agent.py](../agent.py)).

That change is why window 4 produced a real breach — but only 1 of the
Contractor Team's 3 fabricated answers was actually scored ungrounded; the
other 2 (equally confident, equally unsupported) still scored as fully
grounded. **The evaluator did not become reliable at catching confident
fabrication; the fleet-level rate threshold caught what one individual
result would not have.** A previously observed deliberately fabricated
answer receiving a perfect groundedness score is not an isolated fluke — it
is this run's own majority outcome for the same agent. This limitation must
remain visible in any future retest or reuse of this design.

## Is the critical-severity path reachable at all?

The policy has a second trigger besides the rate threshold: any single
result scoring at or below 50% of its own pass threshold (`evaluator.py`'s
`CRITICAL_RATIO`). Window 4's real breach came from the rate threshold only
(`critical_run_ids` was empty for every agent) — so is the critical path
reachable with this fleet design at all, or only in principle?

Testing that live would mean another ~24h Continuous Evaluation cycle per
attempt. Azure AI Evaluation SDK's `GroundednessEvaluator` can call the same
real judge deployment (`gpt-5-mini`) synchronously instead, in seconds, so
six real judge calls were run directly against increasingly aggressive
Contractor-style fabrications before committing to another real window:

| Fabrication style | Topic | Score | Critical (≤1.5)? |
|---|---|---|---|
| Confident, on-topic (matches window 4's real answer) | vpn_setup | 2.0 | No |
| Maximally specific (product+version, URL, ticket ID, contact, SLA) | vpn_setup | 2.0 | No |
| False authority ("per the official KB article...") | vpn_setup | 2.0 | No |
| False authority, dense | password_reset | 2.0 | No |
| False authority, dense | license_renewal | 2.0 | No |
| Off-topic, non-responsive | vpn_setup | **1.0** | **Yes** |

On-topic confident fabrication — the exact failure mode this control
targets — floored at 2.0 across every style and topic tried. The only style
that reached the critical band was one that did not address the question at
all.

**What this means for how this control should be used:** the critical-item
override is not a dependable safety net for the highest-risk pattern this
control is meant to catch (a plausible, specific, confidently wrong answer).
This is not an incidental gap: `builtin.groundedness` scores against five
fixed, qualitatively defined levels, not a continuous scale, and every
on-topic-but-wrong answer falls into the same level 2 by definition,
regardless of how wrong it is -- only a non-responsive, off-topic answer
reaches the level below it. See
[docs/IMPLEMENTATION.md](IMPLEMENTATION.md#groundedness-is-a-composite-five-level-rubric-not-a-continuous-score)
for the exact rubric, read directly from the judge SDK. The fleet-level
rate threshold, not the critical-item override, is what actually caught the
real breach above, and should be treated as the primary lever against
confident fabrication; do not rely on the critical override to catch it.

This is real judge-model evidence, not a mocked test, though obtained via a
direct synchronous call to the same judge deployment rather than through
Continuous Evaluation's own asynchronous sampling path -- treat it as a
strong, live-corroborated signal about this evaluator's behavior on this
scenario, not a guarantee that every invocation path scores identically.
