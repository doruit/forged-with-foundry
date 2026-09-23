---
title: QLT-001 Teams delivery configuration
description: How to configure the two Teams Workflows this control notifies; the quality_review_required card has been captured, the cannot_evaluate card is still pending.
ms.date: 2026-09-23
---

## Status

A `quality_review_required` card has been sent from a real deployment of
this control and captured: see
[../media/teams-quality-review-required.png](../media/teams-quality-review-required.png),
also embedded in `README.md`'s "Demo" section, showing the real window rate
(47.06%), threshold (5.0%), and critical-item count (2) delivered to the
Product Owner's channel via `QLT001_TEAMS_WEBHOOK_URL` (`HTTP 202`). For
this validation run, `QLT001_TEAMS_WEBHOOK_URL` was set to `VAL-001`'s
already-configured webhook URL rather than creating a new one, since the
webhook mechanism itself (not its destination) is what needed proving; a
real deployment should still follow "Configure the webhook" below to point
at its own Product Owner channel. A `cannot_evaluate` card to
`QLT001_GOVERNANCE_TEAMS_WEBHOOK_URL` has not yet been sent or captured for
this control specifically. `VAL-001`'s
[docs/TEAMS-DELIVERY.md](../../../value_adoption_and_finops/VAL-001_kpi_underperformance/docs/TEAMS-DELIVERY.md)
in this repository shows a real, privacy-masked capture of the generic
Teams-webhook *configuration* screens (trigger setup, copy-URL step) for a
different control on the same mechanism — those setup screens were not
recaptured for QLT-001 since the underlying webhook UI is identical; only
this control's own card content needed its own capture.

## Recipient routing

Configure two tenant-authenticated Teams Workflows:

* `QLT001_TEAMS_WEBHOOK_URL` posts `quality_review_required` cards to the
  Product Owner's channel.
* `QLT001_GOVERNANCE_TEAMS_WEBHOOK_URL` posts `cannot_evaluate` cards to the
  AI Governance Operations channel.

The second route is intentionally separate: a missing or incomplete
groundedness measurement must not look like a healthy window, and a Product
Owner should not be asked to review an outcome the control could not
establish.

## Configure the webhook

Follow [Create and manage Teams incoming webhooks with Workflows](https://learn.microsoft.com/en-us/microsoftteams/platform/webhooks-and-connectors/how-to/add-incoming-webhook)
to create a **When a Teams webhook request is received** trigger followed by
a **Post card in a chat or channel** action, restricted to **Any user in my
tenant** (never anonymous). Enter the generated URL using hidden input so it
is never echoed or committed, following the same pattern as
[VAL-001's equivalent step](../../../value_adoption_and_finops/VAL-001_kpi_underperformance/docs/TEAMS-DELIVERY.md#4-enter-it-locally-without-displaying-it):

```zsh
set +x
read -rs 'QLT001_TEAMS_WEBHOOK_URL?Paste the Teams HTTP URL (hidden): '
printf '\n'
azd env set QLT001_TEAMS_WEBHOOK_URL "$QLT001_TEAMS_WEBHOOK_URL" --cwd controls/grounding_and_quality/QLT-001_hallucination_rate_high
unset QLT001_TEAMS_WEBHOOK_URL
printf '' | pbcopy
```

Repeat for `QLT001_GOVERNANCE_TEAMS_WEBHOOK_URL` against a separate flow.

## Reproduce and capture the cards

```zsh
cd controls/grounding_and_quality/QLT-001_hallucination_rate_high
WINDOW_OUTPUT=$(../../../.venv/bin/python demo.py run --window 1)
WINDOW_ID=$(printf '%s\n' "$WINDOW_OUTPUT" | sed -n 's/^Window: \([0-9a-f-]*\).*/\1/p')
../../../.venv/bin/python demo.py evaluate --window-id "$WINDOW_ID"
../../../.venv/bin/python demo.py notify --window-id "$WINDOW_ID"
```

Expect `no_review_required` and no card for window 1-2 (healthy knowledge
base). Repeat with `--window 3` and `--window 4` to reach the degraded
knowledge base; expect `quality_review_required` and a red attention card in
the Product Owner's Workflows chat once the aggregated rate breaches the
control's 5% threshold or a critical hallucination is confirmed.

Capture only the card itself (macOS `Cmd+Shift+4` on the card region, or
`scripts/capture_teams_card.py`), masking tenant chrome, webhook URLs, and
any account identifiers, per
`.github/instructions/screenshot-capture-workflow.instructions.md`.

## References

- [Microsoft Teams connector and webhook authentication](https://learn.microsoft.com/en-us/connectors/teams/)
- [Create and manage Teams incoming webhooks with Workflows](https://learn.microsoft.com/en-us/microsoftteams/platform/webhooks-and-connectors/how-to/add-incoming-webhook)
