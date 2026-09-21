---
description: "Approved assessment for asynchronous monitoring of verified synthetic helpdesk outcomes"
---

# VAL-001 - control assessment

## Candidate

- **Control ID:** VAL-001
- **Name:** KPI underperformance
- **Lifecycle phase:** Live
- **Accountable role:** Business Owner

## Governance problem

- **Risk:** An agent goes live with a declared value hypothesis (VAL-PRE-001)
  and baseline (VAL-PRE-002), but nobody ever checks whether it is actually
  achieving its target once running. A KPI can silently underperform for
  months with no automatic signal reaching the Business Owner.
- **Control objective:** Compare the agent's real, measured KPI rate against
  the target already declared in its governance contract, and trigger a
  Business Owner value review the first time the measured rate falls below
  80% of target for 2 consecutive periods.
- **Authoritative signal:** two independent streams that must never be
  confused: Stream A is the target already declared in
  `.fwf/agents/helpdesk-tier1-triage/governance.yaml`'s VAL-PRE-001 entry
  (`metric.name`, `metric.target`, `metric.direction`) — read-only, never
  redeclared here. Stream B is real Application Insights telemetry emitted
  by an actually-running, hosted Microsoft Foundry agent performing Tier-1
  ticket triage, queried via KQL.
- **Required decision:** Does the measured Stream B rate fall below
  `target * 0.8` for 2 consecutive periods?
- **Required governance action:** For `review_required`, write a structured
  evidence record and notify the Business Owner via a Microsoft Teams channel
  message. For `cannot_evaluate`, notify AI Governance Operations, the
  Control Operator responsible for restoring the measurement path. These are
  detect-and-escalate actions, not blocking gates: a Live-phase value control
  does not have the authority to halt a running agent.
- **Required evidence:** metric name, declared target, the 80% threshold,
  both periods' measured rates, the Business Owner (read from the same
  governance contract entry), and a timestamp.

## Enforcement classification

- **Deterministic policy:** Plain Python evaluator: read target from the
  governance contract, query Log Analytics for the last 2 periods'
  `TicketTriaged` events, compute `deflected / total` per period, compare
  each to `target * 0.8`. No model or LLM call is part of this decision.
- **Model-assisted evaluation:** Not applicable to the decision itself. See
  Model/Foundry role below for the agent's actual role in this control.
- **Human approval:** Not applicable — this control produces a detection and
  a notification, not an approval-gated action. The Business Owner's review
  in response to the notification is an out-of-band organisational process
  this control does not model, analogous to how VAL-PRE-001 does not model
  the upstream hypothesis-approval process either.
- **Configuration assessment:** Not applicable.
- **Monitoring/detection:** This is the primary mechanism. Real Application
  Insights telemetry is the authoritative Live-phase signal; the evaluator
  performs periodic (not per-request) detection over accumulated telemetry.
- **Required fail-closed behavior:** If Stream A's target cannot be read
  (missing/invalid governance contract entry) or fewer than 2 periods of
  Stream B telemetry are available, the evaluator must not silently report
  "no underperformance" — it must report an explicit "insufficient data,
  cannot evaluate" outcome distinct from "healthy," so an absent signal is
  never mistaken for a passing one.
- **Model/Foundry role:** **Monitored workload**, approved on 2026-09-21.
  A real hosted Microsoft Agent Framework agent performs synthetic helpdesk
  work. Only executed and independently verified synthetic resolutions
  without human handling count as deflected; model text is not evidence.
  Periodic deterministic monitoring evaluates these outcomes asynchronously.
  No ACS gate, explanatory governance agent, or LLM evaluator belongs in the
  core path. Existing ACS requirements for inline enforcement remain intact;
  genuine inline tool governance is further exploration only.

## Existing capability review

| Capability | Applicable? | What it already provides | Role in the core demo or reason not used |
|---|---:|---|---|
| Microsoft Agent Governance Toolkit | No | Approval workflows | Not applicable — no approval action in this control's path. |
| Agent Control Specification | No | Tool/model intervention points | No single agent turn is gated; this control evaluates aggregated telemetry across periods, not an inline action. See Model/Foundry role. |
| Microsoft Foundry | Yes | Hosted agent runtime (`azd ai agent`), Agent Framework (`agent_framework.foundry.FoundryChatClient`) | Core: a real hosted Foundry agent performs the actual Tier-1 triage work being measured. Same import pattern as `controls/privacy/PRI-00{1,2,3,4}`. |
| Foundry Control Plane | No | Agent governance surface | Not needed beyond standard hosted-agent deployment for this control's scope. |
| Azure API Management AI Gateway | No | Model/tool traffic gating | Not applicable — this control is not about gating traffic to a model. |
| Microsoft Purview | No | Data governance cataloguing | Not applicable to this control's signal. |
| Microsoft Defender | No | Threat protection | Not applicable. |
| Microsoft Entra | Yes | Managed identity for the hosted agent and evaluator's Log Analytics query | Reused: no credential is embedded in the demo; the evaluator and agent use managed identity, matching repo convention. |
| Azure AI Content Safety / Language | No | Content moderation | Not applicable to this control's signal. |
| Azure Monitor / Application Insights / OTel | Yes | Telemetry ingestion, custom events, KQL query | Core: this is Stream B. `ARCHITECTURE.md` reserved this capability for VAL-001 specifically ("Reused later for VAL-001/VAL-005... once the agent is running"). |
| Other supported Microsoft capability | Yes | Microsoft Teams Workflows app (Power Automate webhook-trigger flow) | Notification delivery. Verify the exact trigger, connector, authentication, tenant policy, and licensing before deployment. E5 alone does not establish entitlement. HTTP acceptance is not proof of Teams delivery. |

## Existing samples and implementations

| Repository, documentation, or sample | Overlap | What is still missing |
|---|---|---|
| `controls/value_adoption_and_finops/VAL-PRE-001_value_hypothesis_missing` | Same fictional agent (`helpdesk-tier1-triage`) and metric (`tier1_ticket_deflection_rate`). Target 35 is an absolute 35% deflection rate, not a relative increase. Read target and owner through the shared validator; never redeclare them. | Hosted workload, verified telemetry, two-period evaluation, and notification. |
| `controls/privacy/PRI-002_retention_violation` | Closest existing "control decides, real Foundry agent does the measured/governed work, model narration is optional and non-authoritative" pattern in this repo. | PRI-002's agent narrates an independently-computed decision about a Blob record; VAL-001's agent does not narrate anything in the core path — its real ticket-handling behavior IS the measured signal, which is a different relationship, not previously built here. |

## Repository overlap

- **Related Forged with Foundry controls:** `ARCHITECTURE.md` explicitly
  reserves VAL-001 as "the one control reserved for value tracking and
  reporting... do not create a second control for tracking or reporting a
  KPI against its target." VAL-002 (benefits realisation gap), VAL-003 (ROI
  degradation), VAL-004 (value leakage), and VAL-005 (adoption-to-value
  conversion gap) are documented as later controls that will read the same
  Stream A/Stream B shape this control establishes — they are not being
  pre-built here.
- **Existing components that can be reused:** VAL-PRE-001's fixture
  (`.fwf/agents/helpdesk-tier1-triage/governance.yaml`) as the read-only
  Stream A source; PRI-002's "control decides, agent does the real/measured
  work, narration is optional" architecture as the closest structural
  precedent; the microsoft-foundry skill's hosted-agent scaffold workflow.
- **Risk of duplicating an existing demo:** Low for the control itself
  (uniquely reserved for this role). The main duplication risk to actively
  avoid is building a shared `value_tracking` module now — deferred per the
  repo's own "avoid shared abstractions until multiple implemented controls
  need them" rule; VAL-001's evaluator is self-contained, shaped for later
  extraction once VAL-002 actually needs the same shape.

## Proposed contribution

- **Classification:** `ADAPT` — reuses Foundry Agent Framework hosted-agent
  deployment, Application Insights/Log Analytics, and Microsoft Teams
  Workflows directly; adds only the deterministic evaluator, the explicit
  period-tagging convention, and the evidence/notification glue.
- **Demo format:** `DEPLOYABLE_DEMO` — a real running agent and real
  telemetry are required to produce a genuine Stream B signal; this cannot
  be demonstrated as clearly through a guided exercise alone.
- **Deployment:** Required for the core learning outcome.
- **Existing capabilities reused:** Microsoft Foundry Agent Framework
  (hosted agent), Application Insights/Log Analytics + KQL, Microsoft Teams
  Workflows (Power Automate), Microsoft Entra managed identity.
- **How their role is made visible in the core demo:** the hosted agent is
  deployed and actually triages synthetic tickets; the evaluator's KQL query
  and its output are shown directly; the Teams notification is a real
  message delivered to a real channel, not a simulated/logged stand-in.
- **Minimum custom implementation or artifacts:** the deterministic
  evaluator (read target, query KQL, apply the 2-period rule, emit
  evidence), the demo runner that seeds tagged ticket batches per period,
  and the Teams flow's evidence-to-Adaptive-Card mapping.
- **Unique learning outcome:** how to turn a declared Pre-Live value
  hypothesis into a real, live-measured KPI check against actually-running
  agent telemetry, ending in a real notification, not a synthetic log line.
- **Distinct governance learning beyond an existing official sample:** shows
  the read-only Stream-A/Stream-B separation in a governance contract
  context, and the "no ACS gate, telemetry is the authoritative signal"
  shape that none of the other 9 implemented controls demonstrate yet.
- **Why this deserves a separate bite-sized demo:** it is the single control
  this category's `ARCHITECTURE.md` reserves for this exact role; no
  substitute exists.
- **Why deployment is or is not justified:** a real hosted agent producing
  real telemetry cannot be faked without undermining the very thing being
  taught — that KPI tracking must be grounded in real measured behavior, not
  narrated or assumed.

## Smallest useful design

- **Supported metric semantics:** only `tier1_ticket_deflection_rate`, direction
  `increase`, with an absolute percentage target in `(0, 100]`. The existing
  target 35 gives a threshold of 28%. Both consecutive periods must be
  strictly below the threshold; equality does not trigger a review.
- **Measurement integrity:** a unique run identity, explicit period sequence,
  and expected synthetic ticket identities bind the telemetry query. Missing,
  empty, invalid, conflicting, or incomplete observations produce
  `cannot_evaluate`. Identical retransmissions are deduplicated; conflicting
  duplicates and nonconsecutive periods are rejected.
- **Action verification:** one authoritative JSON record binds control and
  policy versions, run/correlation identity, contract reference and digest,
  counts, rates, target, threshold, decision, reason, owner, and notification
  verification. `review_required` never depends on notification success.
  Persist an attempt before sending; do not blindly resend after a timeout
  or restart. Require delivery evidence before recording Teams delivery.
- **Primary governance decision:** Has the measured Stream B rate fallen
  below `target * 0.8` for 2 consecutive periods?
- **Authoritative human role or system:** Business Owner for
  `review_required`, declared in the governance contract's VAL-PRE-001 entry;
  AI Governance Operations for `cannot_evaluate` remediation.
- **Signal source:** Stream A (governance contract target, read-only) +
  Stream B (Application Insights `TicketTriaged` custom events, tagged with
  an explicit `period` property, not derived from calendar time).
- **Authoritative decision or enforcement surface:** the deterministic
  Python evaluator; no ACS intervention point, no Azure Policy (this is
  detection/escalation, not admission control).
- **Authoritative evidence source:** the evaluator's own structured JSON
  evidence record.
- **ACS intervention point, if applicable:** Not applicable — see Model/
  Foundry role.
- **AGT capability, if applicable:** Not applicable.
- **Foundry/Azure services:** Microsoft Foundry hosted agent (`azd ai
  agent`), Application Insights, Log Analytics, Microsoft Entra managed
  identity, Microsoft Teams Workflows (Power Automate).
- **Governance action:** Write evidence + post a Teams notification. No
  blocking effect.
- **Evidence artifact:** JSON: metric name, target, threshold, both
  periods' measured rates, Business Owner, timestamp.
- **Healthy/complete scenario:** both periods measure at or above 80% of
  target — no trigger, evidence still recorded.
- **Policy-triggering scenario:** both periods measure below 80% of target
  — trigger, evidence + Teams notification.
- **Unavailable, incomplete, or ambiguous scenario:** only 1 period of
  telemetry exists yet, or the governance contract target cannot be read —
  evaluator reports "insufficient data," explicitly distinct from "healthy."

## Complexity budget

- **Why each custom component is necessary:** the evaluator's rate/threshold
  logic and period-tagging convention do not exist anywhere else in the
  repo; the demo runner is needed to make the real-agent, real-telemetry
  path reproducible.
- **Files and dependencies used by the core, validation, or optional path:**
  hosted agent source, evaluator script, demo runner, Bicep for Application
  Insights/Log Analytics (reusing the hosted-agent scaffold's provisioning
  where possible), Teams flow definition/URL configuration.
- **Interfaces, agents, stores, or resources deliberately omitted:** no new
  shared `value_tracking` module (deferred until VAL-002 needs it); no new
  governance-contract JSON Schema (VAL-001 only reads VAL-PRE-001's existing
  schema'd field, per item 13 of
  `.github/instructions/fwf-governance-contract.instructions.md`: "do not
  require every runtime control... to acquire a YAML schema merely because
  it exists in the catalog"); no Conftest/Rego policy layer; no blocking
  gate/Azure Policy.
- **How disconnected or shadow evidence is avoided:** the evaluator reads
  the target from the same file VAL-PRE-001 already validates, never a
  separate copy; the evidence record is produced only by the evaluator that
  actually queried real telemetry, never hand-authored.
- **Metadata/configuration edge cases, if applicable:** missing/invalid
  governance contract target; fewer than 2 periods of telemetry; a period
  with zero tickets (division-by-zero guard).

## Community fit

- **Learning level:** Intermediate (requires a working Foundry project and
  basic KQL familiarity to inspect).
- **Estimated completion time:** roughly 30-45 minutes: hosted-agent
  deployment, then a 15-30 minute compressed 2-period demo run.
- **Minimum prerequisites:** an Azure subscription with a Foundry
  project/model deployment, a Microsoft 365 tenant with Teams + Power
  Automate (E5 confirmed available), Azure CLI signed in.
- **Why the core demo remains accessible:** reuses the existing hosted-agent
  scaffold pattern and a single evaluator script; no new shared platform.
- **Intentional simplifications:** each "period" is an explicit tag set by
  the demo script (`period=1`, `period=2`, ...), not a real calendar
  boundary — documented plainly as a simplification, the same spirit as
  PRI-002's `DemoAgeDays` workaround. Ticket volume and content are
  synthetic.
- **Further exploration to document rather than implement:** extracting a
  shared `value_tracking` evaluator module once VAL-002 is built; wiring
  VAL-001 into a CI/CD schedule for continuous monitoring; using Foundry's
  own agent observability/evaluation telemetry instead of Application
  Insights; publishing a monthly positive-performance summary through a
  Power BI dashboard built from Log Analytics and control evidence.
- **Optional community exploration paths:** swapping the Teams Workflows
  notification for email/ServiceNow/other ITSM integration; adding a monthly
  healthy-performance report for the Business Owner and AI Governance
  Operations in Power BI.

## Scope boundary

- **Included:** reading the existing Stream A target; deploying a real
  hosted Foundry agent that performs real Tier-1 triage; real Application
  Insights telemetry; the deterministic 2-period evaluator; evidence +
  Teams notification.
- **Explicitly excluded:** portfolio-level aggregation across agents
  (VAL-PORT-*); any new governance-contract schema or Rego policy; a
  blocking/gating action; a shared cross-control evaluator module.
- **What the demo proves:** a real agent's real measured behavior can be
  compared against a Pre-Live-declared target and reliably trigger a real
  business-owner-facing notification when it underperforms for 2 periods.
- **What the demo does not prove:** that the declared target was
  strategically sound (that adequacy judgment is VAL-PRE-001's boundary,
  not this control's); that 2 demo-compressed periods are equivalent to 2
  real reporting periods in production; that the notification is acted upon.
- **Is the core control correct and safe within this boundary?** Yes, with
  the fail-closed "insufficient data" outcome explicitly distinguishing an
  absent signal from a passing one.

## Decision

- **Proceed / revise / reject:** Proceed. The design and Monitored workload
  classification were approved on 2026-09-21. Implementation and live
  deployment, telemetry, Teams, and control-owned cleanup validation remain
  required; this assessment is not evidence that those paths have run.
- **Rationale:** Fulfils `ARCHITECTURE.md`'s reserved role for VAL-001, uses
  a real Foundry agent and real telemetry as explicitly requested, and
  deliberately avoids over-adopting the heavier governance-contract
  machinery per this session's earlier strategic assessment.
- **Review date:** 2026-09-21.
- **Authoritative references:**
  - `controls/value_adoption_and_finops/ARCHITECTURE.md` (control-to-stream
    mapping, reserved role for VAL-001)
  - `controls/value_adoption_and_finops/VAL-PRE-001_value_hypothesis_missing/ASSESSMENT.md`
    and its fixture (Stream A source)
  - `controls/privacy/PRI-002_retention_violation/README.md` ("the control
    decides; the agent explains and orchestrates")
  - `.github/instructions/fwf-governance-contract.instructions.md` (item 13:
    reuse the appropriate mechanism only, no schema/Rego by default)
  - [Microsoft Foundry Agent Framework](https://learn.microsoft.com/en-us/azure/ai-foundry/) —
    verify current hosted-agent (`azd ai agent`) support status at
    implementation time.
  - [Microsoft Teams Workflows app / Power Automate webhook trigger](https://support.microsoft.com/en-us/office/) —
    verify current support status at implementation time; do not use the
    legacy Office 365 Connector.
