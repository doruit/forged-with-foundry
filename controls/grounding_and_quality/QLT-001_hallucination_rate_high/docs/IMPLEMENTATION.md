---
title: QLT-001 implementation notes
description: How batch evaluation, the Eval definition, and the deterministic policy fit together, why Continuous Evaluation was not used, and what is still unverified pending a full live pass.
ms.date: 2026-09-23
---

## Why batch evaluation, not Continuous Evaluation

`ASSESSMENT.md` records the full history of this decision. In short:

1. The first draft proposed a bespoke script calling `GroundednessEvaluator`
   directly against synthetic transcripts. Foundry Observability's
   **Continuous Evaluation** (GA, March 2026) does exactly this already, in
   production, against sampled live traffic — reusing it instead of
   re-implementing an evaluator call keeps this control to one authoritative
   signal path.
2. Reading the installed `azure-ai-projects` package source (not blog
   summaries) confirmed the whole configuration chain is genuinely
   SDK-callable: `client.evaluation_rules.create_or_update()` creates an
   `EvaluationRule` with a `ContinuousEvaluationRuleAction`, and the
   underlying Eval definition is created through the OpenAI-compatible Evals
   API exposed via `client.get_openai_client().evals`. This requires
   `AIProjectClient(..., allow_preview=True)` — a disclosed preview
   dependency, not silently used.
3. **A real deployment then showed Continuous Evaluation rejects hosted
   agents outright:** `client.evaluation_rules.create_or_update()` against a
   real, freshly-deployed `kind: hosted` agent (`it-helpdesk-kb-assistant`)
   returned `400 UserError: The agent '...' is of kind 'hosted', which is
   not supported for evaluation rules. Hosted and external agents are not
   supported.` Reproduced identically on `azure-ai-projects` 2.3.0 (this
   project's pinned version) and 2.7.0 (newest available at the time),
   ruling out an SDK-version explanation. See `docs/UPSTREAM-FEEDBACK.md` for
   the full writeup, including Microsoft's own public statement that
   hosted-agent support is coming.

That is why this control's core path uses **batch evaluation**
(`azd ai agent eval`) instead: the same underlying groundedness evaluator
technology, confirmed working end to end against the same real hosted agent,
triggered explicitly per measurement window rather than sampling
automatically.

## Core path: batch evaluation via `azd ai agent eval`

1. Deploy the hosted agent (`azd up`, see README.md "Deploy").
2. Create the Eval definition once (real command, confirmed working):

   ```zsh
   azd ai agent eval generate --agent it-helpdesk-kb-assistant \
     --evaluator builtin.groundedness \
     --gen-instruction "<description of the agent, its topics, and its windows>" \
     --max-samples 15 --name qlt-001-groundedness --no-prompt
   ```

   This writes `eval.yaml` and a generated dataset under `datasets/`, and
   registers a real Eval definition in the Foundry project (confirmed
   real id shape: `eval_<32 hex chars>`).
3. `demo.py evaluate --window-id <id>` triggers a fresh run
   (`azd ai agent eval run --config eval.yaml --output json`) and reads
   real per-item results via
   `openai_client.evals.runs.output_items.list(eval_id, run_id)`.

**Confirmed real result-item schema** (2026-09-23, against a real run):

```json
{
  "name": "qlt-001-groundedness",
  "passed": true,
  "score": 0.7413793103448276,
  "threshold": 0.5,
  "reason": "..."
}
```

This first run's `qlt-001-groundedness` criterion used a 0.0–1.0
weighted-rubric score with an explicit pass/fail at a 0.5 threshold. A
**second** live run, this time also configuring the `builtin.groundedness`
criterion in the same `eval.yaml`, returned real scores of roughly 1.0–4.0
for that differently-named criterion — a materially different numeric range
for the same `results[].score`/`threshold` fields, confirming the scale is
evaluator-specific and cannot be hardcoded. `evaluator.py` was corrected
twice to match: first to assume a fixed 0.0–1.0 range, then to compare each
item's `score` against its own `threshold` (`score <= threshold * 0.5` for
the critical-item override) instead of any absolute floor, so the same rule
is correct regardless of which evaluator scale is configured. Its tests
cover both observed scales.

## Known gap: the dataset does not literally replay `demo.py run`'s conversations

Foundry's evals API drives its **own fresh invocations** of the target
agent from the dataset when a run executes (`data_source.target.type:
azure_ai_agent`); it does not score already-recorded conversations. This
means `demo.py run --window N` (three real, manually-invoked conversations,
kept as production-traffic evidence in the window manifest) and
`demo.py evaluate --window-id` (a fresh batch-eval run against the same
agent, using its own generated dataset) are two separate, real activities
against the same real agent — not one pipeline correlated by conversation
id. The generated dataset's scenarios are LLM-authored from the
`--gen-instruction` text describing the agent and its windows abstractly,
not hand-scripted to be exactly the three literal topic queries `demo.py
run` sends.

Closing this gap for exact 1:1 determinism requires authoring a literal,
per-window dataset file (`azd ai agent eval generate --dataset <file>` /
`azd ai agent eval update --dataset-only`) instead of relying on generation.
This was not completed — the exact literal-dataset row schema (beyond the
richer, generation-produced `id`/`description` rows this control's own
`datasets/qlt-001-groundedness/qlt-001-groundedness_dg.jsonl` shows) was not
confirmed live. Documented in README.md "Further exploration" rather than
guessed further.

## Optional, still-preview: wiring Continuous Evaluation once it supports hosted agents

Kept here as a documented starting point for when
`docs/UPSTREAM-FEEDBACK.md`'s status question comes back positive:

```python
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    EvaluationRule, ContinuousEvaluationRuleAction, EvaluationRuleFilter,
)

client = AIProjectClient(endpoint, credential, allow_preview=True)
client.evaluation_rules.create_or_update(
    "qlt-001-continuous-groundedness",
    EvaluationRule(
        display_name="QLT-001 continuous groundedness",
        action=ContinuousEvaluationRuleAction(eval_id="<eval-id>", sampling_rate=100),
        filter=EvaluationRuleFilter(agent_name="it-helpdesk-kb-assistant"),
        event_type="responseCompleted",
        enabled=True,
    ),
)
```

Confirmed real requirements from a live attempt: `display_name` is required
(the service rejects its absence with a clear `400`), and the call currently
fails for any `kind: hosted` or external agent regardless of the rest of the
payload.

## `extract_run_id()`: confirmed real output shape

`azd ai agent invoke` prints human-readable labeled text, not JSON. Real,
confirmed fields include `Trace ID:` (a 32-hex-character OTel trace id) and
`Response:` (an OpenAI Responses-API id, `caresp_...`). `extract_run_id()`
parses the `Trace ID:` line and returns `None` (fail closed) if it is
absent, rather than guessing a wrong field — this was corrected from an
earlier, unverified assumption that the output was JSON.
