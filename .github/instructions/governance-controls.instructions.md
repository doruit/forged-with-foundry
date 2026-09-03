---
applyTo: "controls/**/*"
---

Before changing a control, read its complete README, assessment, known
limitations, and any exercise artifacts, source, infrastructure, or tests that
are present.

Keep the control bite-sized, independently usable, and reproducible. Select the
smallest effective format: `GUIDED_EXERCISE`, `HYBRID_DEMO`, or
`DEPLOYABLE_DEMO`. Do not expand it into a reusable platform unless at least two
other implemented controls demonstrably need the same abstraction.

Do not introduce an application, agent, cloud resource, AGT, ACS, or custom code
merely to make a control appear technical. Use deployment only when it adds a
distinct learning outcome that a guided evidence-and-decision exercise cannot
show as clearly. Requirements for infrastructure, automated tests, deployment,
and cleanup apply only when the selected format creates or executes them.

Preserve or improve explicit authority boundaries, deterministic rules,
fail-closed behavior, least privilege, managed identity where supported, data
minimization, safe evidence, action verification, synthetic scenarios, and
precise non-claims.

For every custom technical component, record which AGT, ACS, Foundry, APIM, Purview,
Defender, Entra, Content Safety, Language, Monitor, Application Insights, or
other Microsoft capability was evaluated first and why custom code remains
necessary.

Reject changes that merely reproduce an official quickstart without adding a
distinct governance scenario, composition, evidence pattern, or learning
outcome.

When this change sets a control's status to `Implemented` or `Validated`,
update the repository root `README.md` in the same change per the Root README
navigation rules in `.github/copilot-instructions.md`. A control change is not
complete until the root README reflects the control's current status.
