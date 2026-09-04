# PRI-PRE-002 Lawful Basis Gate Agent

This guided demo shows how a project can process personal data without a
documented GDPR Article 6(1) lawful basis or purpose, and a safe response
that uses a **real Azure Policy `audit` assignment** to flag the gap for
remediation — not custom application code.

## What happens

1. Create four synthetic AI-system/project records covering every outcome.
2. Scan the register with a deterministic lawful-basis and purpose check.
3. Let the Foundry agent explain the safe metadata-only result.

Unlike PRI-PRE-001's `deny` gate, `audit` never blocks a deployment — it
flags a non-compliant resource in Azure's own compliance report. This
demo's README documents a real, manual walkthrough of that flag; it isn't
shown live in this chat because Azure's compliance evaluation runs on its
own asynchronous schedule.

> **The control decides. The agent explains. Azure Policy is the real backstop — as a flag, not a block.**
