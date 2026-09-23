---
title: VAL-002 implementation and validation
description: What differs from VAL-001's deployment mechanics, plus screenshot capture and pending live-validation results.
ms.date: 2026-09-22
---

## Deployment configuration

Deployment mechanics are identical to VAL-001's — same Python/Agent Framework
Foundry/hosting/Monitor exporter versions (see [requirements.txt](../requirements.txt),
unchanged from VAL-001's pinned set), same `azd env set` variable shapes, same
Bicep deploy command shape. See
[VAL-001's deployment configuration](../../VAL-001_kpi_underperformance/docs/IMPLEMENTATION.md#deployment-configuration)
for the full walkthrough. This page documents only what is different for
VAL-002.

Differences:

- `azd env new val-002-benefits-realisation-gap-dev` (own environment).
- Monitor deployment name `val002-monitor`; outputs stored as
  `VAL002_WORKSPACE_ID` and `APPLICATIONINSIGHTS_CONNECTION_STRING`, which
  `azure.yaml` reads into `VAL002_APPLICATIONINSIGHTS_CONNECTION_STRING`.
- Teams webhooks: **reused from VAL-001**
  (`VAL001_TEAMS_WEBHOOK_URL` / `VAL001_GOVERNANCE_TEAMS_WEBHOOK_URL`), copied
  into this control's `azd env` rather than freshly created — see
  [ASSESSMENT.md](../ASSESSMENT.md) for why.

## Pooled 6-period KQL shape

Where VAL-001 queries and compares two periods independently, VAL-002 pools
every matching event across all six periods before comparing to the
threshold:

```kql
AppEvents
| where Name == "TicketTriaged"
| where tostring(Properties["run_id"]) == "<run-id>"
| extend Period=tostring(Properties["period"]), HumanHandled=tobool(Properties["human_handled"]), Verified=tobool(Properties["verified"])
| summarize TotalTickets=count(), DeflectedTickets=countif(HumanHandled == false), VerifiedTickets=countif(Verified == true) by Period
| union (
    print Period="Pooled"
    | extend TotalTickets=0, DeflectedTickets=0, VerifiedTickets=0
  )
| summarize PooledTotal=sum(TotalTickets), PooledDeflected=sum(DeflectedTickets) by 1
| extend PooledPercent=round(100.0 * PooledDeflected / PooledTotal, 2), ThresholdPercent=17.5
| extend Decision=iff(PooledPercent < ThresholdPercent, "reassess_required", "no_reassessment_required")
```

The evaluator (`evaluator.py`) performs this pooling in Python directly over
the queried per-event rows, not in KQL — the query above is illustrative of
the same arithmetic for manual inspection in the Azure Portal, not the code
path itself.

## Screenshot capture

New for this control: `scripts/capture_teams_card.py` at the repository
root (Playwright, one-time authoring tool — not a runtime dependency of the
demo).

Setup (author-only, not required to run the demo itself):

```bash
.venv/bin/pip install playwright
.venv/bin/python -m playwright install chromium
```

Usage:

```bash
.venv/bin/python scripts/capture_teams_card.py \
  --match "VAL-002" \
  --out controls/value_adoption_and_finops/VAL-002_benefits_realisation_gap/media/teams-cards-both-decisions.png
```

The script launches a **visible** Chromium window, navigates to
`https://teams.microsoft.com`, and prints a prompt asking you to sign in
interactively and open the Workflows chat — it never automates or stores
Entra credentials. Once you press Enter, it locates the message card(s)
matching `--match` and screenshots that specific element's bounding box
directly to `--out`, which crops out personal navigation and tenant chrome
by construction (only the element itself is captured) and avoids manual
`Cmd+Shift+4` selection. Follow
[the screenshot-capture-workflow instructions](../../../.github/instructions/screenshot-capture-workflow.instructions.md)
if capturing many screenshots in one session.

## Live validation

Steps 1-7 of the implementation path were run against real services on
2026-09-22. The hosted `helpdesk-tier1-triage` agent reuses this Foundry
project's shared identity slot: `azd ai agent show` reports
`instance_identity.principal_id` unchanged from VAL-001's own deployment
(`5eca04b3-9553-43be-b7bb-3ab151934752`) — the same managed identity backs
whichever control's code is currently deployed to that agent name, while
each control's own Application Insights/Log Analytics resources stay
separate (`appi-val002-*`/`log-val002-*`, distinct from VAL-001's, which
were already deleted). The `blueprint.principal_id` field `azd` also now
reports is a newer "Agent Identity Blueprint" principal type that Azure
RBAC's `Microsoft.Authorization/roleAssignments` rejects outright
(`PrincipalTypeNotSupported: ... agentIdentityBlueprintPrincipal cannot
validly be used in role assignments`) — a live platform discovery, not
present in VAL-001's original documentation. Use `instance_identity.principal_id`,
not `blueprint.principal_id`, for the RBAC step.

| Scenario | Observed pooled rate | Observed result |
|---|---|---|
| `milestone_shortfall` | 6/36 (16.67%), each of 6 periods at 1/6 (16.67%) | `reassess_required`; Teams posting accepted (HTTP 202) to the Business Owner route |
| `milestone_met` (evaluated against a missing contract path) | n/a | `cannot_evaluate`, reason `invalid_or_missing_input`; Teams posting accepted (HTTP 202) to the AI Governance Operations route |

Run IDs: `5c2cf1f4-ac03-4248-82a7-07f56e3c7f2d` (shortfall, `reassess_required`),
`49b3747a-90af-4470-956a-9f962d2339d7` (missing-contract, `cannot_evaluate`).
The full evidence records are the authoritative source; the table above
reproduces their key fields.

**Not yet completed:** the operator-checked Teams delivery receipt
(`demo.py record-delivery`, requiring the flow run ID and message ID from
the Power Automate run history) and the screenshot capture. Both HTTP `202`
responses above mean *accepted*, not *delivered* — per this control's own
evidence discipline (inherited from VAL-001), a webhook `202` is never
recorded as delivery on its own. `scripts/capture_teams_card.py`'s Chromium
download failed twice against `cdn.playwright.dev` (request timeout) in the
sandboxed authoring environment, consistent with a corporate network
policy blocking that CDN rather than a transient failure. Completing these
two steps requires an environment where either that download succeeds, or
a Playwright/Chromium install already exists, or the manual capture method
in VAL-001's [Teams delivery walkthrough](../../VAL-001_kpi_underperformance/docs/TEAMS-DELIVERY.md)
is used instead.

## Cleanup results

*Pending — completed after `infra/cleanup.py --confirm` is run and
independently verified, mirroring
[VAL-001's cleanup results](../../VAL-001_kpi_underperformance/docs/IMPLEMENTATION.md#cleanup-results).
This control's cleanup only ever targets its own `appi-val002-*` /
`log-val002-*` resources and its own hosted agent instance — it never
touches VAL-001's resources or the reused Teams Workflows.*
