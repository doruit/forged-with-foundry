# PRI-001 — control assessment

## Decision

- **Classification:** `COMPOSE`
- **Proceed / revise / reject:** Proceed with the current core-demo boundary
- **Review date:** 2026-09-03
- **Learning level:** Foundation

## Reuse decision

PRI-001 reuses Azure AI Language Text PII and native Document PII for detection,
redaction, document extraction, and native-file reconstruction. It does not
reimplement those platform capabilities. Microsoft Foundry supplies the agent
and model path.

The smallest justified custom layer is the deterministic control contract,
safe orchestration, metadata-only escalation, and the enforced handoff before
and after the agent call.

AGT and ACS were evaluated. They can standardize `input`, `pre_model_call`, and
`output` intervention points, transforms, and evidence. They are intentionally
not included in this foundation-level core demo because the visible host
boundary teaches the Document PII composition with less setup. They remain a
documented optional exploration path.

## Unique learning outcome

Show that detecting PII is not the same as safely redacting it, and that only a
successfully governed representation may cross into or out of an agent boundary.

## Community boundary

- **Core demo:** Text and native-document PII enforcement around one Foundry
  agent interaction.
- **Intentional simplifications:** Local Azure CLI identity, public endpoints,
  local/optional-webhook escalation, and no ACS adapter.
- **Further exploration:** Workload identity, private networking, durable
  evidence and cleanup monitoring, and optional standardized ACS intervention
  points.
- **What it does not prove:** Complete PII recall, compliance, production
  isolation, or mediation of application paths outside this demo.

## Authoritative references

- [Document-based PII overview](https://learn.microsoft.com/azure/ai-services/language-service/personally-identifiable-information/document-based-pii-overview)
- [Detect and redact PII in native documents](https://learn.microsoft.com/azure/ai-services/language-service/personally-identifiable-information/how-to/redact-document-pii)
- [Managed identities for native document support](https://learn.microsoft.com/azure/ai-services/language-service/native-document-support/managed-identities)
- [Agent Control Specification](https://github.com/microsoft/agent-governance-toolkit/tree/main/policy-engine)
