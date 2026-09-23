---
title: Pre-Live Azure Policy gate consolidation
description: Proposal to remove near-duplicate Azure Policy demo scaffolding across Pre-Live controls without weakening the schema or Rego enforcement layers, or the bite-sized-per-control README philosophy.
ms.date: 2026-09-22
---

## Status

**Proposal, not yet adopted.** Nothing in this document has been implemented.
It records an investigation and a recommended design for review before any
code changes. Written in response to a direct question about repository
structure, not a request to build it yet.

**Explicitly out of scope for this proposal:**

- Changing anything about the schema layer or the Rego policy-pass layer —
  see [What already works and should not change](#what-already-works-and-should-not-change).
- Consolidating the Azure Policy demo layer itself, described below — that
  is the actual subject of this proposal and remains unimplemented.

**Update, 2026-09-22, same day:** the schema-layer gap described in the
original [Two generations, not one](#two-generations-not-one) finding was
closed the same day it was written up, at the user's explicit request —
`PRI-PRE-001`, `PRI-PRE-002`, and `PRI-PRE-003` now each have a schema under
`schemas/governance-contract/v1alpha1/controls/`, fixtures under their own
`fixtures/` folders, boundary-case tests at `tests/test_pri_pre_00*_governance_contract.py`,
and their own `validate.sh` extended to exercise the shared validator. Their
pre-existing Azure Policy demo (the actual subject of this proposal) was
deliberately **not** touched — it keeps working exactly as before, since it
evaluates deployment-request tags directly and never reads a
`governance.yaml` file. See the section below for what this did and did not
change.

## Why this exists

Every Pre-Live control ("is required declaration X present and valid before
go-live? If not, block or escalate") follows the same shape. With 5
implemented today and roughly 35 more planned across every category
(`docs/roadmap.md`), the cost of any duplicated boilerplate in that shape
multiplies for as long as this repository is actively adding controls.

## What already works and should not change

Reading `docs/governance-contract.md` and the actual implementations, two of
the architecture's three enforcement layers are **already properly shared**:

1. **Schema-valid** — `scripts/validate_governance_contract.py` is fully
   generic; it validates any control's schema under
   `schemas/governance-contract/v1alpha1/controls/`. Adding a new control
   here means adding one small JSON Schema file, not new validator code.
2. **Policy-pass** — `policy/governance-contract/` (Conftest/Rego) plus
   `scripts/build_deployment_plan.py` and `scripts/deployment_gate.sh` are
   also fully generic and data-driven: which controls are required for which
   agents lives in a deployment profile
   (`examples/deployment-manifests/*.yaml`), not in per-control code.

Neither layer needs consolidation. They are the two layers this document
protects, not the ones it changes.

## The actual duplication: layer three

The third layer — Azure Policy's `deny` effect over a small set of
deployment tags, which `docs/governance-contract.md` itself documents as
"the weakest of the three guarantees and never a substitute for the other
two" — is where the real, measurable duplication lives, confirmed by diffing
the implemented controls directly:

- `infra/deploy.sh` (74 lines) is identical between PRI-PRE-002 and
  PRI-PRE-003 except for control-ID string substitution
  (`PRIPRE002_*` → `PRIPRE003_*`) and two log strings.
- `infra/main.bicep` (23 lines), `infra/cleanup.sh`,
  `infra/policy-definition.bicep`, and `infra/demo-target.bicep` follow the
  same pattern: same structure, different control-ID strings.
- This is exactly the shape every future structural-presence Pre-Live
  control will keep re-copying, because the underlying mechanism (assign a
  `deny` policy keyed on one tag, provide a demo resource to validate
  against, provide deploy/cleanup scripts) is genuinely identical every
  time — only the control ID, the tag name, and the "complete" value differ.

This is a good consolidation candidate specifically *because* it is the
weakest, most illustrative layer: simplifying it cannot silently weaken the
two layers that actually carry enforcement weight.

## Two generations, not one (resolved for the schema layer, 2026-09-22)

Diffing across categories originally surfaced a second, separate fact:
`PRI-PRE-001/002/003` did not use the governance-contract architecture at
all. There was no `.fwf/agents/.../governance.yaml`, and no schema for them
under `schemas/governance-contract/v1alpha1/controls/` (only `VAL-PRE-001`
and `VAL-PRE-002` existed there). They predated
`.github/instructions/fwf-governance-contract.instructions.md`'s current
"every new control gate integrates into the FwF governance contract
architecture" rule and used a standalone tag + Bicep pattern instead, with
no schema-valid layer of any kind.

**This is now fixed for the schema layer**, additively: each of the three
now has its own `schemas/governance-contract/v1alpha1/controls/PRI-PRE-00*.schema.json`,
complete/incomplete fixtures under a new shared fictional agent
(`customer-support-agent`, reusing the identity already established in
`examples/workload-repositories/customer-service-agent/`), and boundary-case
tests. Their pre-existing Azure Policy demo layer — the tag-based
`infra/policy-definition.bicep`/`deploy.sh`/`cleanup.sh`/`demo-target.bicep`
quintet this proposal is actually about — was deliberately left unchanged:
it is independent of `governance.yaml` (it evaluates deployment-request
tags directly, per `docs/governance-contract.md`'s own description of the
Azure Policy layer), so adding the schema layer alongside it carried no
regression risk to already-captured evidence or screenshots.

Practical consequence for this proposal: the shared module below is
designed against the schema-plus-fixture shape all five implemented
Pre-Live controls now consistently have. `PRI-PRE-001/002/003`'s own Azure
Policy demo infrastructure is still the older, hand-copied pattern this
proposal wants to consolidate — closing the schema-layer gap did not change
that, and prototyping the shared module against one of these three (instead
of only a brand-new control) is now also a viable option, since they are no
longer architecturally inconsistent with the rest of the Pre-Live family.

## Proposed design

A new shared module, tentatively `infra/pre-live-policy-gate/`, holding the
generic Bicep templates and one parameterized shell script, replacing what
is today copied wholesale into each control's own `infra/` folder.

**Module interface (illustrative, to be finalized during prototyping):**

```bicep
// infra/pre-live-policy-gate/policy-definition.bicep
param controlId string            // e.g. 'VAL-PRE-003'
param tagName string              // e.g. 'benefitAttributionStatus'
param completeValue string = 'complete'
param demoResourceType string = 'Microsoft.Insights/actionGroups'
```

```bash
# from any control's own directory
../../../scripts/pre_live_gate.sh deploy \
  --control-id VAL-PRE-003 --tag-name benefitAttributionStatus
../../../scripts/pre_live_gate.sh demo --control-id VAL-PRE-003
../../../scripts/pre_live_gate.sh cleanup --control-id VAL-PRE-003
```

**What a control's own directory keeps** (never templated away — this is
the actual lesson, not boilerplate):

- `README.md` / `ASSESSMENT.md` — the real-life scenario, the specific field
  being checked, the specific governance action, screenshots of *this*
  control's own denial/allow outcome.
- Its own schema fragment
  (`schemas/governance-contract/v1alpha1/controls/<ID>.schema.json`) and its
  two fixtures (complete/incomplete `governance.yaml`) — small, and
  genuinely control-specific: this *is* the definition of what "satisfied"
  looks like for this one requirement.

**What a control's own directory drops**: the ~7 near-duplicate
`infra/*.bicep` and `*.sh` files, replaced by a short parameters block (a
handful of lines) invoking the shared module.

**README impact**: every future Pre-Live control's "Implementation path"
section collapses from a full hand-written Azure Policy walkthrough to a
couple of lines pointing at the shared module's own docs for the generic
mechanics — the same pattern VAL-002 just used by linking to VAL-001 instead
of repeating its setup steps. This directly serves the "keep it digestible"
goal: less boilerplate to read in every single control README, not just less
to write.

**Isolation is preserved**: a learner can still clone the repository, `cd`
into one control's directory, and run its own `deploy`/`demo`/`cleanup`
commands without needing to understand the shared module's internals first
— the module is invoked by reference with a couple of parameters, not
something the reader has to open to run the demo.

## Rollout plan

1. **Do not touch already-implemented controls yet.** VAL-PRE-001/002's
   existing infra stays as-is; this avoids regression risk on already
   captured, published evidence.
2. **Prototype the shared module against one real upcoming Pre-Live
   control** (not a throwaway example) — the next genuine candidate, so the
   module's interface is validated against a real requirement, not an
   imagined one.
3. **Only after the prototype works end-to-end** (deploy, demo both allow
   and deny paths, cleanup, tests) decide whether to backport it to
   VAL-PRE-001/002. Backporting is optional, not assumed.
4. Update this document's Status to reflect the outcome once a prototype
   exists — from Proposal to either Adopted (with the finalized module
   interface) or Rejected/Revised (with why).

## Open questions to resolve during prototyping

- Exact module location and name (`infra/pre-live-policy-gate/` vs. a
  `scripts/`-only approach with inline Bicep strings vs. something else).
- Whether the shared script should also generate the control's schema
  boilerplate (likely no — schema content is genuinely per-control and
  small; templating it risks the same "shared abstraction nobody fully
  understands" problem this proposal is trying to avoid on the infra side).
- How the shared module's own tests prove ownership-scoped cleanup for
  *every* control that uses it, not just the one it was prototyped against
  (mirroring `infra/cleanup.py`'s validate-before-delete pattern already
  used elsewhere in this repository).

## References

- [`docs/governance-contract.md`](governance-contract.md) — the three
  enforcement layers this proposal only partially touches.
- `controls/privacy/PRI-PRE-002_lawful_basis_or_purpose_missing/infra/` and
  `controls/privacy/PRI-PRE-003_retention_design_missing/infra/` — the
  concrete duplication evidence this proposal is based on.
- `controls/value_adoption_and_finops/ARCHITECTURE.md` — the existing
  precedent for a living, category-scoped design note this document follows
  the style of, at repository scope instead of category scope.
