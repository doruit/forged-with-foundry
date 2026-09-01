# PRI-001 PII Governance Demo

This demonstration places a deterministic PII enforcement boundary before
Microsoft Agent Framework and GPT-5.

## Detected versus redacted

| Status | What it means | What happens next |
|---|---|---|
| **Detected** | Azure AI Language found PII. The demo shows only safe metadata such as category and count. | PRI-001 triggers immediate Privacy Officer escalation. |
| **Redacted** | Azure AI Language created a separate transformed output in which detected values are masked. | Only this redacted output may cross into the agent boundary. |

Detection is a **governance signal**. Redaction is a **content transformation**.
A successful detection does not by itself prove that redaction succeeded. If
detection or required redaction cannot be completed safely, PRI-001 blocks the
request.

## What to watch in the chat

Every request visibly moves through four phases:

1. **Detect** PII.
2. **Decide** using deterministic PRI-001 policy.
3. **Redact** when PII was detected.
4. **Handoff** only allowed or redacted content to GPT-5, then check its response again.

## Try it

- Enter a chat message with or without synthetic PII.
- Upload a PDF, DOCX, or TXT file of at most 10 MB.
- Observe the allow, redact-and-escalate, or fail-closed policy decision.
- Download the Microsoft-generated redacted document when native processing succeeds.

Raw detected PII is never sent to GPT-5. Escalation events contain metadata only
and are assigned to the Privacy Officer after the first occurrence.

> **Governance outside the agent; intelligence inside the agent.**
