#!/usr/bin/env python3
"""Boundary-case tests for validate_value_hypothesis.py's structural check.

Run directly (python3 scripts/test_validate_value_hypothesis.py) or via
validate.sh; no pytest dependency is introduced for this small control.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import validate_value_hypothesis as vvh  # noqa: E402

_COMPLETE = """
value_hypothesis:
  metric: tier1_ticket_deflection_rate
  target:
    value: 35
    direction: increase
  baseline:
    status: net_new
  owner: it-service-desk-manager@contoso.example
  business_case_id: BIZ-CASE-HELPDESK-001
"""


def _assess(yaml_text: str) -> dict[str, object]:
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as handle:
        handle.write(yaml_text)
        path = Path(handle.name)
    try:
        return vvh.assess(path)
    finally:
        path.unlink()


def _with_override(field_path: str, replacement: str) -> str:
    """Replace one line in _COMPLETE identified by its leading field name."""
    lines = _COMPLETE.splitlines()
    out = []
    for line in lines:
        if line.strip().startswith(f"{field_path}:"):
            out.append(replacement)
        else:
            out.append(line)
    return "\n".join(out)


class TestStructuralValidation(unittest.TestCase):
    def test_complete_hypothesis_is_complete(self) -> None:
        result = _assess(_COMPLETE)
        self.assertEqual(result["valueHypothesisStatus"], "complete")
        self.assertEqual(result["businessCaseId"], "BIZ-CASE-HELPDESK-001")
        self.assertEqual(result["reasons"], [])

    def test_missing_metric(self) -> None:
        yaml_text = _COMPLETE.replace("  metric: tier1_ticket_deflection_rate\n", "")
        result = _assess(yaml_text)
        self.assertEqual(result["valueHypothesisStatus"], "incomplete")
        self.assertIn("metric is missing or blank", result["reasons"])

    def test_blank_metric(self) -> None:
        yaml_text = _with_override("metric", "  metric: '   '")
        result = _assess(yaml_text)
        self.assertIn("metric is missing or blank", result["reasons"])

    def test_non_numeric_target(self) -> None:
        yaml_text = _with_override("value", "    value: banana")
        result = _assess(yaml_text)
        self.assertEqual(result["valueHypothesisStatus"], "incomplete")
        self.assertIn("target.value must be numeric", result["reasons"])

    def test_missing_target(self) -> None:
        yaml_text = _COMPLETE.replace("    value: 35\n", "")
        result = _assess(yaml_text)
        self.assertIn("target.value is missing", result["reasons"])

    def test_invalid_direction(self) -> None:
        yaml_text = _with_override("direction", "    direction: sideways")
        result = _assess(yaml_text)
        self.assertIn("target.direction must be 'increase' or 'decrease'", result["reasons"])

    def test_invalid_baseline_status(self) -> None:
        yaml_text = _with_override("status", "    status: guessed")
        result = _assess(yaml_text)
        self.assertIn("baseline.status must be 'measured' or 'net_new'", result["reasons"])

    def test_blank_owner(self) -> None:
        yaml_text = _with_override("owner", "  owner: '  '")
        result = _assess(yaml_text)
        self.assertIn("owner is missing or blank", result["reasons"])

    def test_missing_business_case_id(self) -> None:
        yaml_text = _COMPLETE.replace(
            "  business_case_id: BIZ-CASE-HELPDESK-001\n", ""
        )
        result = _assess(yaml_text)
        self.assertIn("business_case_id is missing or blank", result["reasons"])
        self.assertEqual(result["businessCaseId"], "")


class TestEnforceExitCode(unittest.TestCase):
    def _run_enforce(self, yaml_text: str) -> int:
        script = Path(__file__).parent / "validate_value_hypothesis.py"
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as handle:
            handle.write(yaml_text)
            path = Path(handle.name)
        try:
            proc = subprocess.run(
                [sys.executable, str(script), str(path), "--enforce"],
                capture_output=True,
                check=False,
            )
            return proc.returncode
        finally:
            path.unlink()

    def test_enforce_exits_zero_when_complete(self) -> None:
        self.assertEqual(self._run_enforce(_COMPLETE), 0)

    def test_enforce_exits_nonzero_when_incomplete(self) -> None:
        yaml_text = _with_override("owner", "  owner: ''")
        self.assertNotEqual(self._run_enforce(yaml_text), 0)


if __name__ == "__main__":
    unittest.main()
