# Forged with Foundry Agent Governance Contract

This document explains the Forged with Foundry (FwF) Agent Governance
Contract: a small, repository-owned pattern for declaring which governance
controls apply to an agent and what evidence proves each one, written in
plain language for anyone new to this repository.

> **This is a Forged with Foundry community pattern, not an official
> Microsoft specification.** Microsoft Foundry, the Microsoft Agent
> Framework, and `azd` tooling do not discover or enforce this file.
> Enforcement happens only where this repository's own validators and
> CI/CD pipelines call it — never automatically, and never by Microsoft
> tooling.

## What it is

An agent's governance contract is one YAML file that says, in one place:
*which* Forged with Foundry governance controls this agent has implemented,
and *what evidence* proves each one is satisfied. It lives at a fixed,
predictable path inside a workload's own repository:

```
.fwf/agents/<agent-id>/governance.yaml
```

Every deployable agent gets its own `<agent-id>` subfolder. A repository
with three agents has three `.fwf/agents/<agent-id>/` folders, each with its
own `governance.yaml` declaring only the controls that actually apply to
*that* agent — not every control in the catalog.

A minimal example:

```yaml
apiVersion: forgedwithfoundry.dev/v1alpha1
kind: AgentGovernanceContract

metadata:
  agentId: helpdesk-tier1-triage
  description: Governance contract for the helpdesk triage agent
  source: https://github.com/doruit/forged-with-foundry
  license: MIT

spec:
  agentRef:
    definition: ./agent.yaml

  controls:
    - id: VAL-PRE-001
      version: "1.0.0"
      evidence:
        owner: it-service-desk-manager@contoso.example
        businessCaseId: BIZ-CASE-HELPDESK-001
        expectedOutcome: Reduce Tier-1 tickets that need a human agent
        metric:
          name: tier1_ticket_deflection_rate
          direction: increase
          target: 35
        baseline:
          status: net_new
```

See a fuller, believable example at
[`examples/workload-repositories/customer-service-agent/`](../examples/workload-repositories/customer-service-agent/README.md).

## `agent.yaml` versus `governance.yaml`

These are two different files with two different owners, and this
architecture exists specifically so they never get confused:

| Artifact | Purpose | Owner |
|---|---|---|
| Microsoft or vendor agent manifest (for example a real Microsoft Foundry hosted-agent `agent.yaml`) | Runtime, hosting, and deployment configuration | Platform/tooling |
| `.fwf/agents/<agent-id>/governance.yaml` | Governance requirements and control declarations | Workload and governance teams |
| Evidence files (for example a supporting measurement JSON) | Measurements, assessments, and approvals | Accountable control owners |

A real Microsoft Foundry hosted-agent manifest is schema-validated
(`$schema=.../AgentSchema/.../ContainerAgent.yaml`) and consumed by real
`azd ai agent` tooling and the Foundry Toolkit VS Code extension — it has
nothing to do with governance evidence, and this architecture never
repurposes that filename or shape for a different purpose. The FwF
governance contract **complements** whatever real agent manifest exists (if
any); it never replaces or re-validates it. `spec.agentRef.definition` is
just a pointer to that real manifest's path, for a human reader's
convenience — the FwF validator never opens or parses it.

## Where enforcement happens

Enforcement is whatever calls the validator, the policy layer, or Azure
Policy — never Microsoft tooling automatically. Three supported call sites
exist, each answering a different question and each complementary rather
than duplicative. A single word like "valid" is ambiguous across all three,
so this document (and every control README) uses three distinct terms:

* **schema-valid** — every declared control entry is structurally complete
  and well-formed (right fields, right types, right conditional
  requirements). Checked by
  `python scripts/validate_governance_contract.py --root . --enforce`. This
  says nothing about *which* controls an agent was supposed to declare.
* **policy-pass** — every agent a deployment profile expects actually has a
  schema-valid contract declaring every control that profile requires.
  Checked by the [Conftest/Rego policy layer](#policy-layer). A contract can
  be schema-valid on its own and still fail this check, for example if it is
  missing an entire required control or its folder never existed.
* **deployment-allowed** — Azure Policy's `deny` effect, evaluated at
  deployment time against a small set of tags derived from a contract's
  evidence, did not block the request. See
  [Azure Policy coexistence](#azure-policy-coexistence) for why this is the
  weakest of the three guarantees and never a substitute for the other two.

### A CI check (schema-valid)

`python scripts/validate_governance_contract.py --root . --enforce`
discovers every `.fwf/agents/*/governance.yaml` under a repository root and
fails the pipeline if any control's evidence is structurally incomplete.
This is fast, credential-free feedback, and the only layer that inspects a
contract's actual evidence content.

### Policy layer

This is the **policy-pass** call site. JSON Schema `contains`/`minContains`
could technically require one fixed contract document to declare a specific
control ID, but that would hardcode the required-control set into the
structural schema itself — forcing a schema change (and a new control or
`apiVersion` revision) every time an organisation's requirements change, and
giving every deployment profile the same fixed rule instead of letting it
vary per profile or environment (see `examples/deployment-manifests/`, where
`core-profile.yaml` requires two controls and `val-pre-001-only.yaml`
requires one). Rego was chosen instead so "which agents are expected, and
which controls are mandatory for them" is centrally managed **policy data**
that a deployment profile can change independently of contract schema
versioning, without touching `schemas/governance-contract/` at all. That
coverage decision lives in
[`policy/governance-contract/`](../policy/governance-contract/README.md),
expressed as [Conftest](https://www.conftest.dev/)/[OPA Rego](https://www.openpolicyagent.org/)
rules evaluated against a deployment plan document built by
`scripts/build_deployment_plan.py` — never against a workload's own
`governance.yaml` directly, and never trusting a workload to report its own
coverage. That builder step validates the deployment manifest itself before
any contract is discovered: a manifest with a missing, empty, wrong-typed,
duplicated, or unknown-control-ID `expectedAgents`/`requiredControls` is
rejected as an execution failure (exit code 2), never silently treated as an
empty list that the Rego rules would then evaluate as allowed. The Rego
policy also denies an empty or missing `expectedAgents`/`requiredControls`
directly, as defense in depth against a hand-built plan document that skipped
that validation. `scripts/deployment_gate.sh` runs this whole sequence
(validate the manifest, discover, schema-validate, evaluate policy, emit an
evidence artifact) as the single deployment enforcement boundary a trusted
pipeline is expected to call; see that script and the policy README for
exact usage. This layer denies a deployment when: an expected agent has no
discovered `.fwf/agents/` folder at all, the folder exists with no
`governance.yaml`, the contract exists but is not schema-valid, or the
contract is schema-valid but is missing (or has
an incomplete) required control.

### Azure Policy (deployment-allowed)

VAL-PRE-002's [executable deployment walkthrough](../controls/value_adoption_and_finops/VAL-PRE-002_kpi_baseline_missing/docs/DEPLOYMENT-DEMO.md)
offers CI-only, independent Azure Policy-only and combined routes. Its
credential-free candidate job runs `deployment_gate.sh` with the existing
`val-pre-002-only` profile; the OIDC release job depends on its success and
uses its output tag. Negative fixture tests and the deliberate Policy denial
experiment cannot authorize a release. Local workflow-step tests prove
failure propagation; current live OIDC execution remains unverified.

Azure Policy's `deny` effect evaluates only a small set of deployment tags
(for example `valueHypothesisStatus`/`businessCaseId` for VAL-PRE-001,
`kpiBaselineStatus` for VAL-PRE-002) reduced from a contract's evidence. It
never reads `governance.yaml` itself, cannot prove the CI check or the
policy layer actually ran, and cannot distinguish genuine tags from forged
ones — see each control's own README "What this demo does not prove"
section, and [Azure Policy coexistence](#azure-policy-coexistence) below.

## Azure Policy coexistence

VAL-PRE-001's and VAL-PRE-002's demo policies both trigger on
`tags['goLiveRequested']=='true'`, and both demos are designed to be
assignable to the same shared resource group. Without an explicit selector,
each policy would also evaluate — and could wrongly deny — a request that
only ever set the *other* control's required tag, because its own required
tag would simply be absent (not `complete`).

Both policy definitions add a `tags['control-id']` equality condition
scoped to their own control ID (`VAL-PRE-001` or `VAL-PRE-002`) so each
policy only ever evaluates requests explicitly tagged for its own control,
letting the two demos coexist safely in one resource group without either
policy assignment being weakened or removed. Like every other tag these
demos use, `control-id` is caller-supplied and illustrative: it can be
omitted or forged, and Azure Policy does not authenticate that a real
contract assessment produced it.
[`tests/test_azure_policy_coexistence.py`](../tests/test_azure_policy_coexistence.py)
is the regression check protecting this: it compiles both policy
definitions and asserts each still carries its own `control-id` selector
alongside the shared `goLiveRequested` trigger.



## Versioning: three distinct concepts, kept separate

- **Contract API version** (`apiVersion: forgedwithfoundry.dev/v1alpha1`):
  the shape of the envelope itself (`metadata`, `spec.agentRef`,
  `spec.controls`). Lives under `schemas/governance-contract/v1alpha1/`. A
  breaking change to the envelope gets a new version folder
  (`v1alpha2`/`v1beta1`/...) alongside it, never an in-place rewrite.
- **Control definition version** (`spec.controls[].version`, for example
  `"1.0.0"`): which iteration of one control's own evidence shape a
  contract entry follows. A control's schema can grow a new required field
  in a later version without touching the contract `apiVersion`.
- **FwF catalog control ID** (`spec.controls[].id`, for example
  `VAL-PRE-001`): the permanent, immutable identifier from this
  repository's control catalog. It never changes.

## How schemas relate to a contract instance

`schemas/governance-contract/v1alpha1/` defines **what controls are
available to declare** — one JSON Schema file per implemented control
(`controls/VAL-PRE-001.schema.json`, `controls/VAL-PRE-002.schema.json`,
...), referenced from the central `fwf-governance-contract.schema.json` via
`oneOf`. A schema is only added once a control is actually implemented;
skeleton or planned controls never get a placeholder schema.

An agent's own `governance.yaml` is **one instance** of that catalog — the
subset of available controls that actually apply to this one agent, with
this agent's own evidence filled in. A workload only lists the controls
relevant to it; nothing requires every agent to declare every implemented
control.

Each control's schema enforces its own exact ID with `const`, so:

- an unknown or misspelled control `id` fails every `oneOf` branch and is
  rejected — fails closed;
- two entries sharing the same `id` are rejected by the shared validator
  (a check JSON Schema cannot express reliably on its own);
- the directory name a contract was discovered under
  (`.fwf/agents/<agent-id>/`) must exactly equal `metadata.agentId`,
  enforced by the same validator.

## How to add a newly implemented control

See
[`.github/instructions/fwf-governance-contract.instructions.md`](../.github/instructions/fwf-governance-contract.instructions.md)
for the concise, enforceable checklist. In short: add a schema under the
active `v1alpha1` folder, enforce that control's own ID with `const`, wire
it into the central schema's `oneOf`, add complete and incomplete examples,
add positive and fail-closed tests, and document what the control's
evidence proves and does not prove — all under the control's existing,
unchanged FwF catalog ID.

## What this proves, and what it never claims

A passing schema validation proves that a control's declared evidence is
**structurally present and well-formed** — the right fields, the right
types, the right conditional requirements. It never proves that the
underlying business judgment is *good*: whether a value hypothesis is
strategically credible, whether a recorded baseline is accurate, or whether
an agent will actually create value. That adequacy judgment belongs to the
organisation's own governance intake and approval process, upstream of
every control built on this architecture. Each control's own README states
this explicitly in its "What this demo does not prove" section.

## Further exploration

These integrations are optional and not required to complete the core
architecture or any control built on it. They are listed here so a future
contributor does not assume this repository requires them:

- **Backstage software catalog** — an organisation could surface discovered
  `.fwf/agents/*/governance.yaml` contracts as Backstage catalog entities or
  a custom Backstage plugin for browsing coverage across many
  repositories. This architecture does not require Backstage, ship a
  Backstage plugin, or assume one exists.
- **OSCAL (Open Security Controls Assessment Language)** — a future control
  could export its evidence as an OSCAL assessment result for exchange with
  external GRC tooling. This architecture does not require every control to
  produce OSCAL output, and no control in this repository does today.

## Source and license

This document, the schemas, and the shared validator are part of the
[Forged with Foundry](https://github.com/doruit/forged-with-foundry)
repository, licensed under the [MIT License](../LICENSE).
