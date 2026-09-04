# PRI-PRE-001 — control assessment

## Proposed control

- **Risk:** A known high-risk AI system reaches go-live without approved DPIA
  evidence.
- **Required decision:** Allow or deny the demonstrated deployment request.
- **Governance action:** Block go-live until the metadata is remediated.
- **Required evidence:** Azure Policy result, policy version and identifiers,
  deployment correlation name, timestamp, and accountable role.

## Enforcement classification

- **Configuration assessment:** The high-risk classification and DPIA evidence
  are represented as deployment metadata.
- **Deterministic enforcement:** Azure Policy is the only decision engine.
- **Model-assisted evaluation:** Not applicable.
- **Human approval:** A DPO decision is assumed to have happened upstream and is
  represented only by an opaque evidence identifier.
- **Fail-closed behavior:** A tagged high-risk go-live request without both an
  approved status and non-empty evidence identifier is denied.

**Model/Foundry role: Explanatory only.** Azure Policy's `deny` effect is the
sole decision engine and enforcement point; no Foundry agent or ACS
intervention point is part of the core demo, because the authoritative
signal is Azure resource deployment metadata with no agent action in the
loop. There is no local approval registry to mediate — the DPO approval
itself happens upstream and is represented only by the opaque evidence
identifier Azure Policy evaluates.

## Existing capability review

| Capability | Applicable? | Reuse decision |
|---|---:|---|
| Azure Policy | Yes | Core capability: use the native `deny` effect and deployment validation. |
| Microsoft Agent Governance Toolkit | Not in the core | Approval workflows become relevant only if an agent initiates or records the DPIA approval action. |
| Agent Control Specification | Not in the core | No model or agent tool call is part of Azure resource admission. |
| Microsoft Foundry | Not in the core | A Foundry agent would only narrate the policy result and would not improve this learning outcome. |
| Microsoft Purview / Priva | Context only | An organization may track assessments or privacy work there, but this demo does not claim either product is a complete DPIA or ROPA system. |
| Microsoft Entra | Yes | The Azure CLI uses the signed-in identity; no credential is embedded in the demo. |

## Existing samples and overlap

Azure Policy already supplies the enforcement mechanism. Reimplementing a
local risk scorer, approval protocol, policy engine, storage register, or agent
would duplicate capabilities or expand the scope. The repository-specific
learning outcome is the translation of a privacy control into a minimal,
observable `deny` example and its contrast with PRI-PRE-002's `audit` example.

## Smallest useful demo

- **Classification:** `DEMONSTRATE`
- **Demo format:** `DEPLOYABLE_DEMO`
- **Deployment requirement:** Required; the real Azure Policy decision is the
  learning outcome.
- **Core path:** Deploy definition and assignment; validate one incomplete and
  one remediated request; create no workload.
- **Custom code:** Two small shell scripts for repeatability and evidence
  projection, plus Bicep for the policy and harmless validation target.
- **Advanced extension:** Connect the trigger metadata to an authoritative AI
  inventory/release process or an AGT-backed approval flow.

## Community and safety boundary

- Foundation-level and runnable in approximately 15–20 minutes.
- Synthetic metadata only; no PII, DPIA document, approver identity, prompt, or
  model is processed.
- The demo assumes trusted high-risk classification and trigger metadata. It
  explicitly does not claim universal deployment coverage or legal compliance.
- Cleanup removes only the control's policy assignment and definition.

## Decision

- **Proceed / revise / reject:** Proceed with the simplified Azure Policy-only
  implementation.
- **Reason:** It uses the supported capability directly, proves a real deny
  result, removes disconnected application logic, and remains distinct from the
  non-blocking PRI-PRE-002 demo.
- **Review date:** 2026-09-04
- **References:**
  - [Azure Policy `deny` effect](https://learn.microsoft.com/en-us/azure/governance/policy/concepts/effect-deny)
  - [Azure Policy definition structure](https://learn.microsoft.com/en-us/azure/governance/policy/concepts/definition-structure-policy-rule)
  - [AGT approval workflows](https://github.com/microsoft/agent-governance-toolkit/blob/main/docs/tutorials/38-approval-workflows.md)
