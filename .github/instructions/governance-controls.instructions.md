---
applyTo: "controls/**/*"
---

Before changing a control, read its complete README, assessment, source,
infrastructure, tests, and known limitations.

Keep the control bite-sized and independently runnable. Do not expand it into a
reusable platform unless at least two other implemented controls demonstrably
need the same abstraction.

Preserve or improve explicit authority boundaries, deterministic rules,
fail-closed behavior, least privilege, managed identity where supported, data
minimization, safe evidence, action verification, synthetic scenarios, and
precise non-claims.

For every custom component, record which AGT, ACS, Foundry, APIM, Purview,
Defender, Entra, Content Safety, Language, Monitor, Application Insights, or
other Microsoft capability was evaluated first and why custom code remains
necessary.

Reject changes that merely reproduce an official quickstart without adding a
distinct governance scenario, composition, evidence pattern, or learning
outcome.
