#!/usr/bin/env python3
"""Configuration assessment for VAL-PRE-001: is agent.yaml's value_hypothesis
structurally measurable?

This is a structural check only: it answers "is there a named metric, a
numeric target with a direction, a baseline status, a named owner, and a
business case id", never "is this a good or realistic hypothesis". It never
establishes business approval or owner sign-off, so its result is reported as
`complete`/`incomplete`, not `approved`/`denied`.

By default this script does not enforce anything; Azure Policy remains the
sole *deployment-time* decision engine (see infra/policy-definition.bicep),
and it only ever sees the two reduced tags below, never this file. It
reduces the full `value_hypothesis` structure declared in an `agent.yaml`
fixture down to the two stable tags that policy evaluates:
`valueHypothesisStatus` and `businessCaseId`. Pass `--enforce` to make this
script itself fail (non-zero exit) when the hypothesis is not structurally
complete; this is the mode a real CI check step should use (see
.github/workflows/val-pre-001-value-gate-demo.yml), so the CI check can stop
a pipeline before any Azure call is made. Future Pre-Live controls in this
category (VAL-PRE-002/003/004) are expected to extend this same script
rather than add new tags; see ../../ARCHITECTURE.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

_VALID_DIRECTIONS = {"increase", "decrease"}
_VALID_BASELINE_STATUSES = {"measured", "net_new"}


def _is_blank(value: object) -> bool:
    """True when value is missing, not a string, or only whitespace."""
    return not isinstance(value, str) or not value.strip()


def _is_numeric(value: object) -> bool:
    """True when value is a real number, rejecting bools and non-numeric strings."""
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        try:
            float(value.strip())
        except ValueError:
            return False
        return bool(value.strip())
    return False


def assess(agent_yaml_path: Path) -> dict[str, object]:
    """Return the tag values and reasons for the given agent.yaml fixture."""
    data = yaml.safe_load(agent_yaml_path.read_text(encoding="utf-8")) or {}
    hypothesis = data.get("value_hypothesis") or {}
    target = hypothesis.get("target") or {}
    baseline = hypothesis.get("baseline") or {}

    reasons = []
    if _is_blank(hypothesis.get("metric")):
        reasons.append("metric is missing or blank")
    target_value = target.get("value")
    if target_value in (None, ""):
        reasons.append("target.value is missing")
    elif not _is_numeric(target_value):
        reasons.append("target.value must be numeric")
    if target.get("direction") not in _VALID_DIRECTIONS:
        reasons.append("target.direction must be 'increase' or 'decrease'")
    if baseline.get("status") not in _VALID_BASELINE_STATUSES:
        reasons.append("baseline.status must be 'measured' or 'net_new'")
    if _is_blank(hypothesis.get("owner")):
        reasons.append("owner is missing or blank")

    business_case_id_raw = hypothesis.get("business_case_id")
    if _is_blank(business_case_id_raw):
        reasons.append("business_case_id is missing or blank")
    business_case_id = business_case_id_raw.strip() if isinstance(business_case_id_raw, str) else ""

    status = "complete" if not reasons else "incomplete"
    return {
        "valueHypothesisStatus": status,
        "businessCaseId": business_case_id,
        "reasons": reasons,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("agent_yaml", type=Path, help="Path to the agent.yaml fixture to assess.")
    parser.add_argument(
        "--shell",
        action="store_true",
        help="Print KEY=VALUE lines instead of JSON, for sourcing in shell scripts.",
    )
    parser.add_argument(
        "--enforce",
        action="store_true",
        help=(
            "Exit non-zero when valueHypothesisStatus is not 'complete'. Intended for a real "
            "CI check step (see .github/workflows/val-pre-001-value-gate-demo.yml); "
            "the default mode always exits 0 because it is a local configuration assessment, "
            "not an enforcement point."
        ),
    )
    args = parser.parse_args()

    if not args.agent_yaml.is_file():
        print(f"error: {args.agent_yaml} not found", file=sys.stderr)
        return 2

    result = assess(args.agent_yaml)
    if args.shell:
        print(f"VALUE_HYPOTHESIS_STATUS={result['valueHypothesisStatus']}")
        print(f"BUSINESS_CASE_ID={result['businessCaseId']}")
    else:
        print(json.dumps(result))

    if args.enforce and result["valueHypothesisStatus"] != "complete":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
