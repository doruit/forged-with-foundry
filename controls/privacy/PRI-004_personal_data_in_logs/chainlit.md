# PRI-004 Log Operations Agent

This guided demo shows how an AI agent can help a Privacy Officer respond to
personal data that has reached application logs, without giving the model
mask, purge, or logging-policy authority.

## What happens

1. Ingest three synthetic log entries via the real Logs Ingestion API.
2. Scan them with Azure AI Language Text PII and a deterministic policy.
3. Let the Foundry agent explain the safe metadata-only result.
4. Preview a redacted mask for a record with detected personal data.
5. Request a real, guarded Azure Monitor Data Purge — asynchronous, up to
   30 days to complete.
6. Suppress a field going forward and see the fix apply to a new record.

> **The control decides. The agent explains and orchestrates. The guarded tool masks, purges, or updates logging.**
