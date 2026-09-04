#!/usr/bin/env bash
set -euo pipefail

CONTROL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash -n "${CONTROL_DIR}/demo.sh" "${CONTROL_DIR}/infra/deploy.sh" "${CONTROL_DIR}/infra/cleanup.sh"
az bicep build --file "${CONTROL_DIR}/infra/policy-definition.bicep" --stdout >/dev/null
az bicep build --file "${CONTROL_DIR}/infra/main.bicep" --stdout >/dev/null
az bicep build --file "${CONTROL_DIR}/demo-target.bicep" --stdout >/dev/null
echo "PRI-PRE-001 templates and scripts are valid."
