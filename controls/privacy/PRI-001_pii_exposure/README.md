# PRI-001 — PII exposure

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

## Implementation

This demo enforces PRI-001 before content reaches the AI agent. Policy behavior
is deterministic: zero findings are allowed, one or more findings are redacted
and immediately escalated, and any enforcement failure is blocked.

### Detected versus redacted

These terms describe different stages and must not be used interchangeably:

| Term | Meaning | Governance consequence |
|---|---|---|
| **Detected** | Azure AI Language returned one or more structured PII findings. A finding contains safe metadata such as category and confidence, but no entity value. | Detection is the signal evaluated by PRI-001. One occurrence triggers immediate Privacy Officer escalation. |
| **Redacted** | Azure AI Language produced a separate transformed text or native document in which detected values are masked. | Redacted output—not the original—may cross the enforcement boundary. |

The policy decision is based on **detection**. Agent handoff is based on the
availability of safely **redacted** output. Detection does not prove that
redaction succeeded. If detection or required redaction fails, processing is
blocked fail-closed.

| Input/output | Enforcement path |
|---|---|
| Chat input | Azure AI Language Text PII → policy → governed agent handoff |
| PDF/DOCX/TXT | Blob Storage → native Document PII → policy → redacted artifact |
| Agent output | Azure AI Language Text PII → governed UI display |

The escalation event contains only the control ID, categories, count, action,
role, source type, timestamp, and event ID. It never contains entity values,
source text, filenames, or document contents.

### Why native Document PII?

For supported files, Azure AI Language performs extraction, detection,
redaction, and native-file reconstruction as one asynchronous service workflow.
This avoids a custom PDF/DOCX parsing pipeline and preserves document fidelity.

### Run

From the repository root, deploy infrastructure and start Chainlit:

```bash
./infra/deploy.sh
chainlit run chainlit_app.py -w
```

Implementation: [app/pri_001](../../../app/pri_001).

> **Governance outside the agent; intelligence inside the agent.**
