#!/usr/bin/env bash
# Remove only TOOL-003's control-owned agent, role assignment and project.
# Never touches the shared Foundry account, model deployment or resource group.
set -euo pipefail
CONTROL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${CONTROL_DIR}/../../.." && pwd)"
exec "${PYTHON:-${REPO_ROOT}/.venv/bin/python}" "${CONTROL_DIR}/infra/cleanup.py"
