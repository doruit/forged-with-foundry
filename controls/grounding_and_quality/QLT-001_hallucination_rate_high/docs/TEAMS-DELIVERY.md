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

## Optional: also create an assigned backlog item

A Teams card notifies the Product Owner; it does not, on its own, make the
review trackable or assigned to someone accountable for closing it. The same
Product Owner flow (`QLT001_TEAMS_WEBHOOK_URL`) can gain that without any
change to `demo.py` -- Teams Workflows already received the full decision
payload for its **Post card** action; add one more action after it:

1. add a **GitHub** connector action, **Create an issue**;
2. set the target repository (a real backlog, not necessarily this one);
3. build the title and body from the same trigger payload the card action
   already uses -- correlation ID, decision reason, window number, and the
   worst-performing agent are all in it (see `demo.py`'s `card()` for the
   exact fields);
4. set **Assignees** to the Product Owner's GitHub username and add a label
   such as `qlt-001` or `governance-review`.

Only add this to the `quality_review_required` flow. `cannot_evaluate`
routes to AI Governance Operations for a measurement/infrastructure fix, not
a product backlog item.

This closes the loop from "notified" to "someone is accountable for a
tracked next step" without this control taking any remediating action
itself -- see [docs/REMEDIATION-GUIDANCE.md](REMEDIATION-GUIDANCE.md) for
what that Product Owner should actually investigate, and its "Why this
control does not automate remediation" section for why creating a tracked
task is as far as automation goes here. Unlike Teams delivery, this control
does not verify or record that the issue was actually created -- `demo.py`'s
evidence and the `notify`/`record-delivery` states describe Teams delivery
only; treat a GitHub backlog item as an unverified convenience the flow
provides, not a control guarantee.

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

A fleet-aware `quality_review_required` card was captured and
operator-verified on 2026-09-27 (window 4, correlation
`cba18329-c890-42bc-b22a-e20952d6cc3c`): HTTP 202 accepted, then confirmed
`delivered` by matching the Teams Workflow run ID and message ID against the
posted card. No screenshot is retained here (see the control README's
[Security and privacy](../README.md#security-and-privacy)); the correlation
ID lets the underlying local, git-ignored evidence be cross-checked. An
earlier live run also received HTTP 202 for a `cannot_evaluate`
notification.
