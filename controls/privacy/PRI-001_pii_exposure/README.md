<p align="center">
  <img src="../../../media/themepack/fwf-badge-small-with-pic.png" alt="Forged with Foundry implemented control" width="216">
</p>

# PRI-001 — PII exposure

> **Status:** Validated
>
> **Last reviewed:** 2026-08-31 against the Microsoft references below.

## Overview

PRI-001 demonstrates a deterministic PII enforcement boundary around an AI
agent. Chat text uses Azure AI Language Text PII; PDF, DOCX, and TXT uploads use
native Document PII. Raw detected PII never reaches Agent Framework or GPT-5.
The model response passes through the same outbound text control before display.

> **Governance outside the agent; intelligence inside the agent.**

### Interface preview

![PRI-001 PII governance demo showing the Chainlit governance console](../../../media/pii-governance-demo.png)

## Control contract

| Field | Value |
|---|---|
| **ID** | PRI-001 |
| **Lifecycle phase** | Live |
| **Category / domain** | Privacy |
| **Control / signal** | PII exposure |
| **Evidence / source** | DLP/content safety event |
| **Trigger / threshold** | 1 occurrence |
| **Action / gate effect** | Immediate escalation |
| **Accountable role** | Privacy Officer |

## Control objective

Prevent ungoverned PII from crossing into or out of the AI-agent boundary. The
policy is deterministic: zero findings are allowed, one or more findings require
redaction and immediate metadata-only escalation, and any mandatory enforcement
failure is blocked fail closed.

Detection and redaction are separate outcomes:

| Term | Meaning | Governance consequence |
|---|---|---|
| **Detected** | Azure AI Language returned structured PII findings containing safe metadata such as category and confidence, but no entity value. | Detection drives the PRI-001 decision. One occurrence triggers escalation. |
| **Redacted** | Azure AI Language produced separate transformed text or a native document in which detected values are masked. | Only redacted output—not the original—may cross the enforcement boundary. |

Detection does not prove that redaction succeeded. Agent handoff requires safely
redacted output whenever PII was detected.

## Logical design

```mermaid
flowchart LR
    U[User] --> UI[Chainlit]

    subgraph B[Deterministic PRI-001 boundary]
        UI --> T{Input type}
        T -->|Chat text| TP[Text PII detect and redact]
        T -->|PDF DOCX TXT| DP[Native Document PII]
        TP --> P{PRI-001 decision}
        DP --> P
        P -->|No findings| A[ALLOW]
        P -->|One or more findings| RE[REDACT AND ESCALATE]
        P -->|Detection or redaction failure| BL[BLOCK]
        RE --> ES[Metadata-only Privacy Officer event]
    end

    A --> H[Governed handoff]
    RE --> H
    BL -. no handoff .-> UI
    H --> AF[Agent Framework]
    AF --> M[GPT-5]
    M --> OP[Outbound Text PII]
    OP -->|Safe or safely redacted| UI
    OP -->|Control failure| BL

    classDef governance fill:#6E56CF,stroke:#A855F7,color:#FFFFFF
    classDef platform fill:#3B82F6,stroke:#00D4FF,color:#FFFFFF
    classDef evidence fill:#00D4FF,stroke:#3B82F6,color:#0D1117
    classDef intelligence fill:#A855F7,stroke:#6E56CF,color:#FFFFFF
    classDef neutral fill:#1F2937,stroke:#6E56CF,color:#FFFFFF
    classDef success fill:#22C55E,stroke:#22C55E,color:#0D1117
    classDef attention fill:#F59E0B,stroke:#F59E0B,color:#0D1117
    class U neutral
    class UI,T,TP,DP platform
    class P governance
    class A,H success
    class RE,BL,ES attention
    class AF,M intelligence
    class OP evidence
```

## Infrastructure architecture

```mermaid
flowchart TB
    DEV[Local Chainlit demo]

    subgraph RG[Azure resource group]
        subgraph F[Microsoft Foundry AI Services]
            PRJ[Default project]
            MODEL[gpt-5 deployment]
            PRJ --> MODEL
        end

        subgraph L[Azure AI Language]
            TEXT[Text PII]
            DOC[Document PII API 2026-05-01]
            MI[System-assigned managed identity]
        end

        subgraph S[OAuth-only Blob Storage]
            SRC[Private pii-source container]
            TGT[Private pii-redacted container]
        end
    end

    DEV -->|Entra ID| PRJ
    DEV -->|Cognitive Services User| TEXT
    DEV -->|Cognitive Services User| DOC
    DEV -->|Storage Blob Data Contributor| SRC
    DOC -->|Managed identity reads| SRC
    DOC -->|Managed identity writes| TGT
    MI -. RBAC .-> S
    DEV -->|Download then delete artifacts| TGT

    classDef governance fill:#6E56CF,stroke:#A855F7,color:#FFFFFF
    classDef platform fill:#3B82F6,stroke:#00D4FF,color:#FFFFFF
    classDef evidence fill:#00D4FF,stroke:#3B82F6,color:#0D1117
    classDef intelligence fill:#A855F7,stroke:#6E56CF,color:#FFFFFF
    classDef neutral fill:#1F2937,stroke:#6E56CF,color:#FFFFFF
    class DEV neutral
    class MI platform
    class PRJ governance
    class MODEL intelligence
    class TEXT,DOC,SRC,TGT evidence
```

## Implementation

### Components

| Component | Responsibility | Location |
|---|---|---|
| Chainlit orchestration | Shows Detect → Decide → Redact → Handoff and prevents partial handoff | [app/pri_001/chat.py](../../../app/pri_001/chat.py) |
| Text PII | Detects and redacts inbound chat and outbound model text | [app/pri_001/text_pii.py](../../../app/pri_001/text_pii.py) |
| Native Document PII | Processes PDF, DOCX, and TXT without custom extraction/reconstruction | [app/pri_001/document_pii.py](../../../app/pri_001/document_pii.py) |
| Policy | Applies deterministic `ALLOW`, `REDACT_AND_ESCALATE`, or `BLOCK` decisions | [app/pri_001/policy.py](../../../app/pri_001/policy.py) |
| Escalation | Emits metadata-only Privacy Officer events | [app/pri_001/escalation.py](../../../app/pri_001/escalation.py) |
| Agent adapter | Invokes GPT-5 only with governed content | [app/pri_001/agent.py](../../../app/pri_001/agent.py) |
| Infrastructure | Deploys Foundry, Language, Storage, identities, and RBAC | [infra/main.bicep](../../../infra/main.bicep) |

### Decision rules

| Detection | Required redaction | Decision | Handoff |
|---|---|---|---|
| No findings | Not required | `ALLOW` | Original content may continue |
| One or more findings | Succeeded | `REDACT_AND_ESCALATE` | Redacted content only |
| One or more findings | Failed or incomplete | `BLOCK` | None |
| Detection unavailable | Cannot be proven | `BLOCK` | None |

The escalation event contains only the control ID, categories, count, action,
accountable role, source type, timestamp, and event ID. It excludes entity
values, source text, filenames, and document contents.

### Best-practice choices

- Policy enforcement runs outside model reasoning.
- Authentication uses Microsoft Entra ID; local keys and shared-key Blob access
  are disabled.
- Document processing uses a Language managed identity and scoped Storage Blob
  Data Contributor access.
- Uploaded filenames are replaced with UUID-based generic Blob paths.
- Native results and source artifacts are deleted after processing.
- TLS verification remains enabled and uses the operating-system trust store.
- Native Document PII uses the GA `2026-05-01` API instead of a preview version.
- Errors are sanitized and mandatory enforcement fails closed.

### Why native Document PII?

Azure AI Language handles extraction, detection, redaction, and native-file
reconstruction in one asynchronous workflow. It returns both a redacted artifact
and structured JSON results. This avoids a custom PDF/DOCX parsing pipeline,
reduces sensitive intermediate data, and preserves document fidelity.

## Demo

### Prerequisites

- Python 3.10–3.13 and dependencies from the repository requirements file.
- Azure CLI authentication through `az login`.
- Deployed shared infrastructure described in [infra/README.md](../../../infra/README.md).
- A configured local `.env` copied from the repository example.
- Synthetic PII only; do not use real personal data for demonstrations.

### Deploy

From the repository root:

```bash
./infra/deploy.sh
```

Use Bash, not `sh`, because the deployment wrapper uses Bash syntax.

### Run

```bash
chainlit run chainlit_app.py -w
```

### Expected scenarios

| Scenario | Input | Expected decision | Expected evidence |
|---|---|---|---|
| No PII | A normal governance question | `ALLOW` | `NOT_DETECTED`, redaction not required, governed handoff |
| Synthetic text PII | A synthetic name and email address | `REDACT_AND_ESCALATE` | Redacted preview and metadata-only event reference |
| Synthetic document PII | PDF, DOCX, or TXT up to 10 MB | `REDACT_AND_ESCALATE` | Microsoft-generated redacted file and metadata-only event |
| Language/Storage failure | Unavailable or unauthorized dependency | `BLOCK` | Sanitized fail-closed status and no GPT-5 handoff |
| Model output containing PII | Synthetic model response | Outbound redaction or block | Governed response only |

## Evidence and observability

Safe evidence includes the control ID, action, source type, finding count,
categories, accountable role, timestamp, and correlation/event ID. Logs and
webhook payloads must never contain source text, detected values, uploaded
filenames, original document contents, or model prompts containing PII.

## Security and privacy

- Blob containers are private and shared-key access is disabled.
- Language and local users receive scoped data-plane roles through Azure RBAC.
- Generic source and output names prevent filename disclosure.
- Original and generated Blob artifacts are deleted after download.
- Mixed requests are transactional: an unsupported or failed attachment blocks
  the entire handoff.
- The original document is never sent to GPT-5; non-TXT documents contribute
  metadata only to the agent context.
- The application fails closed when detection, redaction, authorization, polling,
  or artifact retrieval cannot be completed safely.

## Validation

### Automated tests

```bash
python -m compileall -q app chainlit_app.py tests
python -m pytest -q
```

Tests cover deterministic policy decisions, fail-closed messaging, generic Blob
names, metadata-only findings, and the user-facing separation of detection from
redaction.

### Manual checks

The implementation has been validated with text and a native PDF workflow,
including asynchronous polling, redacted artifact retrieval, cleanup, GPT-5
handoff, and outbound PII enforcement.

### Known limitations

- The demo supports PDF, DOCX, and TXT files up to 10 MB.
- Local execution uses Azure CLI credentials; a hosted deployment should use its
  workload managed identity.
- Public network access remains enabled in this simple demo architecture.
- RBAC assignments can require propagation time after deployment.
- The metadata webhook is optional and must be configured separately.

## Cleanup

Delete the shared demo resource group only when no other control demo depends on
it:

```bash
az group delete --name <AZURE_RESOURCE_GROUP> --yes --no-wait
```

## References

- [Azure AI Language PII overview](https://learn.microsoft.com/azure/ai-services/language-service/personally-identifiable-information/overview)
- [Text PII quickstart](https://learn.microsoft.com/azure/ai-services/language-service/personally-identifiable-information/quickstart)
- [Document-based PII overview](https://learn.microsoft.com/azure/ai-services/language-service/personally-identifiable-information/document-based-pii-overview)
- [Detect and redact PII in native documents](https://learn.microsoft.com/azure/ai-services/language-service/personally-identifiable-information/how-to/redact-document-pii)
- [Managed identities for native document support](https://learn.microsoft.com/azure/ai-services/language-service/native-document-support/managed-identities)
- [Source governance catalog](../../../docs/Governance%20Signals%20Repo.pdf)

---

<p align="center">
  <img src="../../../media/themepack/fwf-footer.png" alt="Forged with Foundry" width="814">
</p>
