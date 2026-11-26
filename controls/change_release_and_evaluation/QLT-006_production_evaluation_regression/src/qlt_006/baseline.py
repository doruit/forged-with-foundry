"""Load the CHG-002 release baseline record and verify it against Foundry.

QLT-006 never computes its own baseline. It trusts the record only after
re-reading the Foundry Evaluations run the record cites and recomputing the
pass rates from that run's results.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

REQUIRED = ("agent", "production", "model", "dataset", "evaluators", "passRates", "evaluationRunId")


@dataclass(frozen=True)
class Baseline:
    record: dict
    sha256: str
    dataset_path: Path

    @property
    def rates(self) -> dict[str, float]:
        return {name: float(rate) for name, rate in self.record["passRates"].items()}


def load(path: Path) -> tuple[Baseline | None, str]:
    try:
        raw = path.read_bytes()
        record = json.loads(raw)
    except (OSError, ValueError):
        return None, "qlt_006_baseline_unavailable"
    if not isinstance(record, dict) or any(key not in record for key in REQUIRED):
        return None, "qlt_006_baseline_invalid"
    if set(record["passRates"]) != set(record["evaluators"]):
        return None, "qlt_006_baseline_invalid"
    dataset = (path.parent.parent / record["dataset"]["path"]).resolve()
    if not dataset.is_file() or hashlib.sha256(dataset.read_bytes()).hexdigest() != record["dataset"]["sha256"]:
        return None, "qlt_006_dataset_mismatch"
    return Baseline(record, hashlib.sha256(raw).hexdigest(), dataset), ""


def matches_foundry(baseline: Baseline, recomputed: dict[str, float]) -> bool:
    """True when the record's pass rates equal the ones recomputed from the cited Foundry run."""

    return set(recomputed) == set(baseline.rates) and all(
        abs(recomputed[name] - baseline.rates[name]) < 0.0001 for name in recomputed
    )
