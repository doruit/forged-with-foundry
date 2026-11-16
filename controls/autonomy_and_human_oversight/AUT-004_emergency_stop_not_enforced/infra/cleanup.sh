#!/usr/bin/env bash
# Remove only AUT-004's control-owned Azure and Entra resources.
set -euo pipefail
CONTROL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${CONTROL_DIR}/../../.." && pwd)"
exec "${PYTHON:-${REPO_ROOT}/.venv/bin/python}" "${CONTROL_DIR}/infra/cleanup.py"
