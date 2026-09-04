# PRI-001 — control assessment

## Decision

- **Classification:** `COMPOSE`
- **Proceed / revise / reject:** Proceed with the current core-demo boundary
- **Review date:** 2026-09-04
- **Learning level:** Foundation

## Reuse decision

PRI-001 reuses Azure AI Language Text PII and native Document PII for detection,
redaction, document extraction, and native-file reconstruction. It does not
reimplement those platform capabilities. Microsoft Foundry supplies the agent
and model path.

The smallest justified custom layer is the deterministic control contract
(`policy.py`), safe orchestration, metadata-only escalation, and a native
Python Agent Control Specification (ACS) policy dispatcher that re-expresses
that one decision as a Verdict.

**Model/Foundry role: Active — governed subject.** ACS's `input` and `output`
intervention points are the real enforcement boundary around the Foundry
agent turn, not documentation: `acs_gate.py` calls
`AgentControl.evaluate_intervention_point()` and `AgentControl.enforce()`
before governed content reaches `GovernedAgent.run()` and again before the
agent's response reaches the user, and a `deny` verdict raises
`AgentControlBlocked` and fails closed even if the local PRI-001 decision was
less strict. ACS runs with a `custom` policy type and a native Python
`PolicyDispatcher` (`policy/acs_manifest.yaml` +
`PiiPolicyDispatcher.evaluate()`) — no OPA/Rego bundle — so PRI-001 keeps
exactly one place PII policy is authored (`policy.py`) while ACS becomes the
actual gate the content must cross. Only the decision's action, PII count,
and category names cross the ACS boundary; ACS never receives raw text or
PII entity values.

Microsoft Purview Data Security for Microsoft Foundry (Audit, sensitive
information type classification, DLP, DSPM for AI) was evaluated (2026-09-04)
and is not used in this control. Microsoft's own AI-services onboarding
documentation states the integration "does not include data or context from
Foundry agents" and that "support for Foundry agent integration is not
available at this time" — Purview currently observes only direct Foundry
model/`chat/completions` calls made with a Microsoft Entra user-context token,
not Agent Service interactions, which is the boundary PRI-001 governs. Reusing
it here would misrepresent an unsupported capability. Revisit this evaluation
when Microsoft documents Foundry agent support for Purview Data Security.

## Unique learning outcome

Show that detecting PII is not the same as safely redacting it, and that only a
successfully governed representation may cross into or out of an agent boundary.

## Community boundary

- **Core demo:** Text and native-document PII enforcement around one Foundry
  agent interaction, with Agent Control Specification enforcing the `input`
  and `output` intervention points around the agent call.
- **Intentional simplifications:** Local Azure CLI identity, public
  endpoints, local/optional-webhook escalation, and a native Python ACS
  policy dispatcher instead of an OPA/Rego bundle.
- **Further exploration:** Workload identity, private networking, durable
  evidence and cleanup monitoring, and `pre_tool_call`/`post_tool_call` ACS
  coverage if this control grows autonomous tool calls.
- **What it does not prove:** Complete PII recall, compliance, production
  isolation, or mediation of application paths outside this demo.

## Authoritative references

- [Document-based PII overview](https://learn.microsoft.com/azure/ai-services/language-service/personally-identifiable-information/document-based-pii-overview)
- [Detect and redact PII in native documents](https://learn.microsoft.com/azure/ai-services/language-service/personally-identifiable-information/how-to/redact-document-pii)
- [Managed identities for native document support](https://learn.microsoft.com/azure/ai-services/language-service/native-document-support/managed-identities)
- [Enable threat protection for AI services (Purview Foundry-agent limitation)](https://learn.microsoft.com/en-us/azure/defender-for-cloud/ai-onboarding)
- [Agent Control Specification](https://github.com/microsoft/agent-governance-toolkit/tree/main/policy-engine)
