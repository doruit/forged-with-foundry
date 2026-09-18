#!/usr/bin/env bash
set -euo pipefail

CONTROL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash -n "${CONTROL_DIR}/demo.sh" "${CONTROL_DIR}/infra/deploy.sh" "${CONTROL_DIR}/infra/cleanup.sh" \
  "${CONTROL_DIR}/infra/deploy-oidc.sh" "${CONTROL_DIR}/infra/cleanup-oidc.sh"
az bicep build --file "${CONTROL_DIR}/infra/policy-definition.bicep" --stdout >/dev/null
az bicep build --file "${CONTROL_DIR}/infra/main.bicep" --stdout >/dev/null
az bicep build --file "${CONTROL_DIR}/infra/demo-target.bicep" --stdout >/dev/null
az bicep build --file "${CONTROL_DIR}/infra/oidc-identity.bicep" --stdout >/dev/null
python3 -m py_compile "${CONTROL_DIR}/scripts/validate_value_hypothesis.py"
python3 "${CONTROL_DIR}/scripts/validate_value_hypothesis.py" "${CONTROL_DIR}/fixtures/agent.yaml" >/dev/null
python3 "${CONTROL_DIR}/scripts/validate_value_hypothesis.py" "${CONTROL_DIR}/fixtures/agent.incomplete.yaml" >/dev/null
python3 "${CONTROL_DIR}/scripts/validate_value_hypothesis.py" "${CONTROL_DIR}/fixtures/agent.yaml" --enforce >/dev/null
if python3 "${CONTROL_DIR}/scripts/validate_value_hypothesis.py" "${CONTROL_DIR}/fixtures/agent.incomplete.yaml" --enforce >/dev/null 2>&1; then
  echo "error: --enforce should fail on an incomplete hypothesis" >&2
  exit 1
fi
echo "VAL-PRE-001 templates and scripts are valid."
