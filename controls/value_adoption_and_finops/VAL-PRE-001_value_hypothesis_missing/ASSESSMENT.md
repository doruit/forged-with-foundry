# VAL-PRE-001 — control assessment

## Candidate

- **Control ID:** VAL-PRE-001
- **Name:** Value hypothesis missing
- **Lifecycle phase:** Pre-Live
- **Accountable role:** Business Owner

## Governance problem

- **Risk:** A team requests go-live for an agent with no measurable business
  hypothesis. Without a named metric, target, and baseline commitment, no
  later control (VAL-001 KPI underperformance, VAL-002 benefits realisation
  gap, VAL-003 ROI degradation) has anything concrete to measure against, so
  underperformance can go undetected indefinitely.
- **Control objective:** Block go-live for a tagged go-live request unless the
  request carries a structured, measurable value hypothesis: a named metric,
  a numeric target with a direction, a baseline status, a named owner, and a
  business case identifier.
- **Authoritative signal:** the agent's Forged with Foundry governance
  contract (`.fwf/agents/<agent-id>/governance.yaml`, see
  `docs/governance-contract.md`), specifically its `VAL-PRE-001` control
  entry's `evidence` block (metric, target value and direction, baseline
  status, owner, business case id, expected outcome), validated by the
  shared `scripts/validate_governance_contract.py` against
  `schemas/governance-contract/v1alpha1/controls/VAL-PRE-001.schema.json`
  and reduced to the deployment tags Azure Policy evaluates: the
  pre-existing `goLiveRequested` trigger tag, plus the two decision tags the
  validator produces, `valueHypothesisStatus` and `businessCaseId`.
- **Required decision:** Allow or deny the demonstrated deployment request.
- **Required governance action:** Block go-live until every required field is
  present and structurally valid.
- **Required evidence:** Azure Policy result, policy version and identifiers,
  deployment correlation name, timestamp, and accountable role.

## Enforcement classification

- **Deterministic policy:** Azure Policy is the authoritative
  deployment-time decision engine in the core demo. It evaluates exactly
  two stable decision tags, `valueHypothesisStatus` and `businessCaseId`,
  mirroring PRI-PRE-001's `dpiaStatus`/`dpiaEvidenceId` shape so the tag
  surface does not grow as VAL-PRE-002/003/004 add fields.
- **Model-assisted evaluation:** Not applicable.
- **Human approval:** The organisation is expected to have an upstream
  intake or governance process in which the workload team and Business Owner
  define, review, and challenge the value hypothesis before go-live. This
  control does not model that approval workflow; it assumes the resulting
  hypothesis has been agreed and recorded in the governance contract, then
  enforces its structural completeness in the governed deployment path.
- **Configuration assessment:** `scripts/validate_governance_contract.py`
  reads the agent's `.fwf/agents/<agent-id>/governance.yaml` and validates
  its `VAL-PRE-001` entry's `evidence` block against the declarative JSON
  Schema (`schemas/governance-contract/v1alpha1/controls/VAL-PRE-001.schema.json`):
  a named metric, a numeric target, an explicit direction
  (`increase`/`decrease`), an explicit baseline status (`measured`/`net_new`),
  a named owner, a business case id, and an expected outcome — then reduces
  that assessment to the two tags Azure Policy checks. This directly matches
  the catalog's own trigger text: "No **measurable** business hypothesis" —
  a boolean status tag alone would under-implement that requirement, so the
  assessment is moved into the schema-driven validator rather than encoded
  as more and more tags.
- **Automated validation's scope, stated explicitly (never overclaim
  this):** the shared validator proves the declaration exists and is
  structurally valid, and rejects placeholder or obviously meaningless
  input. It cannot judge whether the hypothesis is strategically credible
  or ambitious enough — that adequacy judgment belongs to the organisation's
  own governance intake and approval process, upstream of this control.
  `businessCaseId` is the traceability link to that process. A passing
  schema validation never proves the agent will create value.
- **Monitoring/detection:** Not applicable to this Pre-Live gate.
- **Required fail-closed behavior:** A tagged go-live request whose
  `valueHypothesisStatus` tag is not `complete`, or whose `businessCaseId` tag
  is missing or empty, is denied. Azure Policy evaluates only these two
  reduced tags; it never reads the governance contract and cannot
  distinguish tags a real validator run produced from tags a caller typed
  in by hand.
- **Model/Foundry role:** `Not used — not applicable to the core path`. This
  is Azure resource admission with a human-authored business case; no agent
  or model action is part of the decision. A Foundry agent would only narrate
  the Azure Policy result and would not improve this learning outcome — the
  same justification PRI-PRE-001 uses for its own DPIA gate.

## Existing capability review

| Capability | Applicable? | What it already provides | Role in the core demo or reason not used |
|---|---:|---|---|
| Microsoft Agent Governance Toolkit | No | Approval workflows | Not relevant until an agent initiates or records the hypothesis approval action. |
| Agent Control Specification | No | Tool/model intervention points | No model or tool call participates in Azure resource admission. |
| Microsoft Foundry | No | Agent orchestration | Would only narrate the policy result; adds complexity with no distinct learning outcome. |
| Foundry Control Plane | No | Agent governance surface | Not applicable — no agent runtime event is being gated here. |
| Azure API Management AI Gateway | No | Model/tool traffic gating | Not applicable to deployment-time admission. |
| Microsoft Purview | Context only | Data governance cataloguing | Not a business-value tracking system; not used. |
| Microsoft Defender | No | Threat protection | Not applicable to this control's signal. |
| Microsoft Entra | Yes | Signed-in identity used by the Azure CLI; Workload Identity Federation (OIDC) for GitHub Actions | Reused: no credential is embedded in the core demo, and the optional GitHub Actions extension authenticates via a federated credential instead of a client secret. |
| Azure AI Content Safety / Language | No | Content moderation | Not applicable to this control's signal. |
| Azure Monitor / Application Insights / OTel | Not in the core | Live telemetry ingestion/query | Reused later for VAL-001/VAL-005 (Live telemetry, Stream B) once the agent is running — not needed for this Pre-Live gate, which only evaluates deployment tags. |
| Other supported Microsoft capability | Yes | Azure Policy `deny` effect + `az deployment group validate` | Core capability: the same proven, zero-cost, no-resource-created pattern as `controls/privacy/PRI-PRE-001`. |

## Existing samples and implementations

| Repository, documentation, or sample | Overlap | What is still missing |
|---|---|---|
| `controls/privacy/PRI-PRE-001_dpia_required_but_missing` | Identical enforcement mechanism (Azure Policy `deny`, `az deployment group validate`, zero resources created, two-scenario shell demo, two-tag schema shape) | VAL-PRE-001 needs a configuration-assessment step upstream of the two tags, because its trigger is "no **measurable** business hypothesis", a structural property that a single status tag cannot represent on its own — this is the genuine, smallest gap; the shared `scripts/validate_governance_contract.py` plus this control's declarative JSON Schema is that step. |

Azure Policy already supplies the enforcement mechanism; reusing it directly
avoids duplicating a policy engine, approval protocol, or storage register.

## Repository overlap

- **Related Forged with Foundry controls:** VAL-PRE-002 (KPI baseline
  missing), VAL-PRE-003 (benefit attribution model missing), VAL-PRE-004
  (value owner not assigned) declare their own independent control entries
  in the same governance contract structure (see
  `docs/governance-contract.md` and
  `controls/value_adoption_and_finops/ARCHITECTURE.md`) rather than
  extending this control's evidence block — each control's evidence stays
  self-contained, so a workload can implement any subset of them
  independently. Each gets its own ASSESSMENT.md, JSON Schema, and design
  conversation when reached; VAL-PRE-002 is designed and built directly
  after this migration (not pre-built here).
  `VAL-001_kpi_underperformance` (KPI underperformance, Live) is the
  designated value tracking and reporting control; it later reads the same
  `metric`/`target` fields this control's governance contract entry
  declares, via a separate Live telemetry stream (not built here).
- **Existing components that can be reused:** PRI-PRE-001's Bicep pattern
  (policy definition + resource-group assignment + harmless Action Group
  validation target) and shell-script structure (`deploy.sh`, `demo.sh`,
  `cleanup.sh`, `validate.sh`) are reused near-verbatim, only the tag schema
  and policy rule differ.
- **Risk of duplicating an existing demo:** Low. No other implemented or
  planned control gates on business-value-hypothesis measurability; PRI-PRE-001
  gates on DPIA evidence, a distinct privacy signal.

## Smallest useful demo

- **Classification:** `DEMONSTRATE`
- **Demo format:** `DEPLOYABLE_DEMO`
- **Deployment requirement:** Required; the real Azure Policy decision is the
  learning outcome.
- **Core path:** Deploy definition and assignment; validate one request
  missing the value hypothesis and one request with a complete, structurally
  valid hypothesis; create no workload.
- **Custom code:** Two small shell scripts for repeatability and evidence
  projection, plus Bicep for the policy and a harmless validation target
  (an `IT Helpdesk Tier-1 Triage Agent` go-live request, this category's
  running fictional example).
- **Advanced extension:** Connect the trigger metadata to an authoritative
  business-case/intake system, or to the Live telemetry stream (Stream B)
  once VAL-001 is built, so the same metric name carries through from
  hypothesis to measured outcome. A real, optional CI check + OIDC-authenticated
  CD deployment extension (`.github/workflows/val-pre-001-value-gate-demo.yml`,
  GitHub OIDC via `infra/oidc-identity.bicep`) is now built, reusing the same
  validator and Azure Policy gate rather than adding a competing schema,
  script, or policy.

## Community and safety boundary

- Foundation-level and runnable in approximately 15–20 minutes.
- Synthetic tags only; no real business case, personal data, prompt, or model
  output is processed.
- The demo assumes the go-live request and tag values are trustworthy; it
  does not validate that the target is realistic or that the named owner is
  a real person.
- Cleanup removes only this control's policy assignment and definition.

## Decision

- **Proceed / revise / reject:** Proceed with the Azure Policy-only
  implementation, matching PRI-PRE-001's pattern with a structured
  measurability tag schema.
- **Reason:** Reuses the supported capability directly, proves a real deny
  result for the catalog's own "no measurable business hypothesis" signal,
  and stays distinct from PRI-PRE-001 and from VAL-PRE-002/003/004 (which are
  not being pre-built here).
- **Review date:** 2026-09-18 (migrated from the synthetic `agent.yaml`
  fixture, a naming collision with the real Microsoft Foundry/Agent
  Framework hosted-agent manifest, to the repo-wide Forged with Foundry
  Agent Governance Contract architecture: `.fwf/agents/<agent-id>/
  governance.yaml`, validated by the shared
  `scripts/validate_governance_contract.py` against
  `schemas/governance-contract/v1alpha1/`. Azure Policy tags, the policy
  rule, and the two-scenario demo are unchanged; see
  `docs/governance-contract.md`.)
- **References:**
  - [Azure Policy `deny` effect](https://learn.microsoft.com/en-us/azure/governance/policy/concepts/effect-deny)
  - [Azure Policy definition structure](https://learn.microsoft.com/en-us/azure/governance/policy/concepts/definition-structure-policy-rule)
  - `controls/privacy/PRI-PRE-001_dpia_required_but_missing` (reused pattern)
  - `controls/value_adoption_and_finops/ARCHITECTURE.md` (cross-control data
    flow this control's governance contract entry feeds)
  - `docs/governance-contract.md` (the FwF Agent Governance Contract
    architecture this control was migrated onto)
  - `controls/value_adoption_and_finops/VAL-001_kpi_underperformance`
    (downstream value tracking and reporting control; not yet implemented,
    but already scaffolded and reserved for this role, so it must not be
    duplicated by a new control later)
