---
name: linkedin-post-writer
description: "Generates rich, engagement-optimized LinkedIn posts announcing new AI governance control demos, weekly/monthly repo updates, and category-completion milestones for Forged with Foundry"
license: MIT
user-invocable: true
metadata:
  authors: "Douwe van de Ruit"
  spec_version: "1.0"
  last_updated: "2026-09-04"
---

# LinkedIn Post Writer Skill

## Overview

Drafts LinkedIn posts for the Forged with Foundry repository: the initial
launch announcement, recurring weekly/monthly update posts when one or more
controls ship, and category-completion posts when every demo in a category
group (e.g., Privacy) is implemented. Optimizes for LinkedIn's actual
engagement mechanics rather than generic marketing copy.

Generated post drafts are local-only. Store them under
`content/linkedin/` (gitignored) in this repository, never in a folder that
gets committed or pushed.

## Post Types

#### 1. Launch announcement (one-time)

Introduces the repository, the problem it solves, and why it's worth
following. Written once, before the weekly cadence starts.

#### 2. Weekly/monthly update post (recurring)

Announces one or more newly implemented controls since the last post. Named
after the control(s), e.g. "PRI-004 just shipped."

#### 3. Category-completion post (milestone)

Posted when every demo in one category group (e.g., all Privacy controls)
reaches `Implemented` or `Validated`. Recaps what the category taught as a
whole, not just the last individual control.

## Structure Template

Every post follows this shape, in this order:

1. **Hook** (first 1-2 lines): a concrete scenario or question, not a company
   announcement. This is the only part visible before "see more" truncates
   the post, so it must work standalone.
2. **Body** (3-6 short paragraphs, one idea per paragraph, generous line
   breaks): the real-life scenario, what the control/demo does, and the one
   thing that makes it different from "just prompting a model to behave."
3. **Call to action**: end with a genuine, answerable question that invites a
   comment (not "thoughts?" or "let me know!"). Ask something the reader can
   answer from their own experience.
4. **Hashtags**: 3-5, mixing one broad tag with narrower, topic-specific
   tags. Do not exceed 5; LinkedIn's own guidance treats more as a spam
   signal.
5. **Link placement note**: never include the repository URL in the post
   body. Add a closing line such as "🔗 Link to the repo in the first
   comment." and post the actual link as the first comment immediately after
   publishing.

## Engagement Best Practices

* No hyperlink in the post body. LinkedIn's algorithm demonstrably reduces
  reach on posts with an outbound link because it keeps traffic off-platform;
  posting the link as the first comment avoids that penalty while still
  making it available immediately.
* Ask one specific, answerable question as the CTA. A yes/no or opinion
  question that relates to the reader's own work performs better than a
  generic "what do you think?".
* Use short paragraphs and line breaks. LinkedIn's feed renders dense text
  blocks poorly on mobile; 1-3 sentences per paragraph reads far better.
* Lead with a scenario or tension, not with the product name. The first line
  is a hook shown before truncation, so it must earn the "see more" click on
  its own.
* Reuse a real screenshot from the demo (e.g. a control's own
  `media/*.png` Chainlit console screenshot) rather than a generic stock
  graphic. Authentic product screenshots outperform generic AI-governance
  stock imagery for this audience. Crop to the interesting part (the
  decision, the block, the evidence) rather than posting the full window.
* Tag people or organizations only when the tag is genuinely accurate (for
  example, do not tag Microsoft accounts unless there is a real, specific
  connection to that post's content). Fabricated or unearned tags read as
  spam and hurt credibility.
* Post on a weekday morning in the target audience's primary time zone;
  weekday late-morning posts generally outperform weekend or late-evening
  posts for a professional B2B audience.
* Reply to every comment within the first hour if possible. Early
  engagement velocity is what LinkedIn's algorithm uses to decide whether to
  keep showing the post to more people.

## Hashtag Bank

Rotate a broad tag with 2-4 narrower ones relevant to the specific control or
category being announced. Do not use all of these on every post.

* Broad: `#AIGovernance`, `#ResponsibleAI`, `#MicrosoftFoundry`
* Privacy category: `#GDPR`, `#DataPrivacy`, `#PrivacyByDesign`
* Security category: `#AISecurity`, `#PromptInjection`, `#ZeroTrust`
* Compliance category: `#AICompliance`, `#RiskManagement`
* General AI/agent: `#AIAgents`, `#AgentGovernance`, `#Azure`

## File Naming and Location

Store every drafted post as its own file under `content/linkedin/` (this
folder is gitignored and never pushed):

```text
content/linkedin/
├── 2026-09-04-launch-announcement.md
├── 2026-09-11-pri-001-update.md
├── 2026-mm-dd-<control-id-or-milestone>.md
└── images/
    └── <slug>-cover.png
```

Each post file uses this frontmatter:

```yaml
---
date: 2026-09-04
type: launch | update | category-completion
controls: [PRI-001, PRI-002]   # empty for launch
status: draft | scheduled | published
image: images/<slug>-cover.png
---
```

## Quick Start

To draft a new post, describe: which control(s) or milestone triggered it,
the post type (launch, update, category-completion), and any specific
screenshot or angle to lead with. Apply the Structure Template and Engagement
Best Practices above, save the result under `content/linkedin/` using the
naming convention, and leave `status: draft` until the user confirms it's
ready to post.

## Troubleshooting

| Symptom | Check |
|---|---|
| Post reads like a press release | Rewrite the hook as a scenario or question; move any "we are excited to announce" phrasing out entirely. |
| CTA gets no comments | Replace a generic question ("thoughts?") with one the reader can answer from personal experience. |
| Draft file accidentally staged in git | Confirm `content/linkedin/` is listed in `.gitignore`; run `git status` to verify it shows as ignored. |

## Contributing

* Keep the Structure Template and Engagement Best Practices sections
  generic and portable; control-specific content belongs in the individual
  drafted post files, not in this skill.
* Update the Hashtag Bank as new category groups get their first
  implemented control.
