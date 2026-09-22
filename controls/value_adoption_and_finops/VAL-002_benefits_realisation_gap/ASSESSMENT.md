---
description: "Assessment for a milestone value-hypothesis realisation check, distinct from VAL-001's continuous operational monitoring"
---

# VAL-002 - control assessment

## Candidate

- **Control ID:** VAL-002
- **Name:** Benefits realisation gap
- **Lifecycle phase:** Live
- **Accountable role:** Business Owner

## Governance problem

- **Risk:** VAL-001 catches sustained short-term underperformance (two
  consecutive periods below 80% of target), but an agent can pass that check
  indefinitely — never two bad periods in a row — while still cumulatively
  realizing far less benefit than the business case promised. Nobody ever
  asks, at the milestone the business case itself declared, whether the
  original value hypothesis (VAL-PRE-001) ever actually worked. Without this
  control, a persistently mediocre agent is invisible to VAL-001's rolling
  window and nobody is ever asked to reassess the hypothesis itself, only to
  "review" isolated bad patches.
- **Control objective:** Compare the agent's *aggregate, cumulative* measured
  KPI performance across the declared realisation window against the target
  already declared in VAL-PRE-001, and trigger a Business Owner
  **hypothesis reassessment** — a stronger, business-case-linked action than
  VAL-001's "value review" — the first time cumulative realized performance
  falls below 50% of target at the end of that window.
- **Authoritative signal:** the same two streams VAL-001 established, read
  the same way: Stream A is `.fwf/agents/helpdesk-tier1-triage/governance.yaml`'s
  VAL-PRE-001 entry (`metric.name`, `metric.target`, `metric.direction`,
  `owner`, `businessCaseId`) — read-only, never redeclared here. Stream B is
  the same real Application Insights `TicketTriaged` telemetry the hosted
  Foundry agent emits, queried via KQL — but **aggregated over the full
  declared window** (pooled counts across every period), not a two-period
  rolling check.
- **Required decision:** Has the aggregate measured Stream B rate across the
  full declared realisation window fallen below `target * 0.5`?
- **Required governance action:** For `reassess_required`, write a structured
  evidence record and notify the Business Owner, explicitly referencing the
  VAL-PRE-001 `businessCaseId` and framed as "reassess the value hypothesis,"
  not a routine review. For `cannot_evaluate`, notify AI Governance
  Operations, same as VAL-001. Both are detect-and-escalate actions, not
  blocking gates — a Live-phase value control still cannot halt a running
  agent.
- **Required evidence:** metric name, declared target, the 50% threshold, the
  aggregate realized rate, the number of periods covered and the declared
  window length, the Business Owner and `businessCaseId` (read from the same
  governance contract entry VAL-001 reads), and a timestamp.

## Enforcement classification

- **Deterministic policy:** Plain Python evaluator: read target from the
  governance contract (same shared read path as VAL-001), query Log
  Analytics for every period within the declared window, pool
  `deflected / total` across all of them, compare the pooled rate to
  `target * 0.5`. No model or LLM call is part of this decision.
- **Model-assisted evaluation:** Not applicable to the decision itself; see
  Model/Foundry role.
- **Human approval:** Not applicable — detection and escalation, not an
  approval-gated action. The Business Owner's reassessment in response is an
  out-of-band process this control does not model, same posture as VAL-001
  and VAL-PRE-001.
- **Configuration assessment:** Not applicable.
- **Monitoring/detection:** The primary mechanism, same as VAL-001, but
  evaluating a cumulative window instead of a rolling one.
- **Required fail-closed behavior:** If Stream A's target cannot be read, or
  fewer than the declared number of periods of Stream B telemetry exist yet,
  the evaluator must report an explicit `cannot_evaluate`, never a healthy or
  a reassess-required result — an absent or incomplete signal must never be
  mistaken for either outcome.
- **Model/Foundry role:** **Monitored workload**, same posture as VAL-001 and
  for the same reason: a real hosted Microsoft Agent Framework agent performs
  synthetic helpdesk work; only executed and independently verified synthetic
  resolutions count as deflected; periodic deterministic monitoring evaluates
  these outcomes asynchronously. No ACS gate or explanatory agent belongs in
  the core path — this control changes the evaluation window and the
  governance action, not the enforcement posture.

## Existing capability review

| Capability | Applicable? | What it already provides | Role in the core demo or reason not used |
|---|---:|---|---|
| Microsoft Agent Governance Toolkit | No | Approval workflows | Not applicable — no approval action in this control's path, same as VAL-001. |
| Agent Control Specification | No | Tool/model intervention points | This control evaluates aggregated telemetry across a whole window, not an inline action, same reasoning as VAL-001. |
| Microsoft Foundry | Yes, if deployed | Hosted agent runtime, Agent Framework | Already proven live by VAL-001. If this control deploys its own instance, it demonstrates nothing new about the integration itself — see Proposed contribution for the resulting format question. |
| Foundry Control Plane | No | Agent governance surface | Not needed beyond standard hosted-agent deployment, same as VAL-001. |
| Azure API Management AI Gateway | No | Model/tool traffic gating | Not applicable — same reasoning as VAL-001. |
| Microsoft Purview | No | Data governance cataloguing | Not applicable to this control's signal. |
| Microsoft Defender | No | Threat protection | Not applicable. |
| Microsoft Entra | Yes, if deployed | Managed identity for hosted agent and evaluator queries | Same reuse rationale as VAL-001 if a live deployment is chosen. |
| Azure AI Content Safety / Language | No | Content moderation | Not applicable to this control's signal. |
| Azure Monitor / Application Insights / OTel | Yes | Telemetry ingestion, custom events, KQL query | This is Stream B, already proven live by VAL-001 against the identical event shape (`TicketTriaged`). |
| Other supported Microsoft capability | Yes, if deployed | Microsoft Teams Workflows (Power Automate) | Same notification mechanism as VAL-001, reused rather than re-verified. |

## Existing samples and implementations

| Repository, documentation, or sample | Overlap | What is still missing |
|---|---|---|
| `controls/value_adoption_and_finops/VAL-001_kpi_underperformance` | Near-total mechanical overlap: same hosted agent, same telemetry event shape, same governance-contract read path, same evidence-binding shape, same Teams notification mechanism. | The aggregate/cumulative-window evaluation (VAL-001 is hardcoded to exactly 2 rolling periods and an 80% threshold); the 50%-of-target milestone threshold; the `reassess_required` decision and its distinct hypothesis-reassessment framing tied to `businessCaseId`, versus VAL-001's routine "value review." |
| `controls/value_adoption_and_finops/VAL-PRE-001_value_hypothesis_missing` | Same fixture, same read-only Stream A fields (`metric`, `owner`, `businessCaseId`). | Nothing new required; VAL-002 only reads what VAL-001 already reads. |

## Repository overlap

- **Related Forged with Foundry controls and how each was checked:**
  - **VAL-001 (implemented):** distinct governance moment, not a duplicate.
    VAL-001 is continuous operational monitoring (a rolling 2-period check
    that can fire repeatedly over an agent's life); VAL-002 is a one-time,
    milestone-based check against the original business case's realisation
    horizon, with a strictly different (lower, 50% vs 80%) threshold and a
    stronger action (reassess the hypothesis, not just review it). An agent
    can trip VAL-001 many times without ever tripping VAL-002, and vice
    versa (steady 60%-of-target performance never trips VAL-001's 80%
    two-period check dramatically, but also never trips VAL-002's 50%
    milestone check either — only a genuinely weak, sustained shortfall
    trips VAL-002).
  - **VAL-004 value leakage (planned, not yet assessed) — explicitly
    deferred, not resolved here.** Catalog contract fields for VAL-002
    (`Realised vs planned value`, `<50% after 6 months`, `Reassess
    hypothesis`, Business Owner) and VAL-004 (`Planned vs captured benefit`,
    `>30% gap`, `Root-cause review`, Business Owner) show no confirmed
    mechanistic distinction yet. Per the user's explicit 2026-09-22 decision
    (recorded in `controls/value_adoption_and_finops/ARCHITECTURE.md`),
    VAL-004's own future assessment must re-check its overlap against this
    finished control and README, not against its own skeleton description
    alone. Do not implement VAL-004 by reasoning from its catalog stub in
    isolation.
  - **VAL-PORT-001 aggregate value below plan (planned) — overlap is
    by-design, not a duplication risk.** Same "realised vs planned value"
    shape, portfolio-aggregated instead of single-agent. When VAL-PORT-001 is
    built, it must aggregate VAL-002's own evidence records across agents
    rather than re-deriving a parallel signal from raw telemetry — recorded
    as a forward-looking requirement in `ARCHITECTURE.md`, not implemented
    here.
  - **MTR-002 KPI/value review missed (planned, Portfolio/Cadence category)
    — checked, no overlap.** MTR-002's signal (per `docs/roadmap.md`) is
    process compliance — whether a scheduled governance review cadence was
    met — not outcome measurement. VAL-002 measures whether the value
    actually materialized; MTR-002 would measure whether someone held the
    meeting to check. Different authoritative signal, different category
    section; no action needed now.
- **Existing components that can be reused:** VAL-001's evaluator structure,
  test shape, demo-runner pattern, and Teams evidence-to-card mapping;
  VAL-PRE-001's fixture as the read-only Stream A source (identical to how
  VAL-001 reads it).
- **Risk of duplicating an existing demo:** Low against VAL-001 given the
  distinct threshold/window/action established above. Unresolved against
  VAL-004 by design (deferred, not this control's problem to solve).

## Proposed contribution

- **Classification:** `ADAPT` — reuses VAL-001's governance-contract read
  path, evaluator shape, and notification mechanism directly; adds only the
  aggregate-window evaluation, the 50% milestone threshold, and the
  hypothesis-reassessment evidence/action.
- **Demo format:** **`HYBRID_DEMO` (recommended, needs user confirmation).**
  The Foundry/Application-Insights/Teams integration this control would
  otherwise redeploy was already proven live by VAL-001 — a second full
  `DEPLOYABLE_DEMO` deploying an equivalent hosted agent and Monitor stack
  from scratch would not prove anything about that integration that VAL-001
  doesn't already prove; it would mostly repeat VAL-001's own deployment
  path under a new resource name. The genuine, distinct learning outcome
  here is the aggregation-window/threshold/action logic, which a small
  executable evaluator can demonstrate against a documented captured or
  synthetic telemetry fixture (6 periods' worth of `TicketTriaged`-shaped
  events, the same event shape VAL-001 already validated live) without
  requiring a second live Azure deployment. `DEPLOYABLE_DEMO` remains a valid
  alternative if a second independent live validation pass is considered
  worth the added Azure cost and community setup time — flagging this as an
  open decision rather than deciding it unilaterally.
- **Deployment:** Optional under the recommended `HYBRID_DEMO` format (a
  documented fixture stands in for 6 periods of live telemetry); would become
  Required for the core learning outcome only if `DEPLOYABLE_DEMO` is chosen
  instead.
- **Existing capabilities reused:** Application Insights/Log Analytics event
  shape (documented via fixture or, if deployed, queried live), the
  governance-contract shared validator, the Teams Workflows notification
  pattern. No new Microsoft capability introduced.
- **How their role is made visible in the core demo:** the evaluator's
  aggregate KQL-equivalent query (or fixture-driven pooled computation) and
  its output are shown directly, same as VAL-001; the Teams notification is
  either a real message (if deployed) or documented identically to VAL-001's
  card format with the same masking conventions.
- **Minimum custom implementation or artifacts:** a control-local evaluator
  variant (pooled N-period aggregation, 50% threshold, `reassess_required`
  decision), a demo runner that seeds or loads N periods instead of 2, and
  the evidence shape's additional `businessCaseId`/window fields.
- **Unique learning outcome:** how a milestone-based value-hypothesis health
  check differs mechanically and procedurally from continuous operational KPI
  monitoring, and why a "the premise itself may be wrong" signal needs a
  different threshold, window, and escalation framing than a routine
  performance alert.
- **Distinct governance learning beyond an existing official sample:** none
  of the 11 currently implemented controls demonstrate a cumulative,
  milestone-anchored realisation check distinct from continuous monitoring —
  this is a genuinely different governance moment from VAL-001, once the
  distinction above is enforced (not merely asserted).
- **Why this deserves a separate bite-sized demo:** it is the next
  explicitly reserved step in `ARCHITECTURE.md`'s Value control-to-stream
  sequence (VAL-001 → VAL-002 → …), and the review-window/threshold/action
  distinction from VAL-001 is real and independently useful to a learner even
  though the plumbing is shared.
- **Why deployment is or is not justified:** the live integration was already
  proven by VAL-001; redeploying identical infrastructure does not add proof
  of a new capability, so `DEPLOYABLE_DEMO` is not required to teach this
  control's genuine learning outcome — but is not wrong either, hence flagged
  for explicit user choice rather than assumed.

## Smallest useful design

- **Supported metric semantics:** unchanged from VAL-001 —
  `tier1_ticket_deflection_rate` only, direction `increase`, absolute
  percentage target in `(0, 100]`. Target 35 gives a milestone threshold of
  17.5%. Aggregate rate is **pooled** (`sum(deflected) / sum(total)` across
  every period in the window), not an average of per-period percentages —
  averaging percentages would distort the result when period volumes differ
  (Simpson's-paradox-style risk); this must be stated explicitly in the
  implementation, unlike VAL-001 where 2 equal-sized periods made the
  distinction moot.
- **Realisation window, without a schema change:** the governance-contract
  schema has no go-live or review-date field today (`VAL-PRE-001` has none;
  `VAL-PRE-002` only has `baseline.measuredDate`, which is when the baseline
  was measured, not an anchor for "6 months of operation"). Recommended
  design: extend VAL-001's own precedent that "periods are explicit tags,
  not real calendar boundaries" to a window of **N = 6 demo periods**
  (`period=1..6`) representing 6 months, requiring **no schema or fixture
  change** to VAL-PRE-001/VAL-PRE-002. The alternative — anchoring to
  `baseline.measuredDate` — was considered and rejected for the core demo
  because it conflates "when we started measuring" with "when the business
  case said we'd know," which are not guaranteed to be the same date; keep
  this as a documented `Further exploration` item instead.
- **Measurement integrity:** same completeness, deduplication, and
  period-consistency checks as VAL-001, extended to require exactly the
  declared N periods rather than exactly 2.
- **Action verification:** same evidence-binding discipline as VAL-001 (one
  authoritative JSON record; `reassess_required` never depends on
  notification success; persist an attempt before sending; require delivery
  evidence before recording Teams delivery), with `businessCaseId` and the
  window/period-count added to the evidence shape.
- **Primary governance decision:** Has the pooled Stream B rate across the
  full N-period window fallen below `target * 0.5`?
- **Authoritative human role or system:** Business Owner (same governance
  contract field VAL-001 reads), notified with explicit `businessCaseId`
  cross-reference and hypothesis-reassessment framing; AI Governance
  Operations for `cannot_evaluate`, same as VAL-001.
- **Signal source:** Stream A (governance contract target, read-only) +
  Stream B (`TicketTriaged` events across N periods), same event shape as
  VAL-001.
- **Authoritative decision or enforcement surface:** the deterministic Python
  evaluator; no ACS intervention point, no Azure Policy — detection and
  escalation, same as VAL-001.
- **Authoritative evidence source:** the evaluator's own structured JSON
  evidence record.
- **ACS intervention point, if applicable:** Not applicable — see Model/
  Foundry role.
- **AGT capability, if applicable:** Not applicable.
- **Foundry/Azure services:** same as VAL-001, optional under `HYBRID_DEMO`
  (see Proposed contribution).
- **Governance action:** Write evidence + post a Teams notification framed as
  hypothesis reassessment. No blocking effect.
- **Evidence artifact:** JSON: metric name, target, 50% threshold, pooled
  rate, window length and period count, Business Owner, `businessCaseId`,
  timestamp.
- **Healthy/complete scenario:** pooled rate across all N periods at or above
  50% of target — no trigger, evidence still recorded as
  `no_reassessment_required`.
- **Policy-triggering scenario:** pooled rate across all N periods below 50%
  of target — `reassess_required`, evidence + Teams notification referencing
  `businessCaseId`.
- **Unavailable, incomplete, or ambiguous scenario:** fewer than N periods of
  telemetry exist yet, or the governance contract target cannot be read —
  `cannot_evaluate`, explicitly distinct from either healthy outcome.

## Complexity budget

- **Why each custom component is necessary:** the pooled N-period
  aggregation, the 50% milestone threshold, and the hypothesis-reassessment
  evidence/action do not exist anywhere else in the repo — VAL-001's
  evaluator is intentionally hardcoded to exactly 2 rolling periods and an
  80% threshold with "review" framing, and reusing it unmodified would
  silently misrepresent a milestone check as an operational one.
- **Files and dependencies used by the core, validation, or optional path:**
  a control-local evaluator (adapted from, not shared with, VAL-001's), a
  control-local demo runner, a documented telemetry fixture (or, if
  `DEPLOYABLE_DEMO` is chosen instead, the same Bicep/hosted-agent pattern
  VAL-001 already validated).
- **Interfaces, agents, stores, or resources deliberately omitted:** no new
  governance-contract schema field (see the realisation-window design
  choice above); no shared `value_tracking` module yet — this would be the
  second control needing this general evaluator shape (after VAL-001), which
  starts to approach, but per the repo's own "avoid shared abstractions until
  multiple implemented controls need them" rule does not yet clearly cross,
  the threshold for extraction; flagged in Community fit as worth revisiting
  once VAL-003/004/005 exist; no Conftest/Rego policy layer; no blocking
  gate/Azure Policy.
- **How disconnected or shadow evidence is avoided:** the evaluator reads the
  target from the same file VAL-001 and VAL-PRE-001 already validate, never a
  separate copy; the evidence record is produced only by the evaluator that
  actually aggregated real or documented-fixture telemetry, never
  hand-authored.
- **Metadata/configuration edge cases, if applicable:** missing/invalid
  governance contract target; fewer than N periods of telemetry; a period
  with zero tickets (division-by-zero guard, same as VAL-001, now applied
  per-period before pooling).

## Community fit

- **Learning level:** Intermediate, same as VAL-001 if deployed; Foundation
  if the recommended `HYBRID_DEMO` fixture path is used, since no Azure
  deployment or KQL familiarity is required to run the core demo.
- **Estimated completion time:** 20-30 minutes under `HYBRID_DEMO` (evaluator
  + fixture, no deployment); 45-60 minutes if `DEPLOYABLE_DEMO` is chosen
  instead, matching VAL-001's time.
- **Minimum prerequisites:** none beyond the repository's Python environment
  under `HYBRID_DEMO`; same prerequisites as VAL-001 (Azure subscription,
  Foundry project, Microsoft 365 tenant with Teams) if `DEPLOYABLE_DEMO` is
  chosen.
- **Why the core demo remains accessible:** reuses VAL-001's proven evaluator
  and evidence shape almost entirely; the only new concept a learner needs is
  "pooled aggregation over a window" versus "rolling two-period check."
- **Intentional simplifications:** the realisation window is 6 demo periods,
  not 6 real calendar months (same simplification style as VAL-001's
  `period=1, period=2`); ticket volume and content remain synthetic.
- **Further exploration to document rather than implement:** anchoring the
  realisation window to a real calendar date once the governance contract
  gains a go-live/review-date field; extracting a shared `value_tracking`
  evaluator module once VAL-003 also needs this shape; a possible future
  MTR-002 companion control that checks whether the reassessment meeting
  itself actually happened, distinct from whether the value showed up.
- **Optional community exploration paths:** running both `HYBRID_DEMO`
  (fixture) and `DEPLOYABLE_DEMO` (live) paths side by side to compare a
  learner's confidence in each; swapping the Teams notification for another
  channel, same as VAL-001's documented option.

## Scope boundary

- **Included:** reading the existing Stream A target and owner; a pooled
  N-period Stream B evaluation; the 50%-of-target milestone threshold;
  evidence + Teams notification framed as hypothesis reassessment,
  cross-referencing `businessCaseId`.
- **Explicitly excluded:** any new governance-contract schema field or
  fixture change; portfolio-level aggregation (VAL-PORT-001's territory,
  reserved as a future consumer of this control's evidence); anomaly/leakage
  detection (VAL-004's deferred territory — not resolved by this
  assessment); a blocking/gating action.
- **What the demo proves:** a real (or documented, fixture-driven) agent's
  cumulative measured behavior across a declared realisation window can be
  compared against the Pre-Live-declared target and reliably trigger a
  distinct, business-case-linked hypothesis-reassessment signal when the
  agent never got close to its promise — a different governance moment than
  VAL-001's operational alert, at a different threshold, with a different
  action.
- **What the demo does not prove:** that 50% or a 6-period window is the
  right milestone for any real organization (that judgment stays with the
  Business Owner); that reassessment actually happens once requested; that
  VAL-004 remains non-overlapping (explicitly deferred, tracked in
  `ARCHITECTURE.md`, not settled here).
- **Is the core control correct and safe within this boundary?** Yes, with
  the same fail-closed `cannot_evaluate` outcome as VAL-001 explicitly
  distinguishing an absent or incomplete signal from either healthy or
  reassess-required.

## Decision

- **Proceed / revise / reject:** **Proceed as `ADAPT`, pending the user's
  confirmation of demo format** (`HYBRID_DEMO`, recommended above, versus a
  second `DEPLOYABLE_DEMO`). Every other design choice in this assessment
  (window, threshold, aggregation rule, evidence shape, overlap resolution)
  is settled and does not depend on that answer.
- **Rationale:** Fulfils the next reserved step in
  `controls/value_adoption_and_finops/ARCHITECTURE.md`'s Value
  control-to-stream sequence; reuses VAL-001's proven integration rather than
  re-demonstrating it; the milestone-vs-continuous distinction is real and
  independently teachable once enforced by a strictly different
  window/threshold/action, not merely asserted.
- **Review date:** 2026-09-22.
- **Authoritative references:**
  - `controls/value_adoption_and_finops/ARCHITECTURE.md` (control-to-stream
    mapping, reserved Value sequence, duplication-risk log)
  - `controls/value_adoption_and_finops/VAL-001_kpi_underperformance/ASSESSMENT.md`
    and `README.md` (the closest structural precedent; VAL-002 is the same
    Monitored-workload posture, aggregated differently)
  - `controls/value_adoption_and_finops/VAL-PRE-001_value_hypothesis_missing/ASSESSMENT.md`
    and its fixture (Stream A source)
  - `schemas/governance-contract/v1alpha1/controls/VAL-PRE-001.schema.json`
    and `VAL-PRE-002.schema.json` (confirmed no existing go-live/review-date
    field — informed the realisation-window design choice above)
  - `docs/roadmap.md` (confirmed MTR-002's process-compliance signal is
    distinct from this control's outcome signal)
  - [Microsoft Foundry Agent Framework](https://learn.microsoft.com/en-us/azure/ai-foundry/) —
    verify current hosted-agent support status at implementation time.
