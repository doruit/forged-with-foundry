# PRI-PRE-002 — control assessment

Complete this assessment before creating exercise artifacts, implementation
code, or infrastructure.

## Candidate

- **Control ID:** PRI-PRE-002
- **Name:** Lawful basis or purpose missing
- **Lifecycle phase:** Pre-Live
- **Accountable role:** Privacy Officer

## Governance problem

- **Risk:** A project or feature processes personal data without a
  documented GDPR Article 6(1) lawful basis or a defined processing
  purpose (Article 5(1)(b) purpose limitation), and this gap is only
  discovered during an audit or incident rather than before go-live.
- **Control objective:** Independently detect, for a given project, whether
  it processes personal data, whether a valid lawful basis is on file, and
  whether a processing purpose is documented — and flag any gap for design
  remediation using a real, independent Azure mechanism rather than a
  check the application itself could bypass or silently skip.
- **Authoritative signal:** A synthetic AI-system/project register entry
  (personal-data flag, lawful basis, purpose id) and the real compliance
  result of an Azure Policy assignment against resource tags mirroring
  that entry.
- **Required decision:** Allowed (not applicable), compliant, flagged
  (missing basis or purpose), or flagged-unknown (an unrecognized lawful
  basis value) for each project.
- **Required governance action:** Remediate design — flag the gap so the
  team fixes it, not a hard deployment block.
- **Required evidence:** Decision, whether the project processes personal
  data, whether the lawful basis is valid, whether a purpose is
  documented, whether Azure's own policy evaluation agreed.

## Enforcement classification

- **Deterministic policy:** Yes — the lawful-basis validation and
  purpose-presence check are pure functions with no model involvement.
- **Model-assisted evaluation:** No decision authority; Microsoft Foundry
  only explains the already-computed, metadata-safe result to the Privacy
  Officer.
- **Human approval:** Not required for this control's core demo — a real
  organization's actual lawful-basis determination process is out of
  scope and represented only as pre-existing evidence (tags) on the
  record.
- **Configuration assessment:** Yes — the check is fundamentally a review
  of the project's declared configuration (tags) against policy.
- **Monitoring/detection:** On-demand scan of the synthetic register in
  this demo; the real enforcement backstop is Azure Policy's `audit`
  effect, which flags non-compliance in the compliance report rather than
  blocking the request.
- **Required fail-closed behavior:** A record whose lawful-basis value is
  present but doesn't match a recognized GDPR Article 6(1) category is
  flagged as unknown, never treated as compliant by default.

## Existing capability review

| Capability | Applicable? | What it already provides | Reuse decision |
|---|---:|---|---|
| Microsoft Agent Governance Toolkit | Partial | Action-bound approval protocol (proposed, not yet implemented in AGT) could formalize a real lawful-basis sign-off workflow | Document as production extension, not used in core demo |
| Agent Control Specification | Partial | `pre_tool_call` intervention point if this check becomes an agent tool | Document as production extension, not used in core demo |
| Microsoft Foundry | Yes | Agent Framework hosts a non-authoritative explanation agent | Reused for explanation only |
| Foundry Control Plane | No | Not applicable to this control's scope | Not used |
| Azure API Management AI Gateway | No | Not applicable; no inbound model traffic to mediate | Not used |
| Microsoft Purview | No | Compliance Manager assessments track regulatory controls generally, not a per-project lawful-basis technical flag | Documented as further exploration, not used in core demo |
| Microsoft Defender | No | Not applicable | Not used |
| Microsoft Entra | Yes | Entra ID authenticates the local demo identity for storage and policy operations | Reused |
| Azure AI Content Safety / Language | No | Not applicable; no free-text content to scan in this control | Not used |
| Azure Monitor / Application Insights / OTel | No | Not the primary enforcement mechanism for this control | Not used |
| Other supported Microsoft capability | Yes | **Azure Policy** (`audit` effect, tag-based `notIn` enum conditions) is the authoritative, purpose-built Azure mechanism for flagging non-compliant resources without blocking them | Reused as the primary enforcement capability |

## Existing samples and implementations

| Repository, documentation, or sample | Overlap | What is still missing |
|---|---|---|
| [Azure Policy audit effect](https://learn.microsoft.com/en-us/azure/governance/policy/concepts/effect-audit) | Documents `audit` effect authoring and compliance-evaluation timing used here | A runnable demo pairing a deterministic lawful-basis decision with a real audit-backed flag; the doc is guidance, not a control demo |
| PRI-PRE-001 (this repository) | Deterministic scanner + Table Storage register + non-authoritative Foundry agent + subscription-scope custom Azure Policy | A lawful-basis/purpose domain model instead of a DPIA domain model; the `audit` effect and its asynchronous, non-blocking verification path instead of `deny` and instant `validate`-time blocking |
| Microsoft Priva / Purview Compliance Manager | General lawful-basis/processing-purpose tracking at the Microsoft 365/tenant level | A lightweight, dependency-free technical flag demonstrable without an M365 E5/Priva or full Compliance Manager tenant setup |

Use official legislation, regulators, and standards bodies for normative legal
or regulatory claims. Use authoritative Microsoft sources for Microsoft product
capabilities and implementation guidance. Record current URLs and the review
date. Do not rely on an old sample to infer current support.

## Repository overlap

- **Related Forged with Foundry controls:** PRI-PRE-001 (same lifecycle
  phase, same Table Storage register + deterministic scanner + guarded
  Azure Policy pattern) is the closest structural template. It is not a
  duplicate: PRI-PRE-001 evaluates DPIA completeness and blocks go-live
  with `deny`; this control evaluates lawful basis/purpose and flags for
  remediation with `audit` — a different governance decision and a
  different, non-blocking enforcement mechanism with different
  verification timing.
- **Existing components that can be reused:** The PRI-PRE-00x code shape
  (models/policy/evidence/storage/agent/chat separation) is reused as a
  structural pattern only; no code is imported across controls per the
  bite-sized-scope rule.
- **Risk of duplicating an existing demo:** Low — no other control
  evaluates lawful basis or purpose documentation, or uses Azure Policy's
  `audit` effect.

## Proposed contribution

- **Classification:** `COMPOSE`
- **Demo format:** `DEPLOYABLE_DEMO`
- **Deployment:** Required for the core learning outcome — the point is
  showing Azure's own compliance engine independently flag a
  non-compliant resource without blocking it.
- **Existing capabilities reused:** Azure Policy (`audit` effect, tag
  `notIn` enum conditions), Azure Table Storage, Microsoft Entra ID,
  Microsoft Foundry Agent Framework.
- **Minimum custom implementation or artifacts:** The lawful-basis/purpose
  evaluation policy, the custom policy definition's JSON rule, and the
  teaching orchestration.
- **Unique learning outcome:** Contrast a hard block (`deny`, instant
  `validate`-time proof, as in PRI-PRE-001) with an advisory flag
  (`audit`, asynchronous compliance-report proof) — both are real Azure
  Policy enforcement, but they fit different governance actions and carry
  different verification timing.
- **Why an existing official sample is insufficient:** Microsoft's Azure
  Policy documentation shows how to author `audit` rules but does not pair
  one with a lawful-basis/purpose decision, a synthetic compliance
  register, or an explanation agent.
- **Why this deserves a separate bite-sized demo:** It demonstrates that
  not every governance gate should be a hard block, and shows how to
  verify an `audit`-effect policy honestly, including its asynchronous
  timing — a pattern the ~40 other planned Pre-Live controls will need.
- **Why deployment is or is not justified:** The core teaching point —
  Azure's own compliance engine flagging a resource — cannot be
  demonstrated without a real Azure Policy definition and assignment; a
  guided exercise could not show this authentically.

## Smallest useful design

- **Primary governance decision:** Allowed (not applicable), compliant,
  flagged, or flagged-unknown for each project.
- **Authoritative human role or system:** The Privacy Officer's lawful
  basis and purpose determination (represented as evidence tags);
  ultimately, Azure Policy's own audit evaluation is the authoritative
  technical compliance signal.
- **Signal source:** A dedicated Azure Table Storage register of
  synthetic AI-system/project records (personal-data flag, lawful basis,
  purpose id), populated with synthetic data only.
- **ACS intervention point, if applicable:** `pre_tool_call`, if this
  check is later exposed as an agent tool (not in the core demo).
- **AGT capability, if applicable:** Action-bound approval protocol
  (proposed, not yet implemented in AGT), as a
  production replacement for representing a real lawful-basis
  determination workflow.
- **Foundry/Azure services:** Microsoft Foundry Agent Framework
  (explanation only), Azure Table Storage, Azure Policy, Microsoft Entra
  ID.
- **Governance action:** Remediate design, enforced by a real Azure
  Policy `audit` assignment. Because `audit` never blocks and its
  compliance result is not visible through `validate`, this control's
  proof is a documented manual walkthrough (tag the real storage account,
  trigger a compliance scan, and check the result) rather than an in-app
  action — no billable resource is ever created.
- **Evidence artifact:** Metadata-only record: decision id, whether the
  project processes personal data, whether the lawful basis is valid,
  whether a purpose is documented, accountable role.
- **Healthy/complete scenario:** A project that does not process personal
  data, and a project with a valid lawful basis and documented purpose —
  both `ALLOWED`/`COMPLIANT`.
- **Policy-triggering scenario:** A project processing personal data with
  a missing lawful basis or purpose — `FLAGGED`, and the real Azure
  Policy audit evaluation independently marks the equivalent tags
  non-compliant.
- **Unavailable, incomplete, or ambiguous scenario:** A project whose
  declared lawful basis doesn't match a recognized GDPR Article 6(1)
  category — `FLAGGED_UNKNOWN`, fails closed rather than defaulting to
  compliant.

## Community fit

- **Learning level:** Advanced
- **Estimated completion time:** 30–45 minutes for the interactive demo;
  the optional manual Azure verification walkthrough adds a real,
  asynchronous wait (up to ~15 minutes, or an on-demand scan of
  unspecified duration).
- **Minimum prerequisites:** Python 3.10–3.13, `az login`, shared Foundry
  infrastructure, PRI-PRE-002 infrastructure, and Resource Policy
  Contributor (or equivalent) at subscription scope for the one-time
  policy definition deployment.
- **Why the core demo remains accessible:** The interactive demo (seed,
  scan, explain, cleanup) completes instantly; the asynchronous Azure
  verification is optional, documented, and clearly scoped separately.
- **Intentional simplifications:** Synthetic register only; the 6-value
  GDPR Article 6(1) enum as the only recognized lawful bases, not a full
  legal methodology; lawful basis and purpose represented as tags rather
  than a real record-of-processing-activities system; local,
  metadata-only evidence.
- **Further exploration to document rather than implement:** AGT
  action-bound approval for a real lawful-basis sign-off workflow, ACS
  `pre_tool_call` mediation, Microsoft Priva/Purview Compliance Manager
  integration, extending the policy to a full initiative covering
  multiple Pre-Live gates (DPIA, lawful basis, retention design).
- **Optional community exploration paths:** Wire the on-demand compliance
  scan into a scheduled GitHub Actions/Azure DevOps job so flagged
  projects surface automatically instead of on request.

## Scope boundary

- **Included:** Seed synthetic AI-system/project records (including one
  with an unrecognized lawful-basis value), scan and classify them
  deterministically, let a Foundry agent explain the metadata-safe
  result, and document a real, manual Azure Policy audit verification
  walkthrough.
- **Explicitly excluded:** A real record-of-processing-activities
  workflow, integration with an actual CI/CD pipeline, creation of any
  real billable resource, and any in-app action that implies instant
  Azure verification (architecturally not possible for `audit`).
- **What the demo proves:** The lawful-basis and purpose checks are
  deterministic and independent of the model; a project with a missing or
  unrecognized lawful basis is flagged rather than defaulting to
  compliant; Azure's own policy engine independently agrees with the
  deterministic decision, on its own asynchronous compliance-evaluation
  timeline.
- **What the demo does not prove:** Regulatory compliance, that the
  6-category lawful-basis list is the organization's complete legal
  methodology, that every real deployment path is mediated by this same
  policy, or that a declared purpose is itself adequate or accurate.
- **Is the core control correct and safe within this boundary?** Yes — no
  real personal data is processed, no billable resource is created, and
  the only Azure-side verification demonstrated is a real, non-blocking
  compliance evaluation on the control's own already-deployed storage
  account.

## Decision

- **Proceed / revise / reject:** Proceed with the boundary above.
- **Rationale:** The control teaches a distinct signal (lawful basis and
  purpose limitation) and a distinct, non-blocking Azure Policy
  enforcement mechanism (`audit`), complementing PRI-PRE-001's `deny`
  pattern without duplicating it.
- **Review date:** 2026-09-04
- **Authoritative references:**
  - [Azure Policy definitions audit effect](https://learn.microsoft.com/en-us/azure/governance/policy/concepts/effect-audit)
  - [Get policy compliance data — evaluation triggers and timing](https://learn.microsoft.com/en-us/azure/governance/policy/how-to/get-compliance-data)
  - GDPR Article 6(1) lawful bases for processing and Article 5(1)(b)
    purpose limitation (EU General Data Protection Regulation) — cited
    for illustrative screening criteria only, not legal advice.
