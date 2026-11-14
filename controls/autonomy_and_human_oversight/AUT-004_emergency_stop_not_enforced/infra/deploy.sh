#!/usr/bin/env bash
# Deploy AUT-004 into the shared resource group from infra/.env.
set -euo pipefail
CONTROL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${CONTROL_DIR}/../../.." && pwd)"
exec "${PYTHON:-${REPO_ROOT}/.venv/bin/python}" "${CONTROL_DIR}/infra/deploy.py" "$@"
