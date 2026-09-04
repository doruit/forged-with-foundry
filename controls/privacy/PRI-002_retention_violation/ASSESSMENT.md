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

The local approval registry overlaps with AGT's action-bound approval protocol
(currently a proposed AGT design, not yet implemented). It remains only as a
single-process teaching approximation in the core demo and must not be
presented as a full approval service. If Blob
deletion becomes an agent tool, the preferred extension is AGT approval at an
ACS `pre_tool_call` intervention point while retaining Blob ETag revalidation.

## Unique learning outcome

Show the difference between configuring a platform retention rule and detecting
records that the rule cannot select because their governance metadata is wrong.

## Community boundary

- **Core demo:** Seed, scan metadata, explain deterministic outcomes, explicitly
  approve one guarded delete, verify active absence, and retain recovery through
  soft delete.
- **Intentional simplifications:** Projected age/hold tags, in-memory approval,
  local evidence, public endpoint, and on-demand scanning.
- **Further exploration:** AGT action-bound approval, ACS tool mediation,
  authenticated approvers, durable evidence, lifecycle-run events, and private
  networking.
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
- [AGT action-bound approval protocol (proposed, not yet implemented in AGT)](https://github.com/microsoft/agent-governance-toolkit/blob/main/docs/adr/0030-action-bound-approval-protocol.md)
- [Agent Control Specification](https://github.com/microsoft/agent-governance-toolkit/tree/main/policy-engine)
