<p align="center">
  <img src="../../../media/themepack/fwf-badge-small-only-logo.png" alt="Forged with Foundry" width="223">
</p>

# VAL-PRE-001 — Value hypothesis missing

> **Status:** Validated
>
> **Last reviewed:** 2026-09-18

## Overview

A team launches an AI agent, but nobody can say what business outcome it is
supposed to move, or by how much. Months later nobody can answer "is this
thing working?" because there was never a target to compare against. Agent
ideas without a value hypothesis stay in dev.

This control requires a `value_hypothesis` block in the agent's
`agent.yaml` (metric, numeric target + direction, baseline, owner, business
case id) and enforces it across three responsibilities: GitHub Actions
checks it is structurally *complete*, OIDC/Entra governs which trusted
repository/environment context may obtain the deployment identity, and Azure
Policy checks the required tags are *present* at the platform boundary.
**Validate the intent. Protect the identity. Enforce the platform.**

```yaml
value_hypothesis:
  metric: tier1_ticket_deflection_rate
  target: { value: 35, direction: increase }
  baseline: { status: net_new }
  owner: it-service-desk-manager@contoso.example
  business_case_id: BIZ-CASE-HELPDESK-001
```

> **Governance before enforcement.** The value hypothesis should be agreed
> before the technical gate runs. An organisation should have an upstream
> intake or approval process where the business or workload team states the
> expected value, metric, target, and accountable owner — and where that
> hypothesis is reviewed and challenged before go-live. This demo assumes
> that process has happened and `agent.yaml` records the agreed result; the
> control only enforces structural completeness and the governed deployment
> path.

## Demo profile

| Property | Value |
|---|---|
| **Demo format** | `DEPLOYABLE_DEMO` |
| **Learning level** | Foundation |
| **Estimated time** | 15–20 minutes, including policy propagation |
| **Primary decision** | Deny a tagged go-live request when it lacks a structurally complete value hypothesis |
| **Primary capabilities** | `agent.yaml`'s `value_hypothesis` block + validator; Azure Policy `deny` effect (deployed and validated); optional real GitHub Actions CI check + OIDC/Entra-authenticated CD deployment (see [Production hardening](#production-hardening)) |
| **Deployment** | Required for the core learning outcome |
| **Infrastructure** | One custom policy definition + one resource-group assignment; the optional extension adds one managed identity, one federated credential, one scoped role assignment |
| **AGT / ACS** | Not used: this is Azure resource admission, not an agent-runtime decision |
| **Model/Foundry role** | `Not used — not applicable to the core path` |

## Demo scope

### Core demo

Two validations against the same harmless Azure resource template, tagged as
an IT Helpdesk Tier-1 Triage Agent go-live request: `fixtures/agent.incomplete.yaml`
(missing `owner`/`business_case_id`) is denied; `fixtures/agent.yaml`
(structurally complete) validates. Both use `az deployment group validate`,
so no workload is created.

### Intentional simplifications

- Checks *structural* completeness only, not target realism, owner identity,
  or metric quality.
- One metric per hypothesis; tags stand in for a real intake system.
- The Live counterpart (the agent reporting measured values back) is a
  separate, not-yet-built telemetry stream — see [`../ARCHITECTURE.md`](../ARCHITECTURE.md).

### What this demo proves

- Azure Policy denies the demonstrated go-live request when the required
  tags are absent, and validates it once they are present.
- The optional CI check + CD deployment path has itself been run live,
  end to end, against a real GitHub repository and Azure subscription.
- No model or custom policy engine participates in either decision.

### What this demo does not prove

- That the hypothesis is a *good* one, or that the named owner agreed to be
  accountable.
- That the agent later achieves the target (VAL-001's job, from a separate
  Live telemetry source).
- **Azure Policy cannot distinguish genuine metadata from forged metadata.**
  A caller who supplies trusted-looking tags without ever running the
  validator gets the same platform decision as one who did; only the
  governed CD deployment identity narrows who can plausibly make that call.

## Control contract

| Field | Value |
|---|---|
| **ID** | VAL-PRE-001 |
| **Lifecycle phase** | Pre-Live |
| **Category / domain** | Value |
| **Control / signal** | Value hypothesis missing |
| **Evidence / source** | `agent.yaml`'s `value_hypothesis` block, reduced to two deployment tags |
| **Trigger / threshold** | No measurable business hypothesis |
| **Action / gate effect** | Block approval to proceed |
| **Accountable role** | Business Owner |

## Control objective

Deny the demonstrated go-live request when it lacks a structurally complete
value hypothesis. The decision is deterministic and belongs to Azure Policy.
Whether the hypothesis is a *good* one, and genuine Business Owner sign-off,
remain explicit upstream trust boundaries rather than hidden model decisions.

## Logical design

```mermaid
flowchart TB
  Y[agent.yaml value_hypothesis] --> CI{"GitHub Actions CI check<br/>CONTENT-AWARE: reads agent.yaml"}
  CI -->|incomplete| BLOCK[BLOCK: pipeline stops,<br/>no Azure call made]
  CI -->|complete| ENVIRONMENT[GitHub Environment]
  ENVIRONMENT --> OIDC["OIDC / Entra identity<br/>GOVERNED DEPLOYMENT IDENTITY"]
  OIDC --> REQ[Azure deployment request<br/>carries two reduced tags only]
  REQ --> POLICY{"Azure Policy<br/>PRESENCE-ONLY: never reads agent.yaml"}
  POLICY -->|tag missing or invalid| DENY[DENY: RequestDisallowedByPolicy]
  POLICY -->|tags present| DEPLOY[DEPLOY]

  classDef governance fill:#6E56CF,stroke:#A855F7,color:#FFFFFF
  classDef platform fill:#3B82F6,stroke:#00D4FF,color:#FFFFFF
  classDef success fill:#22C55E,stroke:#22C55E,color:#0D1117
  classDef attention fill:#F59E0B,stroke:#F59E0B,color:#0D1117
  classDef neutral fill:#1F2937,stroke:#6E56CF,color:#FFFFFF
  class Y neutral
  class CI,POLICY governance
  class ENVIRONMENT,OIDC,REQ platform
  class BLOCK,DENY attention
  class DEPLOY success
```

Three distinct responsibilities, never merged: GitHub Actions validates the
*intent* (does `agent.yaml` structurally declare a measurable hypothesis?);
OIDC/Entra protects the *identity* (may this trusted repository/environment
context obtain the deployment identity?); Azure Policy enforces the
*platform* (are the two required tags present on the request?). Azure
Policy never reads `agent.yaml` and cannot prove the CI check ran — see
What this demo does not prove, above.

## Infrastructure architecture

The diagram above already shows every building block this control uses; this
section names the two pieces that run at different times. Bicep provisions
the policy definition and resource-group assignment once, ahead of any demo
run (`infra/deploy.sh`); the Azure CLI then calls `az deployment group
validate` (core demo) or `az deployment group create` (optional CD path) on
every run afterward, against whichever policy state Bicep left in place.
Azure Resource Manager is the only authoritative decision point in both
paths.

## Implementation

### Components

| Component | Responsibility | Location |
|---|---|---|
| `agent.yaml` fixtures | Structured value hypothesis, one complete and one incomplete | [fixtures/](fixtures/) |
| Structural validator | Reduces `agent.yaml` to the two tags Azure Policy checks | [scripts/validate_value_hypothesis.py](scripts/validate_value_hypothesis.py) |
| Azure Policy definition + assignment | Expresses and scopes the authoritative `deny` rule | [infra/policy-definition.bicep](infra/policy-definition.bicep), [infra/main.bicep](infra/main.bicep) |
| Demo runner | Runs the assessment then both validations, printing evidence | [demo.sh](demo.sh) |
| OIDC identity (optional) | Managed identity + federated credential for the real CD extension | [infra/oidc-identity.bicep](infra/oidc-identity.bicep) |
| Real CI check + CD deploy (optional) | Runs both stages for real via GitHub OIDC | [.github/workflows/val-pre-001-value-gate-demo.yml](../../../.github/workflows/val-pre-001-value-gate-demo.yml) |

Full component table, decision rules, and best-practice rationale:
[docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md).

### Decision rules

The validator marks a hypothesis `complete` only when `metric`,
`target.value` (numeric), `target.direction` (`increase`/`decrease`),
`baseline.status` (`measured`/`net_new`), `owner`, and `business_case_id`
are all present and non-blank; otherwise `incomplete`. Azure Policy denies
whenever `valueHypothesisStatus != complete` or `businessCaseId` is empty,
reading only those two tags. Full rules and edge cases:
[docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md#decision-rules).

### Production hardening

The optional real path (real CI check job + OIDC-authenticated CD deployment
job, `needs:`-dependent so the CD job never runs if the CI check fails) is
verified live end to end, including a deliberate bypass scenario proving
Azure Policy alone still denies a request that skipped the CI check. Setup,
screenshots, the identity trust diagram, the current GitHub OIDC subject
format, and GitHub Environment protection-rule hardening (required
reviewers, branch restrictions) that this demo intentionally leaves as
manual, documented steps: [docs/OIDC-DEMO.md](docs/OIDC-DEMO.md).

## Demo

### Prerequisites

- Azure CLI authenticated (`az login`); Python 3 with `pip install -r requirements.txt`.
- An Azure resource group, with permission to validate a deployment and
  create a policy assignment (subscription-scope for the definition, e.g.
  **Resource Policy Contributor**).

### Deploy

```bash
cp controls/value_adoption_and_finops/VAL-PRE-001_value_hypothesis_missing/.env.example \
  controls/value_adoption_and_finops/VAL-PRE-001_value_hypothesis_missing/.env
# set AZURE_SUBSCRIPTION_ID and AZURE_RESOURCE_GROUP in the copied file
./controls/value_adoption_and_finops/VAL-PRE-001_value_hypothesis_missing/infra/deploy.sh
```

Azure Policy assignments can take several minutes to propagate.

### Inspect in Azure

| What to inspect | Azure Portal path | What to verify |
|---|---|---|
| Policy definition | **Policy** → **Definitions** → `val-pre-001-value-hypothesis-gate` | Effect is `deny`; requires `valueHypothesisStatus=complete` and a non-empty `businessCaseId`. |
| Policy assignment | **Policy** → **Assignments** → resource group | Scoped only to the chosen demo resource group. |

### Run

```bash
./controls/value_adoption_and_finops/VAL-PRE-001_value_hypothesis_missing/demo.sh
```

### Demo walkthrough

Captured terminal output from actually running the command above against the
live deployed policy:

```text
1/2 Assessing an agent.yaml with an incomplete value hypothesis...
Validating a go-live request with valueHypothesisStatus=incomplete...
BLOCKED as expected by Azure Policy.
2/2 Assessing an agent.yaml with a complete, measurable value hypothesis...
Validating the same request with valueHypothesisStatus=complete...
VALIDATED as expected by Azure Policy.
{
  "control_id": "VAL-PRE-001",
  "policy_version": "2.0.0",
  "incomplete_hypothesis_result": "denied",
  "complete_hypothesis_result": "validated",
  "resource_created": false,
  "action": "block go-live until a measurable value hypothesis is present",
  "accountable_role": "Business Owner"
}
```

### Expected scenarios

| Input | Expected decision |
|---|---|
| `fixtures/agent.incomplete.yaml` | Deny (`RequestDisallowedByPolicy`) |
| `fixtures/agent.yaml` | Validate |

## Evidence and observability

The terminal record contains the control and policy version, both
authoritative Azure results, a UTC timestamp, the action, and accountable
role — no real business case, personal data, prompt, or model output. The
optional GitHub Actions extension produces the same class of evidence as a
real workflow run: three green job results, inspectable in the Actions tab.

## Security and privacy

- Azure CLI/OIDC authentication only; no credentials stored in the control.
- Only synthetic, non-personal tags are sent to Azure.
- The optional CD identity holds only **Monitoring Contributor** on the demo
  resource group, never `Contributor`. Detail: [docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md#best-practice-choices).

## Validation

### Automated tests

`validate.sh` compiles all Bicep templates, checks the shell scripts, and
runs `scripts/test_validate_value_hypothesis.py` (11 boundary cases:
blank/missing/non-numeric fields, invalid direction/baseline, `--enforce`
pass/fail) plus the validator against both fixtures.

```bash
./controls/value_adoption_and_finops/VAL-PRE-001_value_hypothesis_missing/validate.sh
```

### Known limitations

Target realism, multi-metric hypotheses, and `agent.yaml` revision history
are out of scope; the optional GitHub Environment has no deployment
protection rules configured by default. Full list:
[docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md#known-limitations-detail).

## Cleanup

```bash
./controls/value_adoption_and_finops/VAL-PRE-001_value_hypothesis_missing/infra/cleanup.sh
# if you ran the optional CI check + CD deploy demo:
./controls/value_adoption_and_finops/VAL-PRE-001_value_hypothesis_missing/infra/cleanup-oidc.sh
```

Neither script deletes the resource group or shared infrastructure.

## References

- [Deep dive: implementation detail](docs/IMPLEMENTATION.md)
- [Deep dive: real CI check + CD deployment demo (OIDC)](docs/OIDC-DEMO.md)
- [Glossary](../../../docs/glossary.md)
- [Azure Policy `deny` effect](https://learn.microsoft.com/en-us/azure/governance/policy/concepts/effect-deny)
- [Configure Microsoft Entra Workload ID federation for GitHub Actions](https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation-create-trust-github)
- [GitHub Actions: using environments for deployment](https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment)
- `controls/privacy/PRI-PRE-001_dpia_required_but_missing` — the reused
  enforcement pattern this control adapts.
- [../ARCHITECTURE.md](../ARCHITECTURE.md) — cross-control data flow.


---

<p align="center">
  <img src="../../../media/themepack/fwf-footer.png" alt="Forged with Foundry" width="814">
</p>
