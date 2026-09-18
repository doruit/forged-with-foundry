#!/usr/bin/env bash
set -euo pipefail

CONTROL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${CONTROL_DIR}/../../.." && pwd)"
VALIDATOR="${REPO_ROOT}/scripts/validate_governance_contract.py"
COMPLETE_CONTRACT="${CONTROL_DIR}/fixtures/complete-workload/.fwf/agents/helpdesk-tier1-triage/governance.yaml"
INCOMPLETE_CONTRACT="${CONTROL_DIR}/fixtures/incomplete-workload/.fwf/agents/helpdesk-tier1-triage/governance.yaml"

bash -n "${CONTROL_DIR}/demo.sh" "${CONTROL_DIR}/infra/deploy.sh" "${CONTROL_DIR}/infra/cleanup.sh"
az bicep build --file "${CONTROL_DIR}/infra/policy-definition.bicep" --stdout >/dev/null
az bicep build --file "${CONTROL_DIR}/infra/main.bicep" --stdout >/dev/null
az bicep build --file "${CONTROL_DIR}/infra/demo-target.bicep" --stdout >/dev/null
python3 -m py_compile "${VALIDATOR}"
python3 "${VALIDATOR}" --contract "${COMPLETE_CONTRACT}" --control VAL-PRE-002 >/dev/null
python3 "${VALIDATOR}" --contract "${INCOMPLETE_CONTRACT}" --control VAL-PRE-002 >/dev/null
python3 "${VALIDATOR}" --contract "${COMPLETE_CONTRACT}" --control VAL-PRE-002 --enforce >/dev/null
if python3 "${VALIDATOR}" --contract "${INCOMPLETE_CONTRACT}" --control VAL-PRE-002 --enforce >/dev/null 2>&1; then
  echo "error: --enforce should fail on a workload with no recorded KPI baseline" >&2
  exit 1
fi
echo "VAL-PRE-002 templates and governance contracts are valid. Boundary-case coverage lives in"
echo "tests/test_val_pre_002_governance_contract.py and tests/test_governance_contract_consistency.py"
echo "at the repository root (run: .venv/bin/python -m pytest -q)."
