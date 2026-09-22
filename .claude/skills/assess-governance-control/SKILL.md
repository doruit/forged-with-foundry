---
name: assess-governance-control
description: "Assess a proposed Forged with Foundry governance control before any implementation: classify it (DEMONSTRATE/COMPOSE/ADAPT/IMPLEMENT_GAP/REJECT_DUPLICATE), pick the smallest demo format, and produce a completed ASSESSMENT.md. Use before writing any code or infrastructure for a new or not-yet-implemented control."
license: MIT
user-invocable: true
metadata:
  authors: "Douwe van de Ruit"
  mirrors: ".github/prompts/assess-governance-control.prompt.md"
  spec_version: "1.0"
---

# Assess governance control

Mirrors the GitHub Copilot prompt file at
`.github/prompts/assess-governance-control.prompt.md` so the same
assessment-first workflow runs identically under Claude Code. Keep the two in
sync if either changes; this file should never contradict the original.

## When to use

Before implementing any control whose status in `docs/roadmap.md` is
`Planned` (skeleton README only, no `ASSESSMENT.md`), or whenever the user
asks to assess, scope, or scaffold a new control.

## Instructions

Assess the proposed governance control using
[`.github/copilot-instructions.md`](../../../.github/copilot-instructions.md)
and
[`docs/control-assessment-template.md`](../../../docs/control-assessment-template.md).

Do not implement code or infrastructure during this task.

First inspect:

1. related controls already present in this repository — including the
   category's own `ARCHITECTURE.md` (for example
   `controls/value_adoption_and_finops/ARCHITECTURE.md`), which records
   shared data streams and known duplication risks other controls in the same
   category must reconcile with;
2. relevant Microsoft Agent Governance Toolkit (AGT) capabilities and
   examples;
3. relevant Agent Control Specification (ACS) intervention points and
   semantics;
4. Microsoft Foundry and Azure services that already provide part or all of
   the capability;
5. current official Microsoft samples covering the same scenario.

Determine whether the proposal is `DEMONSTRATE`, `COMPOSE`, `ADAPT`,
`IMPLEMENT_GAP`, or `REJECT_DUPLICATE`.

Recommend the smallest isolated demo that adds a genuine learning outcome.
Select `GUIDED_EXERCISE`, `HYBRID_DEMO`, or `DEPLOYABLE_DEMO`, and state
whether deployment is not applicable, optional, or required for the core
learning outcome. Identify exactly which supported capabilities should form
the core demo, the role each one performs, and how a learner can observe that
role. Explain why any apparently relevant capability is not selected. Identify
what, if anything, still requires custom code or infrastructure. An official
capability or sample can be the center of a `DEMONSTRATE` demo; reject it only
when no distinct governance scenario, composition, evidence pattern, or
learning outcome remains. Never add technology merely to make an
administrative control appear technical.

Also state the control's **Model/Foundry role** per
`.github/instructions/governance-controls.instructions.md`: `Active — governed
subject`, `Monitored workload`, `Explanatory only`, or `Not used — not
applicable to the core path`, with justification.

Produce the completed `ASSESSMENT.md` in the proposed control directory
(copy `docs/control-assessment-template.md` there first if it doesn't exist)
and stop before implementation.
