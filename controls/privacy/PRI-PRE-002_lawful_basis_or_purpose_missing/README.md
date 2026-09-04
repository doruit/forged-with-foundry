<p align="center">
  <img src="../../../media/themepack/fwf-badge-small-only-logo.png" alt="Forged with Foundry" width="223">
</p>

# PRI-PRE-002 — Lawful basis or purpose missing

> **Status:** Validated
>
> **Last reviewed:** 2026-09-04

## Overview

A team is preparing an AI system that processes personal data, but cannot show
the declared lawful basis and documented purpose. The gap should be visible to
the privacy team before go-live, without pretending that a tag alone proves
legal compliance.

This bite-sized demo uses an **Azure Policy `audit` assignment**. It deploys one
disabled Azure Action Group with deliberately incomplete metadata, shows the
non-compliant policy result, and then remediates the same resource so it becomes
compliant. The Action Group has no receivers and sends no notifications.

> **Azure Policy detects. The privacy team remediates. Nothing is blocked.**

## Demo profile

| Property | Value |
|---|---|
| **Demo format** | `DEPLOYABLE_DEMO` |
| **Learning level** | Foundation |
| **Estimated time** | 20–30 minutes; Azure Policy evaluation is asynchronous |
| **Primary decision** | Compliant or non-compliant for the demonstrated personal-data go-live request |
| **Primary capability** | Azure Policy with the `audit` effect and compliance state |
| **Deployment** | Required for the core learning outcome |
| **Infrastructure** | One custom policy definition, one assignment, and one temporary disabled Action Group |
| **AGT / ACS / Foundry** | Not used: this is an Azure configuration assessment, not an agent-runtime decision |

## Demo scope

### Core demo

The core demo uses one resource as the single source of truth:

1. Deploy it with `goLiveRequested=true` and
   `personalDataProcessing=true`, but without a valid `lawfulBasis` or
   non-empty `purposeId`.
2. Trigger Azure Policy evaluation and observe `NonCompliant`.
3. Add `lawfulBasis=contract` and `purposeId=PURPOSE-DEMO-001`.
4. Trigger evaluation again and observe `Compliant`.

### Intentional simplifications

- Tags replace an authoritative record of processing activities.
- The six GDPR Article 6(1) categories are used as a small illustrative enum,
  not as legal advice or a complete organizational decision method.
- Azure Policy checks whether declarations are present and recognized; it
  cannot establish whether they are truthful or legally appropriate.
- The Action Group is only a safe, taggable demonstration target. It is not an
  AI workload and remains disabled with no receivers.

### What this demo proves

- Azure Policy can detect the demonstrated missing or invalid metadata without
  custom decision code.
- `audit` records non-compliance but does not block deployment or remediation.
- The compliant and non-compliant outcomes come from the same Azure resource
  and policy rule, not from disconnected application data.

### What this demo does not prove

It does not prove GDPR compliance, determine the correct lawful basis, validate
the purpose description, or guarantee that every deployment supplies the
trigger tags. Production use requires a trusted inventory or release process
and an authoritative privacy workflow.

## Control contract

| Field | Value |
|---|---|
| **ID** | PRI-PRE-002 |
| **Lifecycle phase** | Pre-Live |
| **Category / domain** | Privacy |
| **Signal** | A personal-data go-live request lacks a recognized lawful basis or purpose reference |
| **Decision** | Azure Policy compliant or non-compliant |
| **Governance action** | Flag for design remediation; do not block |
| **Accountable role** | Privacy Officer |
| **Evidence** | Azure Policy compliance state, policy/resource identifiers, and evaluation timestamp |

## Control objective

Make the demonstrated missing lawful-basis or purpose metadata visible as an
Azure Policy compliance result without blocking the resource. Azure Policy is
the deterministic evaluator; choosing the real lawful basis remains a human
privacy decision outside the demo.

## Logical design

```mermaid
flowchart LR
  R[One tagged demo resource] --> P{Azure Policy audit rule}
  P -->|Basis or purpose missing| N[NonCompliant]
  N --> M[Add valid metadata]
  M --> P
  P -->|Both present| C[Compliant]
  N --> E[Policy state is evidence]
  C --> E

  classDef governance fill:#6E56CF,stroke:#A855F7,color:#FFFFFF
  classDef platform fill:#3B82F6,stroke:#00D4FF,color:#FFFFFF
  classDef evidence fill:#00D4FF,stroke:#3B82F6,color:#0D1117
  classDef intelligence fill:#A855F7,stroke:#6E56CF,color:#FFFFFF
  classDef neutral fill:#1F2937,stroke:#6E56CF,color:#FFFFFF
  classDef success fill:#22C55E,stroke:#22C55E,color:#0D1117
  classDef attention fill:#F59E0B,stroke:#F59E0B,color:#0D1117
  class R,M platform
  class P governance
  class N attention
  class C success
  class E evidence
```

The policy is evaluated only for a demonstrated go-live request that explicitly
declares personal-data processing. It treats a missing, empty, or unrecognized
`lawfulBasis` and a missing or empty `purposeId` as non-compliant.

## Infrastructure architecture

```mermaid
flowchart LR
  U[Community user] --> C[Azure CLI]
  C --> T[Disabled Action Group]
  P[Subscription policy definition] --> A[Resource-group assignment]
  A --> T
  T --> S[Azure Policy state]
  S --> C

  classDef governance fill:#6E56CF,stroke:#A855F7,color:#FFFFFF
  classDef platform fill:#3B82F6,stroke:#00D4FF,color:#FFFFFF
  classDef evidence fill:#00D4FF,stroke:#3B82F6,color:#0D1117
  classDef neutral fill:#1F2937,stroke:#6E56CF,color:#FFFFFF
  class U neutral
  class C,T platform
  class P,A governance
  class S evidence
```

## Implementation

| Component | Responsibility | Location |
|---|---|---|
| Azure Policy definition | Expresses the authoritative `audit` rule | [infra/policy-definition.bicep](infra/policy-definition.bicep) |
| Policy assignment | Limits the policy to one resource group | [infra/main.bicep](infra/main.bicep) |
| Demo target | Provides incomplete and remediated tags on one resource | [infra/demo-target.bicep](infra/demo-target.bicep) |
| Demo runner | Creates, inspects, remediates, and removes the target | [demo.sh](demo.sh) |

### Decision rules

- The rule applies only when `goLiveRequested=true` and
  `personalDataProcessing=true`.
- It audits a missing, empty, or unrecognized `lawfulBasis`.
- It audits a missing or empty `purposeId`.
- A compliant result requires a recognized basis and non-empty purpose
  reference on the same resource.

### Best-practice choices

The demo uses Azure Policy directly, keeps one source of truth, scopes its
assignment, authenticates through Azure CLI, uses only synthetic tags, disables
the Action Group, configures no receivers, and supplies exact cleanup.

## Demo

### Prerequisites

- Azure CLI authenticated with `az login`.
- An existing Azure resource group in which you may deploy the temporary Action
  Group and create a policy assignment.
- Permission to create a custom policy definition at subscription scope, such
  as **Resource Policy Contributor**.

### Configure

From the repository root:

```bash
cp controls/privacy/PRI-PRE-002_lawful_basis_or_purpose_missing/.env.example \
  controls/privacy/PRI-PRE-002_lawful_basis_or_purpose_missing/.env
```

Set `AZURE_SUBSCRIPTION_ID` and `AZURE_RESOURCE_GROUP` in the copied file. If
they already exist in `infra/.env`, the control reuses those values.

### Deploy the policy

```bash
./controls/privacy/PRI-PRE-002_lawful_basis_or_purpose_missing/infra/deploy.sh
```

### Run the non-compliant scenario

```bash
./controls/privacy/PRI-PRE-002_lawful_basis_or_purpose_missing/demo.sh start
```

The resource deployment succeeds because `audit` never blocks. The script
triggers an Azure Policy scan. Evaluation can take several minutes; check until
a state is available:

```bash
./controls/privacy/PRI-PRE-002_lawful_basis_or_purpose_missing/demo.sh status
```

Expected state: `NonCompliant`.

### Remediate the same resource

```bash
./controls/privacy/PRI-PRE-002_lawful_basis_or_purpose_missing/demo.sh remediate
./controls/privacy/PRI-PRE-002_lawful_basis_or_purpose_missing/demo.sh status
```

After Azure reevaluates the resource, the expected state is `Compliant`. The
`status` output is the real Azure Policy evidence and can be saved directly:

```bash
./controls/privacy/PRI-PRE-002_lawful_basis_or_purpose_missing/demo.sh status > evidence.json
```

### Inspect in Azure

| What to inspect | Azure Portal path | What to verify |
|---|---|---|
| Policy definition | **Policy** → **Definitions** → `pri-pre-002-lawful-basis-gate` | The effect is `audit`; missing, empty, or unknown metadata is included in the rule. |
| Policy assignment | **Policy** → **Assignments** → select the resource group | The definition is assigned only to the selected demo resource group. |
| Demo target | Resource group → `pripre002-demo` → **Tags** | It starts without valid basis/purpose metadata and is later updated in place. The Action Group is disabled and has no receivers. |
| Compliance evidence | **Policy** → **Compliance** → select the assignment | The same resource changes from `NonCompliant` to `Compliant` after remediation and reevaluation. |

### Expected scenarios

| Scenario | Input | Expected decision | Expected evidence |
|---|---|---|---|
| Missing declarations | Empty basis and purpose tags | `NonCompliant` | Azure Policy state and audit event |
| Remediated declarations | Recognized basis and non-empty purpose id | `Compliant` | Azure Policy state for the same resource |
| Evaluation pending | Azure has not published policy state | Wait; do not infer success | Explicit `Pending` response |

## Evidence and observability

`demo.sh status` returns a compact projection of Azure Policy state containing:

- compliance state;
- policy definition and assignment identifiers;
- evaluated resource identifier and type;
- policy evaluation timestamp.

Those fields are the authoritative evidence for this demo. No model output,
personal data, lawful-basis rationale, or free-text purpose is collected.

## Security and privacy

- Azure CLI authentication uses the current Entra identity; credentials are not
  stored in the control.
- The temporary Action Group is disabled and has no receivers.
- Tags are synthetic and contain no person, project, legal rationale, or free
  text beyond opaque demo identifiers.
- The policy assignment is resource-group scoped; creating the custom
  definition still requires subscription-scope permission.
- Cleanup targets the named demo resource and the two control-owned policy
  objects only.

## Validation

Run the local, read-only checks:

```bash
./controls/privacy/PRI-PRE-002_lawful_basis_or_purpose_missing/validate.sh
```

This compiles all Bicep templates and checks the shell scripts. The deployed
behavior is validated by completing the non-compliant and remediated paths.

## Cleanup

Delete the temporary Action Group:

```bash
./controls/privacy/PRI-PRE-002_lawful_basis_or_purpose_missing/demo.sh cleanup
```

Then remove only this control's policy assignment and definition:

```bash
./controls/privacy/PRI-PRE-002_lawful_basis_or_purpose_missing/infra/cleanup.sh
```

Neither command deletes the resource group or shared infrastructure.

## Further exploration

- Connect the metadata to the organization's authoritative record of processing
  activities rather than treating Azure tags as the source of truth.
- Use Microsoft Agent Governance Toolkit approval workflows if a future agent
  initiates or records the lawful-basis approval action.
- Automate policy scans and evidence collection in CI/CD or a governance
  reporting workflow.
- Group this rule with related pre-live controls in an Azure Policy initiative.

## References

- [Azure Policy `audit` effect](https://learn.microsoft.com/en-us/azure/governance/policy/concepts/effect-audit)
- [Get Azure Policy compliance data](https://learn.microsoft.com/en-us/azure/governance/policy/how-to/get-compliance-data)
- [Microsoft Agent Governance Toolkit approval workflows](https://github.com/microsoft/agent-governance-toolkit/blob/main/docs/tutorials/38-approval-workflows.md)
- GDPR Article 6(1) and Article 5(1)(b); the demo is illustrative and is not
  legal advice.

---

<p align="center">
  <img src="../../../media/themepack/fwf-footer.png" alt="Forged with Foundry" width="814">
</p>
