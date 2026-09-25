# QLT-001 — control assessment

> **Assessment outcome:** COMPOSE  
> **Implementation status:** Implemented, not Validated  
> **Reviewed:** 2026-09-25

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

## Evidence assessment

| Claim | Current evidence | Assessment |
|---|---|---|
| Prompt-agent fleet can be registered | Live operator observation, 2026-09-25 | Observed; no current screenshot retained |
| Synthetic traffic reaches Application Insights | Live operator observation | Observed; no current screenshot retained |
| Continuous Evaluation results are readable | Live result shape informed parser and tests | Observed |
| Partial evidence fails closed | Automated tests | Reproducible |
| Teams accepts a measurement-failure notification | HTTP 202 from live run | Observed; acceptance is not delivery |
| Current fleet triggers a quality review | None | Not demonstrated |
| Cleanup removes all control-owned state | Implemented with ownership checks | Requires live validation |

Historical single-agent batch screenshots were removed because they did not
prove the current fleet/Continuous Evaluation architecture.

## Key limitations and risks

- Groundedness is support-by-context, not truth or correctness.
- The evaluator is model-based and can miss polished unsupported answers.
- A deliberately fabricated answer previously received a perfect groundedness
  score; this limitation must remain visible.
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

Publication is acceptable as an **Implemented** community demo only when
repository CI is green and the README keeps the evidence gaps explicit.

The control may become **Validated** only after a fresh run of the current
architecture captures a real quality-review decision, verified Teams delivery,
and successful full cleanup.
