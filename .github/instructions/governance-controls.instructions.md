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

When Azure resources or configuration are deployed, add a focused `Inspect in
Azure` walkthrough to the README. Show where to find the relevant resource and
configuration in Azure Portal, what the user should verify, and why it matters
to the control. Include configuration such as identity, RBAC, lifecycle,
networking, diagnostics, or monitoring only where relevant. Keep
environment-specific identifiers and secrets out of the documentation.

`Logical design` and `Infrastructure architecture` are two different diagram
types; do not reuse one shape for both. `Logical design` shows the decision
flow: inputs, checks, branches, and outcomes, and a linear or branching
sequence is correct there. `Infrastructure architecture` is a building-blocks
overview of what runs where, not a numbered execution trace, so never model
it as a single `A --> B --> C --> D` chain that just replays the demo script's
call order. Group nodes with mermaid `subgraph` blocks by the environment or
boundary they actually run in, such as a CI/CD environment (GitHub Actions or
Azure DevOps), the developer or pipeline execution context, the Azure
subscription or resource group, and Microsoft Foundry when the control uses
it. Show only the relationships that matter at that level, such as which
service calls which, and which policy scope applies to which assignment, not
every local script's internal call order. When a control both provisions
resources through an IaC tool (Bicep or Terraform) and separately calls the
Azure CLI at demo run time, show these as two distinct building blocks with
different timing, not one merged node, since one runs once during setup and
the other runs on every demo execution. Every mermaid `subgraph` must carry an
explicit `style <id> fill:...,stroke:...,color:...` line with readable
contrast; do not leave a subgraph container on mermaid's default styling,
which renders unreadable against this repository's dark rendering theme.

Every control's Demo section must include real captured proof that the demo
was actually run, not only a description of the output you expect to see.
Acceptable proof is a screenshot of the relevant UI (Azure Portal, Chainlit,
or similar) or a copy-pasted transcript of real terminal output from actually
executing the demo script or command. Capture this proof by actually running
the documented core path before marking a control `Implemented` or
`Validated`, and add it under the Demo section, with a short caption per
artifact stating what it shows and why it matters to the control. Never
present a hypothetical, templated, or reconstructed transcript as if it were
captured evidence. When a walkthrough requires many browser screenshots,
follow `.github/instructions/screenshot-capture-workflow.instructions.md` for
context-window management.

When an optional extension depends on external platform configuration this
repository's own IaC cannot provision, such as a GitHub repository's
Environments, Actions variables, or OIDC federation settings, verify it by
actually running it end to end against a disposable external resource, such
as a throwaway companion repository, rather than claiming it works from code
review alone. Delete or clearly mark that disposable resource as temporary
afterward, and fold any real finding the live run surfaces, such as an
unexpected token claim shape or a platform-specific error code, back into the
control's own README and this repository's memory so it is not re-discovered
next time.

Preserve or improve explicit authority boundaries, deterministic rules,
fail-closed behavior, least privilege, managed identity where supported, data
minimization, safe evidence, action verification, synthetic scenarios, and
precise non-claims.

For every custom technical component, record which AGT, ACS, Foundry, APIM, Purview,
Defender, Entra, Content Safety, Language, Monitor, Application Insights, or
other Microsoft capability was evaluated first and why custom code remains
necessary.

Use every supported capability that materially contributes to the control's
signal, decision, enforcement point, governance action, or evidence in the core
demo. Make its role visible in the architecture, walkthrough, and expected
evidence. Do not relegate a capability to `Further exploration` when it is part
of the primary learning outcome. If an apparently relevant capability is not
used, document the concrete reason in `ASSESSMENT.md` and the demo scope.

Every `ASSESSMENT.md` must state the control's **Model/Foundry role** as one of
three postures, and justify it:

- **Active — governed subject:** a real Foundry agent or model `input`,
  `pre_tool_call`/`post_tool_call`, or `output` event is gated through a real
  Agent Control Specification (ACS) `AgentControl` intervention point. The
  deterministic policy becomes the ACS policy dispatcher that the intervention
  point calls, not code the application calls directly and unmediated.
- **Explanatory only:** Foundry narrates an already-computed decision and adds
  no enforcement authority. Permitted only when the control's authoritative
  signal is genuinely platform or data state with no agent action in the loop
  (for example, a Blob lifecycle scan). Label this posture explicitly in the
  Demo profile table so a reader never mistakes narration for enforcement.
- **Not used — not applicable to the core path:** the authoritative control is
  administrative, configuration-based, or enforced by another supported
  platform capability, and adding a model or agent would only add narration or
  complexity. Foundry may still be the governed workload or data context; state
  that relationship without deploying or simulating an agent.

Default to the Active posture whenever a control's signal or governance action
is agent, tool, or autonomy behavior — this includes every control in
`autonomy_and_human_oversight` and `tool_governance`, the prompt-injection and
tool-misuse signals in `security`, and the agent-loop or context-contamination
signals in `runtime_and_operations`. For data-, configuration-, or
administrative-state controls, default to Not used when Foundry would only
narrate the result. Use Explanatory only when that narration adds a distinct,
testable learning outcome, and keep it optional rather than making it a second
authoritative path. For any state-changing agent action, still prefer ACS
`protect_tool()`/`run_tool()` over a bespoke local approval-token class. Reserve
a fully custom approval registry for the rare case where its binding semantics
genuinely cannot be expressed through ACS's `approval_resolver`. ACS's
`approval_resolver`, `Decision.Escalate`, and `EnforcementMode` are implemented
today in the published `agent-control-specification` package — do not describe
action-bound approval as "proposed" or "not yet implemented in AGT."

The core demo must expose one authoritative signal, decision surface, and
evidence source. Do not maintain a local shadow decision or evidence record
beside the supported service. Every file and dependency inside a control must
serve the documented core path, its validation, or a clearly labeled optional
path. Remove disconnected interfaces, assets, scaffolding, and example evidence
that the demo does not actually produce. For metadata- or configuration-driven
controls, cover missing, empty, invalid, and valid values and make any scope
precondition explicit.

An official capability or sample may be the center of a `DEMONSTRATE` demo.
Reject changes only when they merely reproduce an official quickstart without
adding a distinct governance scenario, composition, evidence pattern, or
learning outcome.

When this change sets a control's status to `Implemented` or `Validated`,
update the repository root `README.md` in the same change per the Root README
navigation rules in `.github/copilot-instructions.md`. A control change is not
complete until the root community demo table includes it. Do not add a separate
status overview to the root README.
