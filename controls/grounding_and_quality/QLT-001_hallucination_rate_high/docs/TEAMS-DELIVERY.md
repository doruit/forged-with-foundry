---
title: QLT-001 Teams delivery configuration
description: How to configure the two Teams Workflows this control notifies; a cannot_evaluate delivery is confirmed live via the real API response, the quality_review_required fleet card is still pending a portal screenshot.
ms.date: 2026-09-25
---

## Status

A `cannot_evaluate` notification was sent for real from the fleet
redesign (2026-09-25) and accepted (`HTTP 202`) by
`QLT001_GOVERNANCE_TEAMS_WEBHOOK_URL` — confirmed via the real API response
(see README.md "Demo"), since Continuous Evaluation's own computed score has
not yet been observed to surface anywhere queryable (see
`docs/UPSTREAM-FEEDBACK.md`), so every live `evaluate` run to date correctly
produces this decision rather than a real breach. A portal screenshot of
this specific card has not yet been captured. A `quality_review_required`
card has not yet been sent or captured for the current fleet design — the
one previously captured (`../media/teams-quality-review-required.png`,
window rate 47.06%, threshold 5.0%, 2 critical items) is **historical,
pre-refactor evidence** from this control's original single-hosted-agent,
batch-evaluation design, kept per this repository's evidence conventions,
not a current capture: `card()`'s content shape has since changed to report
fleet facts (best/worst agent, per-agent breakdown) that this older
screenshot does not show. `VAL-001`'s
[docs/TEAMS-DELIVERY.md](../../../value_adoption_and_finops/VAL-001_kpi_underperformance/docs/TEAMS-DELIVERY.md)
in this repository shows a real, privacy-masked capture of the generic
Teams-webhook *configuration* screens (trigger setup, copy-URL step) for a
different control on the same mechanism — those setup screens were not
recaptured for QLT-001 since the underlying webhook UI is identical; only
this control's own card content needs its own capture, still pending for
both card types under the current fleet design.

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

As of this writing, expect `cannot_evaluate` and a card to AI Governance
Operations for every window, regardless of `--window` value — Continuous
Evaluation's own computed score has not yet been observed to surface
anywhere queryable (see `docs/UPSTREAM-FEEDBACK.md`), so `fetch_fleet_results()`
correctly fails closed rather than fabricate a `no_review_required` or
`quality_review_required` decision. Once that score-read path is confirmed,
expect `no_review_required` for `--window 1`/`--window 2` (Platform and
Regional Teams both healthy) and `quality_review_required` — a red attention
card naming the worst-performing agent — for `--window 3`/`--window 4` (the
Regional Team's KB drift) or any window at all (the Contractor Team is
degraded from window 1 onward by design; see README.md "Demo scope").

Capture only the card itself (macOS `Cmd+Shift+4` on the card region, or
`scripts/capture_teams_card.py`), masking tenant chrome, webhook URLs, and
any account identifiers, per
`.github/instructions/screenshot-capture-workflow.instructions.md`.

## References

- [Microsoft Teams connector and webhook authentication](https://learn.microsoft.com/en-us/connectors/teams/)
- [Create and manage Teams incoming webhooks with Workflows](https://learn.microsoft.com/en-us/microsoftteams/platform/webhooks-and-connectors/how-to/add-incoming-webhook)
