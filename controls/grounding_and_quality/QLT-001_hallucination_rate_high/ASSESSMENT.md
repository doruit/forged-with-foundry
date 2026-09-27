# QLT-001 — control assessment

> **Assessment outcome:** COMPOSE  
> **Implementation status:** Validated  
> **Reviewed:** 2026-09-27

## Candidate

| Field | Decision |
|---|---|
| Control ID | QLT-001 |
| Catalog name | Hallucination rate high |
| Lifecycle | Live |
| Accountable role | Product Owner |
| Model/Foundry role | Monitored workload |
| Demo format | Hybrid demo |

## Governance problem

An agent can continue producing fluent answers after its supplied context
becomes incomplete or stale. Without a measured signal and an accountable
review path, unsupported answers can remain invisible.

The catalog name uses “hallucination,” but no single groundedness evaluator
establishes factual truth. The implemented operational signal is the share of
responses that Foundry's groundedness evaluator marks as unsupported by their
supplied context. QLT-001 treats that as a proxy for hallucination risk.

## Capability review

| Capability | Use | Reason |
|---|---|---|
| Microsoft Foundry prompt agents | Core | Real monitored workload; supported by Continuous Evaluation rules |
| Foundry Continuous Evaluation | Core | Supplies the independent per-response groundedness result |
| Application Insights and Log Analytics | Core | Carry sampled traces required by Continuous Evaluation |
| Teams Workflows | Core | Routes review and measurement-failure notifications |
| Agent Control Specification | Not used | The decision is asynchronous and window-based, not an inline intervention |
| Azure AI Content Safety groundedness filter | Not used | It is an inline response filter; QLT-001 demonstrates asynchronous fleet monitoring |
| Custom LLM evaluator | Rejected | Would duplicate the supported Foundry evaluator |
| Custom policy code | Minimal gap | Foundry supplies scores but not this fleet-level threshold, completeness, routing, and evidence policy |

## Contribution decision

**COMPOSE.** The distinct learning outcome is not how to build another
groundedness evaluator. It is how to turn supported evaluator results into an
accountable governance decision:

1. correlate each asynchronous result to a recorded final response;
2. require complete, unique evidence for every expected response;
3. calculate a per-agent failure rate;
4. prevent a fleet average from hiding one degraded agent;
5. route quality findings and measurement failures to different owners.

## Authoritative path

| Responsibility | Authority |
|---|---|
| Signal | Foundry Continuous Evaluation `builtin.groundedness` |
| Decision | Deterministic QLT-001 policy in `evaluator.py` |
| Evidence | Minimized window record in the local git-ignored control state |
| Governance action | Tenant-authenticated Teams Workflow |

The response's self-reported confidence is deliberately outside this path. It
is an untrusted UX hypothesis, not evidence and not an approval signal.

## Scenarios

| Window | Fleet condition | Expected policy behavior |
|---|---|---|
| 1–2 | All three agents have current KB content | No review if all authoritative results pass |
| 3–4 | Regional and Contractor KBs degrade; their instructions differ | Review if any agent breaches; otherwise retain evaluator limitation as evidence |
| Any | One expected score is absent, duplicate, ambiguous, or malformed | `cannot_evaluate`; notify AI Governance Operations |

The Contractor Team is intentionally instructed to answer confidently when its
article is missing. This is synthetic adversarial behavior used only to test
the evaluator and control path.

## Threshold assessment

The catalog threshold is >5%. A demo window contains three final responses per
agent, so one failed result equals 33.3%. The threshold is therefore useful for
showing deterministic mechanics but is not statistically calibrated.

A production implementation must set a minimum sample size, calibrate the
threshold against labeled data, and define the measurement period before using
the result as an SLO or risk appetite statement.

The severe-item override compares a score with half of that result's own pass
threshold. It avoids hard-coding an evaluator scale, but it remains an
evaluator-derived severity signal—not a human-confirmed critical
hallucination.

Tested live (2026-09-27) with six direct, synchronous calls to the real
judge deployment (`gpt-5-mini`, via Azure AI Evaluation SDK's
`GroundednessEvaluator`, bypassing the ~24h Continuous Evaluation wait): the
override did not fire for any on-topic confident fabrication, however
specific or falsely authoritative, across all three synthetic topics — every
one scored 2.0, above the 1.5 critical cutoff. It fired only for an
off-topic, non-responsive answer (1.0). The rate threshold, not this
override, is what caught the real breach in window 4. Treat the override as
tuned to a different failure mode (non-responsiveness), not as a safety net
for confident fabrication — see README.md's Validation section for the full
comparison table.

## Evidence assessment

| Claim | Current evidence | Assessment |
|---|---|---|
| Prompt-agent fleet can be registered | Live operator observation, 2026-09-25 | Observed; no current screenshot retained |
| Synthetic traffic reaches Application Insights | Live operator observation | Observed; no current screenshot retained |
| Continuous Evaluation results are readable | Real window `cba18329`, 9/9 responses correlated, 2026-09-27 | Observed |
| Partial evidence fails closed | Automated tests | Reproducible |
| Teams accepts and operator verifies a quality-review notification | HTTP 202, then `delivered` via matched Teams Workflow run ID and message ID, 2026-09-27 | Observed; delivery verified, not just accepted |
| Current fleet triggers a quality review | Real window `cba18329`: `quality_review_required`, Contractor Team 1/3 ungrounded (33.3%), 2026-09-27 | Demonstrated |
| Cleanup removes all control-owned state | `--confirm` run against the same deployment; every target independently re-queried and confirmed absent, 2026-09-27 | Demonstrated |

Historical single-agent batch screenshots were removed because they did not
prove the current fleet/Continuous Evaluation architecture.

## Key limitations and risks

- Groundedness is support-by-context, not truth or correctness.
- The evaluator is model-based and can miss polished unsupported answers.
- Confirmed on the real breach captured 2026-09-27: only 1 of the Contractor
  Team's 3 confidently fabricated answers was scored ungrounded; the other 2
  scored as fully grounded. The fleet-level rate threshold caught the
  breach, not evaluator reliability at detecting individual fabrication.
  This limitation must remain visible.
- The critical-item severity override does not reliably catch confident
  fabrication either: six live judge-model tests (2026-09-27) all scored
  on-topic fabrications at 2.0, never at or below the 1.5 critical cutoff,
  regardless of specificity. It fired only for a non-responsive, off-topic
  answer. See [Threshold assessment](#threshold-assessment).
- Scores arrive asynchronously and may take roughly a day.
- Programmatic evaluation configuration currently uses a preview-enabled SDK
  surface even though Continuous Evaluation is presented as a product
  capability.
- Content recording stores the synthetic prompt and response in Azure Monitor.
- The current SDK's non-streaming tracing path has reproduced a
  `NonRecordingSpan` crash. Publication must describe it as a known SDK
  limitation without misattributing it to a closed issue.
- The UX confidence/follow-up experiment has no demonstrated causal effect on
  later groundedness.

## Security and privacy

Only synthetic content is permitted. Azure CLI credentials are used for client
calls. Teams URLs remain local and git-ignored. Evidence and cards exclude raw
content, while Azure Monitor intentionally retains the synthetic content
needed for evaluation.

The Bicep template grants:

- Foundry User to the project identity;
- Monitoring Reader on Application Insights;
- Log Analytics Reader on the workspace;
- Monitoring Metrics Publisher to the identity exporting telemetry.

These are distinct read, configuration, and ingestion responsibilities.

## Implementation boundary

Included:

- three prompt agents and synthetic KB profiles;
- Continuous Evaluation rules;
- telemetry instrumentation;
- complete per-response correlation and deterministic rollup;
- separate Teams routes;
- ownership-checked cleanup.

Excluded:

- automatic KB or prompt remediation;
- inline blocking or correction;
- production scheduling;
- threshold calibration;
- factual correctness verification;
- a user-facing application.

## Release decision

Publication is acceptable as a **Validated** community demo now that
repository CI is green and a fresh run of the current architecture (window 4,
correlation `cba18329-c890-42bc-b22a-e20952d6cc3c`, 2026-09-27) captured a
real `quality_review_required` decision, operator-verified Teams delivery,
and successful full cleanup with independently confirmed resource absence.
The README keeps the evaluator's demonstrated blind spot (2 of 3 Contractor
Team fabrications still scored as grounded in that same run) explicit
alongside this result.
