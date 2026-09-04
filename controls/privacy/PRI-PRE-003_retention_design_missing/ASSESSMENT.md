# PRI-PRE-003 — control assessment

## Proposed control

- **Risk:** A team requests go-live for a system that will hold governed data
  (for example Microsoft Foundry trace/telemetry data, or another AI system
  record) but has never documented how long that data is kept, where, or who
  owns disposing of it.
- **Required decision:** Allow or deny the demonstrated deployment request.
- **Governance action:** Block go-live until a complete retention design (data
  category, storage system, retention period, disposition, and owner) is
  documented.
- **Required evidence:** Azure Policy result, policy version and identifiers,
  deployment correlation name, timestamp, and accountable role.

## Enforcement classification

- **Configuration assessment:** The retention design is represented as
  deployment metadata (tags), not a real retention configuration.
- **Deterministic enforcement:** Azure Policy is the only decision engine.
- **Model-assisted evaluation:** Not applicable.
- **Human approval:** A Privacy Officer is assumed to have authored the
  retention design upstream; the tags represent its declared content, not an
  approval workflow.
- **Fail-closed behavior:** A tagged go-live request that carries governed
  data is denied unless all five retention-design tags are present and
  individually valid.

**Model/Foundry role: Not used — not applicable to the core path.** The
authoritative signal is Azure resource deployment metadata describing a
retention design, not an agent, tool, or model event. Microsoft Foundry is
named only as an example of the kind of governed workload whose trace data
this control's retention design would cover; no Foundry agent, model, or ACS
intervention point participates in the decision, and adding one would only
narrate an already-deterministic policy result.

## Existing capability review

| Capability | Applicable? | What it already provides | Role in the core demo or reason not used |
|---|---:|---|---|
| Microsoft Agent Governance Toolkit | No | Approval workflows | No agent initiates or records the retention design; not part of this demo. |
| Agent Control Specification | No | Runtime intervention points | No model or agent tool call is part of Azure resource admission. |
| Microsoft Foundry | Context only | Agent tracing, stored in Application Insights | Named only as an example governed workload; tracing is off by default and, when enabled, retention is governed entirely by the connected Application Insights/Log Analytics workspace, not by Foundry itself. |
| Foundry Control Plane | No | Agent/model runtime governance | No agent runtime is part of this control's signal or decision. |
| Azure API Management AI Gateway | No | Model/tool traffic governance | Not applicable; this control gates a deployment request, not model traffic. |
| Microsoft Purview | Context only, not authoritative | "Enterprise AI apps" retention location lists Microsoft Foundry | Applies only to Entra-registered AI apps with a configured collection policy capturing prompts/responses — a distinct, mailbox-based/eDiscovery path. It does not govern generic OpenTelemetry trace data in Application Insights/Log Analytics, so it cannot be the authoritative source for this control. |
| Microsoft Defender | No | Threat detection | Not applicable to a deployment-admission decision. |
| Microsoft Entra | Yes | Signed-in identity for Azure CLI | The Azure CLI uses the signed-in identity; no credential is embedded in the demo. |
| Azure AI Content Safety / Language | No | Content moderation | Not applicable; no content is processed. |
| Azure Monitor / Application Insights / OTel | Yes (as governed context, not as the enforcement point) | Native workspace- and table-level retention settings (`retentionInDays`, `totalRetentionInDays`, up to 12 years total) | The control's tags describe the intended retention design for data that would ultimately live here; the gate itself is Azure Policy, because **no Azure Policy built-in exists** to audit or enforce Log Analytics retention settings (verified against the full built-in policy catalog on 2026-09-04). |
| Azure Policy | Yes | Native `deny` effect and deployment validation | Core capability, reused directly, exactly as PRI-PRE-001 and PRI-PRE-002 do. |

## Existing samples and implementations

| Repository, documentation, or sample | Overlap | What is still missing |
|---|---|---|
| `controls/privacy/PRI-PRE-001_dpia_required_but_missing` | Same Pre-Live, `deny`-effect, tag-driven Azure Policy pattern | Different signal (DPIA approval, not retention design); reused directly as the implementation template. |
| `controls/privacy/PRI-002_retention_violation` | Same general theme (retention) | Live-phase violation detection over already-collected data via Blob lifecycle management, not a Pre-Live design-completeness gate; different phase, mechanism, and authoritative source. |
| [Manage Data Retention in a Log Analytics Workspace](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/data-retention-configure) (reviewed 2026-09-04) | Documents the real retention mechanism this control's design ultimately governs | No Azure Policy built-in to audit/enforce `retentionInDays`/`totalRetentionInDays`; confirms the genuine capability gap this control's Azure Policy layer fills at the design-completeness level. |
| [Foundry tracing and data handling](https://learn.microsoft.com/azure/foundry/observability/concepts/trace-data) (reviewed 2026-09-04) | Confirms trace data is off by default and, when enabled, stored only in the connected Application Insights/Log Analytics workspace | No separate Foundry-level retention control exists to reuse. |
| [Purview retention policies for Copilot and AI apps](https://learn.microsoft.com/en-us/purview/retention-policies-copilot) (reviewed 2026-09-04) | Lists Microsoft Foundry as an "Enterprise AI apps" retention location | Only covers Entra-registered apps with a collection policy; does not govern generic trace telemetry, so it cannot be reused as the authoritative signal here. |

## Repository overlap

- **Related Forged with Foundry controls:** `PRI-PRE-001` (implementation
  template), `PRI-PRE-002` (Pre-Live `audit` analog), `PRI-002` (Live-phase
  retention violation).
- **Existing components that can be reused:** The PRI-PRE-001 Bicep/bash
  pattern (subscription-scope custom policy definition, resource-group-scoped
  assignment, harmless validate-only demo target, shell runner with JSON
  evidence).
- **Risk of duplicating an existing demo:** Low. PRI-PRE-003 is a distinct
  Pre-Live design-completeness gate; PRI-002 only detects violations after data
  already exists, and PRI-PRE-001/PRI-PRE-002 gate a different signal (DPIA),
  not retention design.

## Proposed contribution

- **Classification:** `DEMONSTRATE`
- **Demo format:** `DEPLOYABLE_DEMO`
- **Deployment:** Required for the core learning outcome
- **Existing capabilities reused:** Azure Policy `deny` effect, Azure CLI
  deployment validation, Microsoft Entra signed-in identity.
- **How their role is made visible in the core demo:** The policy definition
  and assignment are real Azure objects inspectable in the Azure Portal; the
  demo runner prints the real `RequestDisallowedByPolicy` result and the real
  successful validation result for each scenario.
- **Minimum custom implementation or artifacts:** One Bicep policy definition,
  one Bicep assignment, one harmless Bicep validation target with a `scenario`
  parameter, and two shell scripts (deploy/cleanup) plus a demo runner and a
  local validation script.
- **Unique learning outcome:** Translating a Pre-Live retention-design
  completeness requirement into a minimal, observable `deny` example, distinct
  from DPIA approval (PRI-PRE-001/002) and from Live-phase violation detection
  (PRI-002).
- **Distinct governance learning beyond an existing official sample:** No
  official Microsoft sample or Azure Policy built-in demonstrates gating
  go-live on retention-design completeness; this closes that specific gap at
  Foundation level.
- **Why this deserves a separate bite-sized demo:** Different lifecycle phase,
  signal, and governance action from every existing privacy control.
- **Why deployment is or is not justified:** The learning outcome is the real,
  asynchronous Azure Policy admission decision (deny vs validate); a
  guided-exercise walkthrough alone cannot show the authoritative
  `RequestDisallowedByPolicy` result.

## Smallest useful design

- **Primary governance decision:** Allow or deny a tagged go-live request
  based on whether its retention design is complete and valid.
- **Authoritative human role or system:** Privacy Officer (declares the
  retention design upstream).
- **Signal source:** Azure deployment tags on the validation request.
- **Authoritative decision or enforcement surface:** Azure Policy `deny`
  effect, evaluated by `az deployment group validate`.
- **Authoritative evidence source:** The Azure CLI validation result
  (`RequestDisallowedByPolicy` or success), captured verbatim by the demo
  runner.
- **ACS intervention point, if applicable:** Not applicable.
- **AGT capability, if applicable:** Not applicable.
- **Foundry/Azure services:** Azure Policy, Azure Resource Manager deployment
  validation, Microsoft Entra (CLI identity). Microsoft Foundry is named only
  as example governed context.
- **Governance action:** Block go-live until the retention design is complete.
- **Evidence artifact:** JSON record with control ID, policy version, all four
  scenario results, correlation names, timestamp, `resource_created: false`,
  and accountable role.
- **Healthy/complete scenario:** `governedDataPresent=true` with all five
  retention tags present and valid → validated.
- **Policy-triggering scenario:** `governedDataPresent=true` with the
  retention tags entirely missing, or present but invalid
  (`retentionPeriodDays=0`, invalid disposition) → denied.
- **Unavailable, incomplete, or ambiguous scenario:** `governedDataPresent=false`
  with no retention tags → validated, proving the gate does not over-trigger
  when no governed data is declared.

## Complexity budget

- **Why each custom component is necessary:** The Bicep policy definition and
  assignment are the only way to express this organization-specific
  design-completeness rule as a real Azure decision; no built-in policy exists.
  The two shell scripts exist only to make deployment, validation, and cleanup
  repeatable and to project a safe evidence record.
- **Files and dependencies used by the core, validation, or optional path:**
  Every file in this control's directory is invoked by `demo.sh`,
  `validate.sh`, `infra/deploy.sh`, or `infra/cleanup.sh`. No Python source or
  test directory is added, matching PRI-PRE-001's pure Bicep-and-bash design.
- **Interfaces, agents, stores, or resources deliberately omitted:** No
  application, database, agent, or persistent workload resource. No local
  shadow decision or evidence store beside Azure Policy's own result.
- **How disconnected or shadow evidence is avoided:** The evidence record only
  restates the real Azure CLI result strings for each scenario; the runner
  fails if a result differs from what Azure actually returned.
- **Metadata/configuration edge cases, if applicable:** Covered explicitly:
  missing tags (`missing` scenario), invalid tag values (`invalid` scenario),
  complete and valid tags (`healthy` scenario), and the not-applicable case
  where no governed data is declared (`not-applicable` scenario).

## Community fit

- **Learning level:** Foundation
- **Estimated completion time:** 15–20 minutes, including policy propagation
- **Minimum prerequisites:** Azure CLI signed in, an existing resource group,
  and subscription-scope permission to create a custom policy definition.
- **Why the core demo remains accessible:** It reuses the exact PRI-PRE-001
  pattern; only the tag schema and policy rule differ.
- **Intentional simplifications:** Tags stand in for an authoritative
  retention register; a declared retention period is not checked against any
  real Log Analytics/storage setting.
- **Further exploration to document rather than implement:** Comparing the
  declared `retentionPeriodDays` tag against the real `retentionInDays` on an
  actual Log Analytics table using
  `az monitor log-analytics workspace table show`.
- **Optional community exploration paths:** Grouping this rule into an Azure
  Policy initiative alongside PRI-PRE-001/PRI-PRE-002.

## Scope boundary

- **Included:** A Pre-Live gate on retention-design completeness for a
  declared-governed-data go-live request, expressed as a custom Azure Policy
  `deny` rule, validated across four scenarios.
- **Explicitly excluded:** Detecting or classifying which systems actually
  hold governed data; verifying a declared retention period against a real
  Log Analytics/storage configuration; DPIA or lawful-basis review (covered by
  PRI-PRE-001/002); Live-phase retention violations (covered by PRI-002).
- **What the demo proves:** Azure Policy can deterministically deny the
  demonstrated go-live request when any part of a declared retention design is
  missing or invalid, and validates it once the design is complete or genuinely
  not applicable.
- **What the demo does not prove:** Regulatory compliance, accuracy of the
  declared retention period, or that every organizational deployment supplies
  the trigger tags.
- **Is the core control correct and safe within this boundary?** Yes — the
  decision is deterministic, fails closed on missing/invalid metadata, and
  creates no persistent workload.

## Decision

- **Proceed / revise / reject:** Proceed with the Azure Policy-only
  implementation, directly templated on PRI-PRE-001.
- **Rationale:** It uses the supported capability directly, proves a real deny
  result across four scenarios, fills a genuine capability gap (no Azure
  Policy built-in exists for retention-design completeness or for auditing
  Log Analytics retention settings), and remains distinct from the Live-phase
  PRI-002 demo and the DPIA-focused PRI-PRE-001/002 demos.
- **Review date:** 2026-09-04
- **Authoritative references:**
  - [Azure Policy `deny` effect](https://learn.microsoft.com/en-us/azure/governance/policy/concepts/effect-deny)
  - [Azure Policy definition structure](https://learn.microsoft.com/en-us/azure/governance/policy/concepts/definition-structure-policy-rule)
  - [Manage Data Retention in a Log Analytics Workspace](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/data-retention-configure)
  - [Foundry tracing and data handling](https://learn.microsoft.com/azure/foundry/observability/concepts/trace-data)
  - [Purview retention policies for Copilot and AI apps](https://learn.microsoft.com/en-us/purview/retention-policies-copilot)
