# PRI-PRE-001 DPIA Gate Agent

This guided demo shows how an AI-powered feature can go live without a
required Data Protection Impact Assessment (DPIA), and a safe response
that uses a **real Azure Policy `deny` assignment** as the actual
enforcement mechanism — not custom application code.

## What happens

1. Create four synthetic AI-system/project records covering every outcome.
2. Scan the register with a deterministic multi-factor risk score and a
   DPIA-evidence-completeness check.
3. Let the Foundry agent explain the safe metadata-only result.
4. Attempt go-live for a project. No real resource is ever created — the
   demo calls `az deployment group validate`, which genuinely triggers
   Azure Policy's real `deny` evaluation.

> **The control decides. The agent explains and orchestrates. Azure Policy is the actual backstop.**
