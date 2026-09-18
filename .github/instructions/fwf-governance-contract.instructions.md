---
description: "Required checklist for integrating a newly implemented governance control into the Forged with Foundry Agent Governance Contract architecture."
applyTo: "controls/**/*, schemas/governance-contract/**"
---

Read [`docs/governance-contract.md`](../../docs/governance-contract.md)
first for the full explanation of this architecture; do not duplicate that
explanation here.

Whenever a new control gate is implemented (status becomes `Implemented` or
`Validated`), integrate it into the FwF governance contract architecture:

1. The control's existing catalog ID (for example `VAL-PRE-002`) remains
   the canonical identifier. Never invent a new ID.
2. Add exactly one control schema under the active contract API version:
   `schemas/governance-contract/v1alpha1/controls/<ID>.schema.json`. Never
   generate a schema for a skeleton-only or planned control.
3. That schema enforces the control's own exact ID using `"id": {"const":
   "<ID>"}`.
4. The central schema
   (`schemas/governance-contract/v1alpha1/fwf-governance-contract.schema.json`)
   references the new schema from `spec.controls.items.oneOf`.
5. Add or update complete and incomplete example contracts as fixtures at
   `.fwf/agents/<agent-id>/governance.yaml` (never `agent.yaml`,
   `fwf-governance-contract.yaml`, or any other filename).
6. Add positive (structurally complete) and fail-closed (structurally
   incomplete, malformed, or unknown-ID) tests exercising the shared
   `scripts/validate_governance_contract.py` and the new schema.
7. Document in the control's own README what the control's evidence proves
   and does not prove — never claim a passing schema validation proves a
   business outcome, only structural completeness.
8. Update the control's status/overview (its own README, category
   `ARCHITECTURE.md` if one exists, root `README.md` "Recently added," and
   regenerate `docs/roadmap.md` via `scripts/generate_roadmap.py` — never
   hand-edit it).
9. Never create a schema, fixture, or example for a control that is only a
   catalog skeleton or roadmap placeholder.
10. Never repurpose a real Microsoft or vendor `agent.yaml` (or any other
    real platform manifest) as an FwF governance contract. They are
    separate artifacts with separate owners; see the ownership table in
    `docs/governance-contract.md`.
11. Never claim Microsoft Foundry, the Microsoft Agent Framework, or `azd`
    tooling automatically discovers or enforces this contract. Enforcement
    comes only from the supplied validator and whatever pipeline calls it.
12. Every schema, fixture, documentation reference, and workflow step uses
    the exact existing control ID — no abbreviations, renames, or
    placeholders.
13. Reuse the appropriate mechanism for the requirement you are adding, and
    no other. A control's own evidence shape (fields, types, conditional
    requirements) always belongs in a JSON Schema per items 2-4 above. An
    organisational "which agents must declare this control" coverage rule
    belongs in the Conftest/Rego policy layer
    (`policy/governance-contract/`, see
    [`docs/governance-contract.md`](../../docs/governance-contract.md#policy-layer))
    instead, and only if a deployment profile should actually require the
    new control — do not add a Rego rule for every new control by default,
    and do not require every runtime control or guided exercise to acquire
    a YAML schema merely because it exists in the catalog.

Keep a new control's evidence self-contained: it must validate correctly
with no assumption that any other control's entry exists in the same
contract, so a workload can implement any subset of controls independently.

The repository's automated consistency check
(`tests/test_governance_contract_consistency.py`) verifies items 2-4 and
duplicate/unknown-ID fail-closed behavior mechanically — run
`.venv/bin/python -m pytest tests/test_governance_contract_consistency.py -q`
before considering a new control's contract integration complete.
