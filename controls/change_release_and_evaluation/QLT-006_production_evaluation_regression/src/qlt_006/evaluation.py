"""Run one Foundry Evaluations (GA) pass of the live agent version.

Deliberately a small copy of CHG-002's module rather than shared code (see
the category ARCHITECTURE.md): same dataset, same built-in evaluators, but
QLT-006 evaluates the *production* agent after release.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from .policy import Counts

EVALUATOR_INPUTS: dict[str, tuple[str, ...]] = {
    "builtin.similarity": ("query", "response", "ground_truth"),
    "builtin.task_adherence": ("query", "response"),
    "builtin.coherence": ("query", "response"),
    "builtin.fluency": ("response",),
    "builtin.relevance": ("query", "response"),
}
_MAPPING = {"query": "{{item.query}}", "response": "{{sample.output_text}}", "ground_truth": "{{item.ground_truth}}"}
TERMINAL = {"completed", "failed", "canceled"}
EVAL_PREFIX = "QLT-006 production regression"


def load_dataset(path: Path) -> list[dict[str, str]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_criteria(evaluators: list[str], judge: str) -> list[dict]:
    unknown = [e for e in evaluators if e not in EVALUATOR_INPUTS]
    if unknown:
        raise ValueError(f"unsupported evaluator(s): {unknown}")
    return [
        {
            "type": "azure_ai_evaluator",
            "name": e.split(".", 1)[1],
            "evaluator_name": e,
            "initialization_parameters": {"deployment_name": judge},
            "data_mapping": {f: _MAPPING[f] for f in EVALUATOR_INPUTS[e]},
        }
        for e in evaluators
    ]


def run_live(openai_client, *, agent: str, version: str, rows: list[dict], evaluators: list[str], judge: str, timeout_s: int = 1800) -> tuple[str, str, str]:
    eval_obj = openai_client.evals.create(
        name=f"{EVAL_PREFIX} {agent}",
        data_source_config={
            "type": "custom",
            "item_schema": {
                "type": "object",
                "properties": {"query": {"type": "string"}, "ground_truth": {"type": "string"}},
                "required": ["query", "ground_truth"],
            },
            "include_sample_schema": True,
        },
        testing_criteria=build_criteria(evaluators, judge),
    )
    run = openai_client.evals.runs.create(
        eval_id=eval_obj.id,
        name=f"production-{agent}-v{version}",
        data_source={
            "type": "azure_ai_target_completions",
            "source": {"type": "file_content", "content": [{"item": row} for row in rows]},
            "input_messages": {
                "type": "template",
                "template": [{"type": "message", "role": "user", "content": {"type": "input_text", "text": "{{item.query}}"}}],
            },
            "target": {"type": "azure_ai_agent", "name": agent, "version": str(version)},
        },
    )
    deadline = time.monotonic() + timeout_s
    status = run.status
    while status not in TERMINAL:
        if time.monotonic() > deadline:
            return eval_obj.id, run.id, "timed_out"
        time.sleep(10)
        status = openai_client.evals.runs.retrieve(run.id, eval_id=eval_obj.id).status
    return eval_obj.id, run.id, status


def list_items(openai_client, eval_id: str, run_id: str, expected: int | None, *, attempts: int = 6, wait_s: float = 10) -> list[dict]:
    """List output items; right after completion the list can still be short (observed live), so re-read briefly."""

    for attempt in range(attempts):
        items = [item.model_dump() for item in openai_client.evals.runs.output_items.list(run_id, eval_id=eval_id)]
        if expected is None or len(items) >= expected or attempt == attempts - 1:
            return items
        time.sleep(wait_s)
    return items


def counts_for(openai_client, eval_id: str, run_id: str, evaluators: list[str], expected: int | None = None) -> dict[str, Counts]:
    return count_results(list_items(openai_client, eval_id, run_id, expected), evaluators)


def count_results(items: list[dict], evaluators: list[str]) -> dict[str, Counts]:
    result = {}
    for evaluator in evaluators:
        name = evaluator.split(".", 1)[1]
        passed = failed = errored = 0
        for item in items:
            matches = [r for r in (item.get("results") or []) if r.get("name") == name]
            if len(matches) != 1 or matches[0].get("passed") is None:
                errored += 1
            elif matches[0]["passed"]:
                passed += 1
            else:
                failed += 1
        result[evaluator] = Counts(len(items), passed, failed, errored)
    return result
