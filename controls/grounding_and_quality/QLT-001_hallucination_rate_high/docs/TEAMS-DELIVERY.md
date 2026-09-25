---
title: QLT-001 Teams delivery configuration
description: Configure separate authenticated routes for quality review and measurement failure.
ms.date: 2026-09-25
---

# Teams delivery

QLT-001 uses two tenant-authenticated Teams Workflows:

| Decision | Setting | Recipient |
|---|---|---|
| `quality_review_required` | `QLT001_TEAMS_WEBHOOK_URL` | Product Owner |
| `cannot_evaluate` | `QLT001_GOVERNANCE_TEAMS_WEBHOOK_URL` | AI Governance Operations |

A missing measurement is not a quality result and must not be routed as if the
Product Owner can review an established breach.

## Configure each workflow

In Teams Workflows:

1. create **When a Teams webhook request is received**;
2. restrict it to **Any user in my tenant**;
3. add **Post card in a chat or channel**;
4. select the intended review channel;
5. save and copy the generated URL.

Store each URL without echoing it:

```bash
cd controls/grounding_and_quality/QLT-001_hallucination_rate_high
set +x
read -rs -p 'Product Owner workflow URL: ' QLT001_TEAMS_WEBHOOK_URL
printf '\n'
azd env set QLT001_TEAMS_WEBHOOK_URL "$QLT001_TEAMS_WEBHOOK_URL"
unset QLT001_TEAMS_WEBHOOK_URL

read -rs -p 'Governance Operations workflow URL: ' QLT001_GOVERNANCE_TEAMS_WEBHOOK_URL
printf '\n'
azd env set QLT001_GOVERNANCE_TEAMS_WEBHOOK_URL "$QLT001_GOVERNANCE_TEAMS_WEBHOOK_URL"
unset QLT001_GOVERNANCE_TEAMS_WEBHOOK_URL
```

Never print, commit, or capture either URL.

## Send the current decision

```bash
../../../.venv/bin/python demo.py notify --window-id "<window-id>"
```

The sender accepts only HTTPS endpoints under the expected Power Platform or
Logic Apps domains and obtains a tenant token through Azure CLI credentials.

## Interpret the receipt

| State | Meaning |
|---|---|
| `attempted` | State persisted before the external call |
| `accepted` | Endpoint returned 2xx; delivery is not yet independently verified |
| `rejected` | Endpoint returned a non-2xx status |
| `delivery_unknown` | Network outcome was ambiguous; the tool does not resend blindly |
| `delivered` | Operator recorded matching workflow and Teams receipt IDs |

Only an explicit 401 or 403 rejection can be retried with
`--retry-rejected`. Timeouts and ambiguous attempts are not automatically
resent because that could duplicate a governance notification.

## Evidence status

A prior live run received HTTP 202 for a `cannot_evaluate` notification. No
current-architecture screenshot is retained, and a fleet-aware
`quality_review_required` card has not yet been captured. Those gaps are
why QLT-001 remains Implemented rather than Validated.
