# PRI-002 — control assessment

## Decision

- **Classification:** `COMPOSE`
- **Proceed / revise / reject:** Proceed as a complete small teaching demo;
  retain the documented optional exploration paths
- **Review date:** 2026-09-03
- **Learning level:** Foundation / Intermediate

## Reuse decision

PRI-002 reuses Azure Blob Lifecycle Management as the primary retention control,
Blob index tags as the selection signal, ETag conditions for stale-state
protection, soft delete for recovery, and Microsoft Foundry for non-authoritative
explanation.

The custom scanner adds a distinct learning outcome: a mistagged record can sit
outside a correct lifecycle filter, so the platform rule and exception-detection
control solve different problems.

**Model/Foundry role: Active — governed subject.** The guarded delete is a real
Agent Control Specification `pre_tool_call`/`post_tool_call` intervention-point
pair (`src/pri_002/acs_gate.py`), not a bespoke in-memory approval registry.
ACS's policy dispatcher escalates every guarded delete; the Chainlit "Approve
guarded deletion" click resolves that escalation through `approval_resolver`,
and ACS's `action_identity` binds the approval to the exact blob_name/etag pair
it evaluated — the same binding guarantee the removed `ApprovalRegistry` gave,
now provided by ACS itself. A native Python `PolicyDispatcher` is used (no
OPA/Rego bundle), consistent with PRI-001.

## Unique learning outcome

Show the difference between configuring a platform retention rule and detecting
records that the rule cannot select because their governance metadata is wrong.

## Community boundary

- **Core demo:** Seed, scan metadata, explain deterministic outcomes, explicitly
  approve one guarded delete, verify active absence, and retain recovery through
  soft delete.
- **Intentional simplifications:** Projected age/hold tags, a native Python ACS
  policy dispatcher instead of an OPA/Rego bundle, local evidence, public
  endpoint, and on-demand scanning.
- **Further exploration:** Authenticated approvers, durable evidence,
  lifecycle-run events, and private networking.
- **What it does not prove:** Legal compliance, physical erasure, exact lifecycle
  timing, restart-safe approval, or organization-wide exception discovery.

## Optional community follow-up

- Keep lifecycle-policy and deterministic deadline semantics aligned.
- Restrict seed and cleanup operations to Blobs explicitly tagged as PRI-002
  synthetic demo records.
- Add an optional Azure integration test for ETag-conditional deletion and
  active-absence verification.

## Authoritative references

- [Azure Blob Storage lifecycle management](https://learn.microsoft.com/azure/storage/blobs/lifecycle-management-overview)
- [Monitor lifecycle management policy runs](https://learn.microsoft.com/azure/storage/blobs/lifecycle-management-policy-monitor)
- [Conditional Blob operations](https://learn.microsoft.com/rest/api/storageservices/specifying-conditional-headers-for-blob-service-operations)
- [Agent Control Specification](https://github.com/microsoft/agent-governance-toolkit/tree/main/policy-engine)
