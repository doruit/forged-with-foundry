#!/usr/bin/env bash
set -euo pipefail

CONTROL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${CONTROL_DIR}/../../.." && pwd)"
VALIDATOR="${REPO_ROOT}/scripts/validate_governance_contract.py"
COMPLETE_CONTRACT="${CONTROL_DIR}/fixtures/complete-workload/.fwf/agents/customer-support-agent/governance.yaml"
INCOMPLETE_CONTRACT="${CONTROL_DIR}/fixtures/incomplete-workload/.fwf/agents/customer-support-agent/governance.yaml"

bash -n "${CONTROL_DIR}/demo.sh" "${CONTROL_DIR}/infra/deploy.sh" "${CONTROL_DIR}/infra/cleanup.sh"
az bicep build --file "${CONTROL_DIR}/infra/policy-definition.bicep" --stdout >/dev/null
az bicep build --file "${CONTROL_DIR}/infra/main.bicep" --stdout >/dev/null
az bicep build --file "${CONTROL_DIR}/infra/demo-target.bicep" --stdout >/dev/null

# Schema-valid layer (docs/governance-contract.md), added alongside this
# control's pre-existing Azure Policy demo above, which evaluates
# deployment-request tags directly and is unaffected by this check.
python3 -m py_compile "${VALIDATOR}"
python3 "${VALIDATOR}" --contract "${COMPLETE_CONTRACT}" --control PRI-PRE-003 >/dev/null
python3 "${VALIDATOR}" --contract "${INCOMPLETE_CONTRACT}" --control PRI-PRE-003 >/dev/null
python3 "${VALIDATOR}" --contract "${COMPLETE_CONTRACT}" --control PRI-PRE-003 --enforce >/dev/null
set +e
python3 "${VALIDATOR}" --contract "${INCOMPLETE_CONTRACT}" --control PRI-PRE-003 --enforce >/dev/null 2>&1
exit_code=$?
set -e
if [[ "${exit_code}" -eq 0 ]]; then
  echo "error: --enforce should fail on a missing retention design" >&2
  exit 1
fi
if [[ "${exit_code}" -ne 1 ]]; then
  echo "error: expected exit code 1 (denied), got ${exit_code} (execution failure) -- a crashed validator is not a passing negative test" >&2
  exit 1
fi

echo "PRI-PRE-003 templates, scripts, and governance contracts are valid. Boundary-case"
echo "coverage lives in tests/test_pri_pre_003_governance_contract.py and"
echo "tests/test_governance_contract_consistency.py at the repository root."
