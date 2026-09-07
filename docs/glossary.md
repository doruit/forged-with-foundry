# Glossary

Short definitions for terms used across this repository's control READMEs.
Each control still spells out a term in plain language on first use; this
page is a quick reference for a reader who lands on a single control README
without having read the root README first.

| Term | Meaning |
|---|---|
| **Microsoft Foundry** | Microsoft's platform for building, deploying, and governing AI models and agents. Most demos in this repository deploy a Foundry project and a chat model deployment as shared infrastructure. |
| **Agent Framework** | The Microsoft SDK used to build the Foundry agent that appears in some demos. It sends governed content to a model deployment and returns a response. |
| **AGT (Agent Governance Toolkit)** | Microsoft's toolkit and reference examples for governing AI agents. Referenced where it contributes an official pattern; most demos in this catalog use its sibling, ACS, directly. |
| **ACS (Agent Control Specification)** | A stateless runtime that gates specific points in an agent's execution (see "intervention point") with an `allow`/`deny`/`escalate`/`warn` verdict, and enforces that verdict in code — the actual `input`/`output` or `pre_tool_call`/`post_tool_call` boundary demonstrated in this repository's controls. |
| **Intervention point** | One of the fixed points ACS can gate: `agent_startup`, `input`, `pre_model_call`, `post_model_call`, `pre_tool_call`, `post_tool_call`, `output`, `agent_shutdown`. Each control uses only the points relevant to its risk. |
| **Policy dispatcher** | The small piece of code a control provides to ACS that returns the verdict (`allow`, `deny`, `escalate`, `warn`) for a given intervention point. In this repository it is always a plain Python function/class (`acs_gate.py`), not an OPA/Rego bundle. |
| **`action_identity`** | A hash ACS computes automatically from the exact tool-call arguments (or content) it evaluated. An approval is bound to this identity; if the underlying data changes after evaluation, the identity changes too, and a stale approval is rejected. |
| **Approval ticket** | This repository's explicit, single-use record that a human genuinely approved one guarded action (used, rejected, or expired), created at the moment of the real approval event — never inferred just because a function was called. |
| **Fail closed** | When a control cannot safely evaluate or complete an action (missing data, an unavailable dependency, a policy violation), it blocks the action rather than allowing it by default. |
| **Deterministic policy** | A decision made by plain code from structured inputs, with no model/LLM reasoning involved — the model may explain the decision afterward, but never makes or changes it. |
| **Model/Foundry role** | A Demo profile field stating whether a model is `Active — governed subject` (content passes through it and is gated), `Explanatory only` (it narrates an already-final decision), or `Not used`. |
| **DPIA (Data Protection Impact Assessment)** | A required GDPR assessment of privacy risk before starting a high-risk processing activity. See [PRI-PRE-001](../controls/privacy/PRI-PRE-001_dpia_required_but_missing/README.md). |
| **DSR (Data Subject Request)** | A GDPR request from an individual (for example, to access, correct, or erase their data), typically bound by a response-time SLA. See [PRI-003](../controls/privacy/PRI-003_data_subject_request_sla_breach/README.md). |
| **DLP (Data Loss Prevention)** | Detection and control of sensitive data leaving an authorized boundary. |
| **PII (Personally Identifiable Information)** | Data that can identify an individual, such as a name, email address, or government ID number. |
| **Sensitivity label** | A Microsoft Purview classification (for example, "Confidential") applied to a file or email to drive protection and handling policy. See [DAT-PRE-002](../controls/data_and_knowledge/DAT-PRE-002_data_classification_missing/README.md). |
| **RBAC (Role-Based Access Control)** | Azure's model for granting identities specific permissions on specific resources, used throughout this repository instead of shared keys or connection strings. |
| **Managed identity** | An Azure identity automatically managed by the platform, used so demo code authenticates without storing a credential. |
| **Guided exercise / Hybrid demo / Deployable demo** | This repository's three demo formats, in increasing order of what gets deployed. See [Purpose](../README.md#purpose) in the root README for the full definition and when each is used. |

For the full reuse-first design rules behind these terms, see
[.github/copilot-instructions.md](../.github/copilot-instructions.md).
