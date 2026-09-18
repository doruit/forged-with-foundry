# VAL-PRE-002 — control assessment

## Candidate

- **Control ID:** VAL-PRE-002
- **Name:** KPI baseline missing
- **Lifecycle phase:** Pre-Live
- **Accountable role:** Business Owner

## Governance problem

- **Risk:** A team declares a value hypothesis and claims its baseline is
  "measured", but records no actual number or date. Nobody can later tell
  whether the agent moved the needle, because there is nothing concrete to
  compare the measured outcome against -- the baseline exists only as a
  label, not a fact.
- **Control objective:** Block go-live for a tagged go-live request whose
  Forged with Foundry governance contract claims a measured KPI baseline
  without recording an actual numeric value and the date it was measured.
  A `net_new` baseline (genuinely no prior history) needs neither field and
  is trivially complete.
- **Authoritative signal:** the agent's governance contract
  (`.fwf/agents/<agent-id>/governance.yaml`, see
  `docs/governance-contract.md`), specifically its `VAL-PRE-002` control
  entry's `evidence.baseline` block (`status`, and when `status == measured`,
  `value` and `measuredDate`), validated by the shared
  `scripts/validate_governance_contract.py` against
  `schemas/governance-contract/v1alpha1/controls/VAL-PRE-002.schema.json`
  and reduced to one deployment tag Azure Policy evaluates:
  `kpiBaselineStatus`.
- **Required decision:** Allow or deny the demonstrated deployment request.
- **Required governance action:** Block go-live until a claimed measured
  baseline records both a value and a date.
- **Required evidence:** Azure Policy result, policy version and
  identifiers, deployment correlation name, timestamp, and accountable role.

## Enforcement classification

- **Deterministic policy:** Azure Policy is the authoritative
  deployment-time decision engine in the core demo. It evaluates exactly one
  stable decision tag, `kpiBaselineStatus`, following the same reduced-tag
  shape as VAL-PRE-001's `valueHypothesisStatus`.
- **Model-assisted evaluation:** Not applicable.
- **Human approval:** The organisation is expected to have an upstream
  process in which the workload team and Business Owner actually measure and
  record the baseline before go-live. This control does not model that
  measurement process; it assumes the resulting number has been recorded in
  the governance contract, then enforces its structural completeness in the
  governed deployment path.
- **Configuration assessment:** `scripts/validate_governance_contract.py`
  reads the agent's governance contract and validates its `VAL-PRE-002`
  entry's `evidence.baseline` against the declarative JSON Schema: `status`
  must be `measured` or `net_new`; when `status == measured`, `value`
  (numeric) and `measuredDate` (`YYYY-MM-DD`) are both required. This
  directly matches the catalog's trigger text: "No baseline or target
  before build" -- narrowed here to the genuine gap VAL-PRE-001 does not
  already cover (see Repository overlap). A boolean status tag alone would
  under-implement "measured" -- someone could claim it without ever
  recording a number.
- **Automated validation's scope, stated explicitly (never overclaim
  this):** the shared validator proves a claimed measured baseline records
  a number and a date, and rejects placeholder or malformed input (a
  non-numeric value, a malformed date). It cannot verify the number is
  *accurate*, was measured with a sound method, or reflects the real
  historical baseline -- that verification belongs to the organisation's own
  measurement and review process, upstream of this control.
- **Monitoring/detection:** Not applicable to this Pre-Live gate.
- **Required fail-closed behavior:** A tagged go-live request whose
  `kpiBaselineStatus` tag is not `complete` is denied. Azure Policy evaluates
  only this one reduced tag; it never reads the governance contract and
  cannot distinguish a tag a real validator run produced from one a caller
  typed in by hand.
- **Model/Foundry role:** `Not used — not applicable to the core path`. This
  is Azure resource admission with a human-recorded measurement; no agent or
  model action is part of the decision. A Foundry agent would only narrate
  the Azure Policy result and would not improve this learning outcome -- the
  same justification VAL-PRE-001 and PRI-PRE-001 use for their own Pre-Live
  gates.

## Existing capability review

| Capability | Applicable? | What it already provides | Role in the core demo or reason not used |
|---|---:|---|---|
| Microsoft Agent Governance Toolkit | No | Approval workflows | Not relevant until an agent initiates or records the baseline-measurement action. |
| Agent Control Specification | No | Tool/model intervention points | No model or tool call participates in Azure resource admission. |
| Microsoft Foundry | No | Agent orchestration | Would only narrate the policy result; adds complexity with no distinct learning outcome. |
| Foundry Control Plane | No | Agent governance surface | Not applicable -- no agent runtime event is being gated here. |
| Azure API Management AI Gateway | No | Model/tool traffic gating | Not applicable to deployment-time admission. |
| Microsoft Purview | No | Data governance cataloguing | Not a business-value tracking system; not used. |
| Microsoft Defender | No | Threat protection | Not applicable to this control's signal. |
| Microsoft Entra | Yes | Signed-in identity used by the Azure CLI | Reused: no credential is embedded in the core demo. |
| Azure AI Content Safety / Language | No | Content moderation | Not applicable to this control's signal. |
| Azure Monitor / Application Insights / OTel | Not in the core | Live telemetry ingestion/query | Reused later for VAL-001/VAL-005 (Live telemetry, Stream B) once the agent is running -- not needed for this Pre-Live gate. |
| Other supported Microsoft capability | Yes | Azure Policy `deny` effect + `az deployment group validate` | Core capability: the same proven, zero-cost, no-resource-created pattern as VAL-PRE-001/PRI-PRE-001. |

## Existing samples and implementations

| Repository, documentation, or sample | Overlap | What is still missing |
|---|---|---|
| `controls/value_adoption_and_finops/VAL-PRE-001_value_hypothesis_missing` | Identical enforcement mechanism (shared governance-contract schema/validator, Azure Policy `deny`, `az deployment group validate`, zero resources created, two-scenario shell demo) | VAL-PRE-001 already validates `metric`/`target`/`direction` fully -- this control's genuine, smallest gap is narrower: whether a *claimed measured* baseline actually records a value and a date. Reusing the shared validator and schema layer, adding only a new per-control schema file, closes that gap without duplicating VAL-PRE-001's own checks. |

## Repository overlap

- **Related Forged with Foundry controls:** VAL-PRE-001 (value hypothesis
  missing) already validates `metric`, `target`, and `direction` in full.
  The catalog's trigger text for this control ("No baseline or target
  before build") therefore overlaps with VAL-PRE-001 on the word "target" --
  this control deliberately does **not** re-validate target realism or
  presence; that stays VAL-PRE-001's territory. This control's entry is
  fully self-contained (no `businessCaseId` or any other field is reused
  from a VAL-PRE-001 entry, and no VAL-PRE-001 entry needs to exist in the
  same contract) so a workload can implement either control independently,
  per `docs/governance-contract.md`.
- **Existing components that can be reused:** the shared central schema and
  `scripts/validate_governance_contract.py` (this control adds only its own
  `schemas/governance-contract/v1alpha1/controls/VAL-PRE-002.schema.json`);
  VAL-PRE-001's Bicep pattern (policy definition + resource-group assignment
  + harmless Action Group validation target) and shell-script structure
  (`deploy.sh`, `demo.sh`, `cleanup.sh`, `validate.sh`) are reused
  near-verbatim, only the tag name and policy rule differ.
- **Risk of duplicating an existing demo:** Low. No other implemented or
  planned control gates on KPI baseline completeness; VAL-PRE-001 gates on
  value-hypothesis completeness, a distinct (if adjacent) signal.

## Smallest useful demo

- **Classification:** `DEMONSTRATE`
- **Demo format:** `DEPLOYABLE_DEMO`
- **Deployment requirement:** Required; the real Azure Policy decision is
  the learning outcome.
- **Core path:** Deploy definition and assignment; validate one request
  claiming a measured baseline with no recorded value/date, and one request
  with a genuinely recorded value and date; create no workload.
- **Custom code:** Two small shell scripts for repeatability and evidence
  projection, plus Bicep for the policy and a harmless validation target
  (the same `IT Helpdesk Tier-1 Triage Agent` running fictional example),
  plus one new declarative JSON Schema file. No control-local Python: the
  shell scripts call the shared `scripts/validate_governance_contract.py`
  directly.
- **Advanced extension:** An optional GitHub Actions CI check + OIDC-
  authenticated CD deployment demo, mirroring VAL-PRE-001's, is deliberately
  not built in this change to keep the initial contract-architecture rollout
  scoped; see VAL-PRE-001's `docs/OIDC-DEMO.md` for the pattern to reuse if
  a future session adds it here.

## Community and safety boundary

- Foundation-level and runnable in approximately 15-20 minutes.
- Synthetic tags only; no real business case, personal data, prompt, or
  model output is processed.
- The demo assumes the recorded baseline value is trustworthy; it does not
  validate that the number is accurate or was measured with a sound method.
- Cleanup removes only this control's policy assignment and definition.

## Decision

- **Proceed / revise / reject:** Proceed with the Azure Policy-only
  implementation, reusing the shared Forged with Foundry Agent Governance
  Contract schema/validator layer introduced by VAL-PRE-001's migration.
- **Reason:** Reuses the supported capability and the shared contract
  architecture directly, proves a real deny result for the catalog's own
  "no baseline... before build" signal (narrowed to its genuine gap), and
  stays distinct from VAL-PRE-001 (self-contained evidence, no cross-control
  dependency).
- **Review date:** 2026-09-18
- **References:**
  - [Azure Policy `deny` effect](https://learn.microsoft.com/en-us/azure/governance/policy/concepts/effect-deny)
  - [Azure Policy definition structure](https://learn.microsoft.com/en-us/azure/governance/policy/concepts/definition-structure-policy-rule)
  - `controls/value_adoption_and_finops/VAL-PRE-001_value_hypothesis_missing` (reused pattern and shared contract architecture)
  - `docs/governance-contract.md` (the FwF Agent Governance Contract architecture this control is built on)
  - `controls/value_adoption_and_finops/ARCHITECTURE.md` (cross-control data flow)
