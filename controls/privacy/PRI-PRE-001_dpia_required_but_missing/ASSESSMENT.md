# PRI-PRE-001 — control assessment

Complete this assessment before creating exercise artifacts, implementation
code, or infrastructure.

## Candidate

- **Control ID:** PRI-PRE-001
- **Name:** DPIA required but missing
- **Lifecycle phase:** Pre-Live
- **Accountable role:** DPO

## Governance problem

- **Risk:** A new AI-powered feature or project that meets GDPR Article 35
  high-risk criteria (special category data, automated decision-making,
  large-scale monitoring, vulnerable data subjects) goes live without a
  completed Data Protection Impact Assessment, leaving a legally required
  risk assessment undone until a regulator, auditor, or incident forces the
  question.
- **Control objective:** Independently compute whether a DPIA is required
  for a given AI system or project from its declared risk factors, verify
  whether valid DPIA evidence exists, and make "go-live" technically
  impossible without that evidence — using a real, independent enforcement
  mechanism rather than a check the application itself could bypass.
- **Authoritative signal:** A synthetic AI-system/project register entry
  (risk factors + DPIA status/approver/date/report id) and the real
  evaluation result of an Azure Policy assignment against resource tags
  mirroring that entry.
- **Required decision:** Allowed, blocked, or blocked-unknown (risk factors
  themselves missing or invalid) for each project's go-live attempt.
- **Required governance action:** Block go-live.
- **Required evidence:** Decision, risk factor count, whether a DPIA was
  required, whether evidence was complete, whether Azure's own policy
  evaluation agreed — never the DPIA approver's name or the report
  identifier itself.

## Enforcement classification

- **Deterministic policy:** Yes — the risk-score computation and the
  evidence-completeness check are pure, timezone-aware functions with no
  model involvement.
- **Model-assisted evaluation:** No decision authority; Microsoft Foundry
  only explains the already-computed, metadata-safe result to the DPO.
- **Human approval:** Not required for this control's core demo — the
  gate itself is the enforcement point; a real organization's actual DPIA
  approval workflow is out of scope and represented only as pre-existing
  evidence (tags) on the record.
- **Configuration assessment:** Yes — the go-live attempt is fundamentally
  a check of the AI system's declared configuration (tags) against policy.
- **Monitoring/detection:** On-demand scan of the synthetic register in
  this demo; a production system would evaluate at CI/CD or resource
  admission time.
- **Required fail-closed behavior:** A record whose risk factors are
  missing or invalid is blocked from automatic clearance, never treated as
  low-risk by default.

## Existing capability review

| Capability | Applicable? | What it already provides | Reuse decision |
|---|---:|---|---|
| Microsoft Agent Governance Toolkit | Partial | Action-bound approval protocol (proposed, not yet implemented in AGT) could formalize a real DPIA sign-off workflow | Document as production extension, not used in core demo |
| Agent Control Specification | Partial | `pre_tool_call` intervention point if go-live requests become an agent tool | Document as production extension, not used in core demo |
| Microsoft Foundry | Yes | Agent Framework hosts a non-authoritative explanation agent | Reused for explanation only |
| Foundry Control Plane | No | Not applicable to this control's scope | Not used |
| Azure API Management AI Gateway | No | Not applicable; no inbound model traffic to mediate | Not used |
| Microsoft Purview | No | Compliance Manager assessments track regulatory controls generally, not a per-deployment technical go-live gate | Documented as further exploration, not used in core demo |
| Microsoft Defender | No | Not applicable | Not used |
| Microsoft Entra | Yes | Entra ID authenticates the local demo identity for storage and policy operations | Reused |
| Azure AI Content Safety / Language | No | Not applicable; no free-text content to scan in this control | Not used |
| Azure Monitor / Application Insights / OTel | No | Not the primary enforcement mechanism for this control | Not used |
| Other supported Microsoft capability | Yes | **Azure Policy** (`deny` effect, tag-based conditions, `validate`-time evaluation) is the authoritative, purpose-built Azure mechanism for blocking a resource operation that doesn't meet a governance condition | Reused as the primary enforcement capability |

## Existing samples and implementations

| Repository, documentation, or sample | Overlap | What is still missing |
|---|---|---|
| [Azure Policy definition structure](https://learn.microsoft.com/en-us/azure/governance/policy/concepts/definition-structure-policy-rule) | Documents `deny` effect authoring and tag-based conditions used here | A runnable demo pairing a deterministic DPIA-required decision with a real policy-backed gate; the doc is guidance, not a control demo |
| PRI-003 (this repository) | Deterministic scanner + Table Storage register + non-authoritative Foundry agent + guarded action | A go-live/compliance-gate domain model instead of an SLA domain model; a real Azure Policy deny evaluation instead of an application-level guarded delete |
| Microsoft Priva / Purview Compliance Manager | General DPIA/assessment tracking at the Microsoft 365/tenant level | A lightweight, dependency-free technical gate demonstrable without an M365 E5/Priva or full Compliance Manager tenant setup |

Use official legislation, regulators, and standards bodies for normative legal
or regulatory claims. Use authoritative Microsoft sources for Microsoft product
capabilities and implementation guidance. Record current URLs and the review
date. Do not rely on an old sample to infer current support.

## Repository overlap

- **Related Forged with Foundry controls:** PRI-003 (Table Storage
  register + deterministic scanner + guarded action + non-authoritative
  Foundry explanation) is the closest structural template; no other
  control in the repository uses Azure Policy or targets the Pre-Live
  lifecycle phase.
- **Existing components that can be reused:** The PRI-00x code shape
  (models/policy/evidence/storage/agent/chat separation) is reused as a
  structural pattern only; no code is imported across controls per the
  bite-sized-scope rule.
- **Risk of duplicating an existing demo:** Low — no other control
  evaluates DPIA-required status or uses Azure Policy as an enforcement
  mechanism.

## Proposed contribution

- **Classification:** `COMPOSE`
- **Demo format:** `DEPLOYABLE_DEMO`
- **Deployment:** Required for the core learning outcome — the entire
  point is showing Azure's own policy engine independently refuse a
  non-compliant request.
- **Existing capabilities reused:** Azure Policy (`deny` effect, tag
  conditions, `validate`-time evaluation), Azure Table Storage, Microsoft
  Entra ID, Microsoft Foundry Agent Framework.
- **Minimum custom implementation or artifacts:** The multi-factor
  risk-score policy, the DPIA-evidence-completeness guard, the custom
  policy definition's JSON rule (a single authored rule, not a policy
  engine), and the teaching orchestration.
- **Unique learning outcome:** Show that computing whether a DPIA is
  required, checking whether valid DPIA evidence exists, and actually
  blocking go-live are three separate governance decisions — and that the
  last one is safest when backed by a platform mechanism (Azure Policy)
  that keeps working even if the application's own code is bypassed.
- **Why an existing official sample is insufficient:** Microsoft's Azure
  Policy documentation shows how to author `deny` rules but does not pair
  one with a DPIA-required decision, a synthetic compliance register, or
  an explanation agent.
- **Why this deserves a separate bite-sized demo:** It is the first
  Pre-Live-phase, compliance-gate-style control in this repository and
  establishes the pattern (a real platform enforcement mechanism, not
  custom app-level gating) for the ~40 other planned Pre-Live controls.
- **Why deployment is or is not justified:** The core teaching point —
  Azure itself refusing a request — cannot be demonstrated without a real
  Azure Policy definition and assignment; a guided exercise could not show
  this authentically.

## Smallest useful design

- **Primary governance decision:** Allowed, blocked, or blocked-unknown for
  each project's go-live attempt.
- **Authoritative human role or system:** The DPO's completed DPIA
  (represented as evidence tags); ultimately, Azure Policy's own deny
  evaluation is the authoritative technical backstop.
- **Signal source:** A dedicated Azure Table Storage register of synthetic
  AI-system/project records (risk factors + DPIA status/approver/date/
  report id), populated with synthetic data only.
- **ACS intervention point, if applicable:** `pre_tool_call`, if go-live
  requests are later exposed as an agent tool (not in the core demo).
- **AGT capability, if applicable:** Action-bound approval protocol
  (proposed, not yet implemented in AGT), as a
  production replacement for representing a real DPIA sign-off workflow.
- **Foundry/Azure services:** Microsoft Foundry Agent Framework
  (explanation only), Azure Table Storage, Azure Policy, Microsoft Entra
  ID.
- **Governance action:** Block go-live, enforced by a real Azure Policy
  `deny` assignment evaluated via `az deployment group validate` against a
  trivial placeholder template carrying the project's tags — no billable
  resource is ever created.
- **Evidence artifact:** Metadata-only record: decision id, risk factor
  count, DPIA-required flag, evidence-complete flag, whether Azure's real
  policy evaluation agreed, accountable role.
- **Healthy/complete scenario:** A low-risk project (risk score below
  threshold; no DPIA required) and a high-risk project with complete DPIA
  evidence — both `ALLOWED`.
- **Policy-triggering scenario:** A high-risk project with missing or
  incomplete DPIA evidence — `BLOCKED`, and the real `validate` call
  independently returns `RequestDisallowedByPolicy`.
- **Unavailable, incomplete, or ambiguous scenario:** A project whose risk
  factors are missing or unrecognized — `BLOCKED_UNKNOWN`, fails closed
  rather than defaulting to low-risk.

## Community fit

- **Learning level:** Advanced
- **Estimated completion time:** 45–60 minutes after Azure access is
  available (requires subscription-scope permissions in addition to the
  usual resource-group scope).
- **Minimum prerequisites:** Python 3.10–3.13, `az login`, shared Foundry
  infrastructure, PRI-PRE-001 infrastructure, and **Resource Policy
  Contributor (or equivalent) at subscription scope** — a new, more
  elevated prerequisite than PRI-001–004 required.
- **Why the core demo remains accessible:** The go-live attempt uses
  `az deployment group validate`, so no real resource is ever created or
  needs cleanup; the policy JSON itself is short and fully shown in the
  README.
- **Intentional simplifications:** Synthetic register only; a fixed,
  illustrative risk-factor threshold rather than a full legal risk
  methodology; DPIA evidence represented as tags rather than a real
  document management/e-signature system; local, metadata-only evidence.
- **Further exploration to document rather than implement:** AGT
  action-bound approval for a real DPIA sign-off workflow, ACS
  `pre_tool_call` mediation, Microsoft Priva/Purview Compliance Manager
  integration, CI/CD pipeline gate integration (GitHub Actions/Azure
  DevOps required checks).
- **Optional community exploration paths:** Extend the policy to a full
  initiative (policy set) covering multiple compliance gates at once
  (DPIA, lawful basis, retention design) mirroring the other planned
  `PRI-PRE-*` controls.

## Scope boundary

- **Included:** Seed synthetic AI-system/project records (including one
  with unknown/invalid risk factors), scan and classify them
  deterministically, let a Foundry agent explain the metadata-safe result,
  and attempt a real, guarded go-live check via Azure Policy for both an
  allowed and a blocked project.
- **Explicitly excluded:** A real DPIA authoring or e-signature workflow,
  integration with an actual CI/CD pipeline, creation of any real billable
  go-live resource, and any destructive action beyond a validate-time
  policy check.
- **What the demo proves:** The risk-score and evidence-completeness
  checks are deterministic and independent of the model; a project with
  incomplete DPIA evidence is blocked; Azure's own policy engine
  independently agrees with the deterministic decision at validate time,
  not just the application's own code.
- **What the demo does not prove:** Regulatory compliance, that the
  risk-factor list is legally complete, that every real deployment path in
  an organization is mediated by this same policy, or that DPIA content
  itself is adequate.
- **Is the core control correct and safe within this boundary?** Yes — no
  real personal data is processed, no billable resource is created, and
  the only "action" demonstrated is a real, non-destructive Azure Policy
  evaluation.

## Decision

- **Proceed / revise / reject:** Proceed with the boundary above.
- **Rationale:** The control teaches a distinct signal (pre-deployment
  compliance gating) and reuses the real, purpose-built Azure Policy
  `deny` mechanism instead of reimplementing a gate in application code,
  establishing an authentic pattern for the repository's other planned
  Pre-Live controls.
- **Review date:** 2026-09-04
- **Authoritative references:**
  - [Azure Policy definition structure — policy rules](https://learn.microsoft.com/en-us/azure/governance/policy/concepts/definition-structure-policy-rule)
  - [Azure Policy definitions effect basics](https://learn.microsoft.com/en-us/azure/governance/policy/concepts/effect-basics)
  - [Microsoft.Authorization/policyDefinitions template reference](https://learn.microsoft.com/en-us/azure/templates/microsoft.authorization/policydefinitions)
  - [Article 35 GDPR — Data protection impact assessment](https://gdpr-info.eu/art-35-gdpr/)
  - [EDPB / WP29 Guidelines on Data Protection Impact Assessment (wp248rev.01)](https://ec.europa.eu/newsroom/article29/items/611236)
  - [ICO — When do we need to do a DPIA?](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/data-protection-impact-assessments-dpias/data-protection-impact-assessments/)
  - [AGT action-bound approval protocol (proposed, not yet implemented in AGT)](https://github.com/microsoft/agent-governance-toolkit/blob/main/docs/adr/0030-action-bound-approval-protocol.md)
  - [Agent Control Specification](https://github.com/microsoft/agent-governance-toolkit/tree/main/policy-engine)
