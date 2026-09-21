---
title: VAL-001 prerelease review
description: Final review of correctness, evidence, cleanup boundaries, and community reproducibility for the implemented demo.
ms.date: 2026-09-21
---

## Verdict

Implemented. The hosted-workload-to-KPI-to-Teams path, fail-closed measurement
route, deterministic evidence, and ownership-scoped Azure cleanup were
validated. The demo is suitable for community learning within its documented
scope. It does not claim deletion of platform conversation history or Teams
test state that the external platforms do not expose to this cleanup command.

## Resolved findings and accepted boundaries

1. **Accepted boundary: external synthetic-state cleanup.**
   [The runner](../demo.py#L76) creates platform conversations but does not retain
   their identifiers. [Azure cleanup](../infra/cleanup.py#L114) deliberately
   excludes conversation history and Teams state. Nine session filesystems,
   the agent, and control-owned Monitor resources were removed and verified,
   but that is not proof of conversation/message deletion. Cleanup now also
   requires the recorded hosted-agent instance principal before deleting the
   agent. The control documents this limitation and provides scoped Teams
   cleanup instructions; it never claims complete deletion or deletes a shared
   project or chat as a workaround.
2. **Resolved: deployment ordering and identity configuration.**
   [The runbook](IMPLEMENTATION.md#deployment-configuration) records the corrected
   ordering, preview versions, and required environment values. Actual development
   required multiple repairs to authentication, platform environment variables,
   and publisher identity. The corrected order and identity boundary are now
   recorded in the implementation guide.
3. **Accepted follow-up: minimized runner diagnostics.**
   [Invocation output](../demo.py#L81) is captured, then a broad CLI handler reports
   a generic error. Earlier attempts stopped and later attempts succeeded, but
   the original failure was not conclusively diagnosed. Retain a minimized
   failure stage, exit code, and safe correlation, without raw SDK responses,
   URLs, tokens, or model text. Do not turn this into a general logging framework.
4. **Resolved: README release surface.**
   [The README](../README.md) combines two substantial diagrams, resource inventory,
   routing rationale, future reporting, commands, and capture instructions.
   The README now identifies the implemented decision, proof, limitations, and
   next action before the technical walkthrough.
5. **Resolved: observability authority boundary.**
   [The walkthrough](OBSERVABILITY-AGENT.md#1-run-the-kpi-query) now surfaces
   invalid events rather than filtering them into a passing result. It remains
   descriptive only; the JSON evidence record is authoritative.

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

The control test run passed 80 tests. The full repository suite remains the
final regression check for the change. The Monitor template compiled. Real
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
a human-facing review request. Organizations must still review their
tenant-specific owner mapping and external cleanup capabilities.