# PRI-002 Retention Operations Agent

This guided demo shows how an AI agent can help a Privacy Officer respond to an
Azure Blob retention exception without giving the model policy or deletion
authority.

## What happens

1. Create three synthetic records.
2. Scan Blob metadata without downloading content.
3. Let deterministic PRI-002 code classify each record.
4. Ask the Foundry agent to explain the safe metadata-only result.
5. Approve or decline the one destructive remediation.
6. Verify the outcome and emit privacy-safe evidence.

> **The control decides. The agent explains and orchestrates. The guarded tool remediates.**
