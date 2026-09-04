# DAT-PRE-002 Data Classification Agent

This guided demo shows how a Data Owner can respond to a file with unknown
sensitivity, without giving the model classification authority — every
decision is read from and verified against real Microsoft Purview
Information Protection state.

## What happens

1. Create three synthetic files in a dedicated OneDrive demo folder — one
   confidential-marked file with no label, one public-marked file
   pre-classified as a compliant baseline, and one simulated
   extraction-failure file.
2. Read each file's real sensitivity-label state through Microsoft Graph
   (`extractSensitivityLabels`) — never asserted locally.
3. Let the Foundry agent explain the safe, metadata-only result (optional).
4. Classify a flagged file with a guarded, real, asynchronous
   `assignSensitivityLabel` call, then re-verify Microsoft Graph confirms
   the label was actually applied.

> **The control decides from real platform state. The agent explains. The guarded tool classifies.**
