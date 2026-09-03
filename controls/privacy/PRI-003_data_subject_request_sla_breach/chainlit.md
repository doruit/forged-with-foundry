# PRI-003 DSR Operations Agent

This guided demo shows how an AI agent can help a DPO respond to a data
subject request (DSR) that is approaching or has passed its SLA deadline,
without giving the model SLA-decision or extension authority.

## What happens

1. Create five synthetic DSR records covering every outcome.
2. Scan the register with a deterministic SLA policy.
3. Let the Foundry agent explain the safe metadata-only result.
4. Escalate an at-risk or breached request to the DPO.
5. Optionally request and grant one guarded SLA extension.

> **The control decides. The agent explains and orchestrates. The guarded tool extends.**
