"""Run Foundry Evaluations (GA) against two versions of the same agent.

One Eval object defines the evaluators; one run per agent version sends the
same dataset to that version (``azure_ai_target_completions``) and Foundry's
built-in evaluators score every response. Both runs stay visible in the
Foundry portal under Evaluations. This module only starts runs and counts
the per-evaluator results; it never decides.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from .policy import EvaluatorCounts

# Inputs each supported built-in evaluator reads. Anything else is rejected
# before a run starts, so a typo in the contract fails closed.
EVALUATOR_INPUTS: dict[str, tuple[str, ...]] = {
    "builtin.similarity": ("query", "response", "ground_truth"),
    "builtin.task_adherence": ("query", "response"),
    "builtin.coherence": ("query", "response"),
    "builtin.fluency": ("response",),
    "builtin.relevance": ("query", "response"),
}
_MAPPING = {
    "query": "{{item.query}}",
    "response": "{{sample.output_text}}",
    "ground_truth": "{{item.ground_truth}}",
}
TERMINAL = {"completed", "failed", "canceled"}


@dataclass(frozen=True)
class RunResult:
    run_id: str
    status: str
    counts: dict[str, EvaluatorCounts]


def load_dataset(path: Path) -> list[dict[str, str]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for row in rows:
        if not isinstance(row.get("query"), str) or not isinstance(row.get("ground_truth"), str):
            raise ValueError("every dataset row needs string 'query' and 'ground_truth'")
    return rows


def criterion_name(evaluator: str) -> str:
    return evaluator.split(".", 1)[1]


def build_criteria(evaluators: tuple[str, ...], judge_deployment: str) -> list[dict]:
    unknown = [name for name in evaluators if name not in EVALUATOR_INPUTS]
    if unknown:
        raise ValueError(f"unsupported evaluator(s): {unknown}")
    return [
        {
            "type": "azure_ai_evaluator",
            "name": criterion_name(name),
            "evaluator_name": name,
            "initialization_parameters": {"deployment_name": judge_deployment},
            "data_mapping": {field: _MAPPING[field] for field in EVALUATOR_INPUTS[name]},
        }
        for name in evaluators
    ]


def create_eval(openai_client, name: str, evaluators: tuple[str, ...], judge_deployment: str) -> str:
    eval_obj = openai_client.evals.create(
        name=name,
        data_source_config={
            "type": "custom",
            "item_schema": {
                "type": "object",
                "properties": {"query": {"type": "string"}, "ground_truth": {"type": "string"}},
                "required": ["query", "ground_truth"],
            },
            "include_sample_schema": True,
        },
        testing_criteria=build_criteria(evaluators, judge_deployment),
    )
    return eval_obj.id


def start_run(openai_client, eval_id: str, agent_name: str, agent_version: str, rows: list[dict], label: str) -> str:
    run = openai_client.evals.runs.create(
        eval_id=eval_id,
        name=f"{label}-{agent_name}-v{agent_version}",
        data_source={
            "type": "azure_ai_target_completions",
            "source": {"type": "file_content", "content": [{"item": row} for row in rows]},
            "input_messages": {
                "type": "template",
                "template": [
                    {"type": "message", "role": "user", "content": {"type": "input_text", "text": "{{item.query}}"}}
                ],
            },
            "target": {"type": "azure_ai_agent", "name": agent_name, "version": str(agent_version)},
        },
    )
    return run.id


def wait_for_run(openai_client, eval_id: str, run_id: str, *, timeout_s: int = 1800, poll_s: int = 10) -> str:
    deadline = time.monotonic() + timeout_s
    while True:
        run = openai_client.evals.runs.retrieve(run_id, eval_id=eval_id)
        if run.status in TERMINAL:
            return run.status
        if time.monotonic() > deadline:
            return "timed_out"
        time.sleep(poll_s)


def count_results(items: list[dict], evaluators: tuple[str, ...]) -> dict[str, EvaluatorCounts]:
    """Count passed/failed/errored per evaluator; a missing or null result is errored."""

    counts: dict[str, EvaluatorCounts] = {}
    for evaluator in evaluators:
        name = criterion_name(evaluator)
        passed = failed = errored = 0
        for item in items:
            matches = [r for r in (item.get("results") or []) if r.get("name") == name]
            if len(matches) != 1 or matches[0].get("passed") is None:
                errored += 1
            elif matches[0]["passed"]:
                passed += 1
            else:
                failed += 1
        counts[evaluator] = EvaluatorCounts(total=len(items), passed=passed, failed=failed, errored=errored)
    return counts


def collect(openai_client, eval_id: str, run_id: str, status: str, evaluators: tuple[str, ...]) -> RunResult:
    if status != "completed":
        empty = {e: EvaluatorCounts(total=0, passed=0, failed=0, errored=0) for e in evaluators}
        return RunResult(run_id, status, empty)
    items = [item.model_dump() for item in openai_client.evals.runs.output_items.list(run_id, eval_id=eval_id)]
    return RunResult(run_id, status, count_results(items, evaluators))
