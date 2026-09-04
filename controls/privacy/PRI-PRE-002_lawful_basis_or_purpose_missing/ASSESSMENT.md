# PRI-PRE-002 — control assessment

## Proposed control

- **Risk:** A personal-data go-live request lacks a recognized lawful basis or
  documented purpose reference.
- **Required decision:** Compliant or non-compliant for the demonstrated Azure
  resource.
- **Governance action:** Flag the resource for design remediation without
  blocking deployment.
- **Required evidence:** Azure Policy compliance state, policy and resource
  identifiers, evaluation timestamp, and accountable role.

## Enforcement classification

- **Configuration assessment and detection:** Azure Policy evaluates resource
  metadata asynchronously.
- **Deterministic enforcement:** Azure Policy is the only decision engine.
- **Model-assisted evaluation:** Not applicable.
- **Human approval:** The Privacy Officer chooses and records the real lawful
  basis outside this control.
- **Fail-closed behavior:** Within the explicitly tagged demo scope, missing,
  empty, or unrecognized values are non-compliant.

**Model/Foundry role: Explanatory only.** Azure Policy's `audit` effect is
the sole decision engine; no Foundry agent or ACS intervention point is part
of the core demo, because the authoritative signal is Azure resource
configuration compliance with no agent action in the loop. There is no local
approval registry to mediate — the Privacy Officer's lawful-basis choice
happens upstream and is represented only by the resource metadata Azure
Policy evaluates.

## Existing capability review

| Capability | Applicable? | Reuse decision |
|---|---:|---|
| Azure Policy | Yes | Core capability: use the native `audit` effect and compliance state. |
| Microsoft Agent Governance Toolkit | Not in the core | Approval workflows become relevant only if an agent initiates or records the lawful-basis decision. |
| Agent Control Specification | Not in the core | No agent tool call or runtime checkpoint is involved. |
| Microsoft Foundry | Not in the core | A Foundry agent would only narrate the Azure result and add cost and setup. |
| Microsoft Purview / Priva | Context only | These products can support broader compliance or privacy processes, but this demo does not present them as a ROPA system. |
| Microsoft Entra | Yes | The Azure CLI uses the signed-in identity; no credential is embedded in the demo. |

## Existing samples and overlap

Azure Policy already supplies the audit capability. A separate Table Storage
register, Python policy, evidence logger, and explanation agent would create a
second, disconnected decision path. The repository-specific learning outcome is
the privacy-control composition: one real resource moves from `NonCompliant` to
`Compliant`, visibly contrasting `audit` with PRI-PRE-001's `deny` behavior.

## Smallest useful demo

- **Classification:** `DEMONSTRATE`
- **Demo format:** `DEPLOYABLE_DEMO`
- **Deployment requirement:** Required; asynchronous Azure Policy compliance is
  the behavior being taught.
- **Core path:** Deploy definition and assignment; deploy one disabled Action
  Group with incomplete metadata; inspect state; remediate the same resource;
  inspect state again; clean up.
- **Custom code:** Small shell scripts for repeatability and a Bicep target with
  no receivers or operational behavior.
- **Advanced extension:** Source metadata from an authoritative privacy
  register or automate evidence collection in a release workflow.

## Community and safety boundary

- Foundation-level; the only unavoidable complexity is asynchronous policy
  evaluation.
- Synthetic tags only; no PII, purpose text, prompt, or model is processed.
- The demo validates presence and an illustrative enum, not truthfulness,
  adequacy, or legal compliance.
- Cleanup removes the temporary Action Group, policy assignment, and policy
  definition without touching the resource group.

## Decision

- **Proceed / revise / reject:** Proceed with the simplified Azure Policy-only
  implementation.
- **Reason:** It uses the supported capability directly and makes one
  authoritative before/after compliance path observable without duplicated
  policy logic.
- **Review date:** 2026-09-04
- **References:**
  - [Azure Policy `audit` effect](https://learn.microsoft.com/en-us/azure/governance/policy/concepts/effect-audit)
  - [Get Azure Policy compliance data](https://learn.microsoft.com/en-us/azure/governance/policy/how-to/get-compliance-data)
  - [AGT approval workflows](https://github.com/microsoft/agent-governance-toolkit/blob/main/docs/tutorials/38-approval-workflows.md)
