---
agent: "agent"
description: "Assess a governance control before implementation"
---

Assess the proposed governance control using
[the repository instructions](../copilot-instructions.md) and
[the assessment template](../../docs/control-assessment-template.md).

Do not implement code or infrastructure during this task.

First inspect:

1. related controls already present in this repository;
2. relevant Microsoft Agent Governance Toolkit capabilities and examples;
3. relevant Agent Control Specification intervention points and semantics;
4. Microsoft Foundry and Azure services that already provide part or all of the
   capability;
5. current official Microsoft samples covering the same scenario.

Determine whether the proposal is `REUSE_ONLY`, `COMPOSE`, `ADAPT`,
`IMPLEMENT_GAP`, or `REJECT_DUPLICATE`.

Recommend the smallest isolated demo that adds a genuine learning outcome.
Select `GUIDED_EXERCISE`, `HYBRID_DEMO`, or `DEPLOYABLE_DEMO`, and state whether
deployment is not applicable, optional, or required for the core learning
outcome. Identify exactly what should be reused and what, if anything, requires
custom code or infrastructure. Never add technology merely to make an
administrative control appear technical. Produce the completed `ASSESSMENT.md`
in the proposed control directory and stop before implementation.
