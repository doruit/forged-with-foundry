---
title: VAL-001 prerelease review
description: Findings on correctness, simplicity, evidence, cleanup, and community reproducibility for the current implementation.
ms.date: 2026-09-21
---

## Verdict

Not ready for community release. The primary hosted-workload-to-KPI-to-Teams
path is demonstrated, but the requested complete cleanup and reproducible
onboarding gates are not met. This is a prerelease assessment of the current
implementation, not the final approval requested after all work is complete.
Keep status Planned and do not add the control to the root implemented-demo table.

## Open findings

1. **High: complete synthetic-state cleanup is not demonstrated.**
   [The runner](../demo.py#L76) creates platform conversations but does not retain
   their identifiers. [Azure cleanup](../infra/cleanup.py#L114) deliberately
   excludes conversation history and Teams state. Nine session filesystems,
   the agent, and control-owned Monitor resources were removed and verified,
   but that is not proof of conversation/message deletion. Cleanup now also
   requires the recorded hosted-agent instance principal before deleting the
   agent. Retain precise
   handles and exercise supported deletion before claiming complete cleanup;
   never delete a shared project or whole chat as a workaround.
2. **High: a clean-checkout deployment has not been reproduced.**
   [The runbook](IMPLEMENTATION.md#deployment-configuration) records the corrected
   ordering, preview versions, and required environment values. Actual development
   required multiple repairs to authentication, platform environment variables,
   and publisher identity. A new operator must prove the final documented order
   works without the author's existing azd state before organizations rely on it.
3. **Medium: failed runner invocations lose useful diagnostics.**
   [Invocation output](../demo.py#L81) is captured, then a broad CLI handler reports
   a generic error. Earlier attempts stopped and later attempts succeeded, but
   the original failure was not conclusively diagnosed. Retain a minimized
   failure stage, exit code, and safe correlation, without raw SDK responses,
   URLs, tokens, or model text. Do not turn this into a general logging framework.
4. **Medium: the README is still too dense for the intended first read.**
   [The README](../README.md) combines two substantial diagrams, resource inventory,
   routing rationale, future reporting, commands, and capture instructions.
   Preserve the content but move setup detail and secondary architecture/routing
   explanations into the existing technical guide. The first page should make
   the risk, decision, demo, limitations, and next action clear in 60-90 seconds.
5. **Low: the optional observability query must remain descriptive.**
   [The walkthrough](OBSERVABILITY-AGENT.md#1-run-the-kpi-query) now surfaces
   invalid events rather than filtering them into a passing result. It must not
   become a second evaluator; the JSON evidence record remains authoritative.

## Corrected during validation

- Removed the process-lifetime single-tool-invocation limit; two tickets in one
  hosted session then executed successfully.
- Isolated the Entra-authenticated outcome exporter from automatic host telemetry
  and the conflicting platform connection-string variable.
- Assigned the publisher role to the actual agent instance, not the shared project.
- Corrected the Teams token audience's trailing slash; preserved the rejected
  attempt and verified the subsequent matching Teams posting receipt.
- Preserved notification attempts across `cannot_evaluate` measurement retries.
- Replaced the overly strong healthy-card claim for mixed periods.
- Rejected `unresolved` events even when malformed telemetry claims verification.
- Distinguished retained `deleted` session metadata from remaining filesystem state.
- Required the recorded hosted-agent instance identity before agent cleanup.
- Live-tested the separate `cannot_evaluate` route in the private chat with a
   matching correlation and a Teams `201` posting receipt.

## Evidence and assumptions

The repository test run passed 327 tests with 56 dependency deprecation warnings.
The Monitor template compiled. Local documentation links passed. Real runs
measured 20%/20% with `review_required`, 40%/40% with `no_review_required`, and
interrupted runs with `cannot_evaluate`. The matching Teams action returned
201 and a message identifier. Azure cleanup was independently verified.

The private Teams recipient is a synthetic Business Owner and AI Governance
Operations stand-in for this demo. Both routes were live-tested against the
same private chat, with matching correlation and Teams `201` receipts. An
organization must review its real contract-owner-to-flow-destination mapping;
the code does not discover or verify that mapping. Receipt recording is an
explicit operator-checked step, not an automatic claim by the sender. Local
evidence relies on trusted filesystem access and is not tamper-proof.

The implementation composes supported services with small control-specific
adapters rather than adding a governance platform or LLM evaluator. Its community
value is the demonstrated link from a declared target to verified outcomes and
a human-facing review request. Resolve the release blockers before presenting
that pattern as independently reproducible for organizational implementation.