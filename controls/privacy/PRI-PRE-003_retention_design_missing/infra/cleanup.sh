#!/usr/bin/env bash
# Remove only the Azure Policy assignment and definition owned by PRI-PRE-003.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${CONTROL_DIR}/../../.." && pwd)"
CONTROL_ENV="${CONTROL_DIR}/.env"

load_env() {
  local env_file="$1" line key value
  [[ -f "${env_file}" ]] || return 0
  while IFS= read -r line || [[ -n "${line}" ]]; do
    [[ -z "${line}" || "${line}" =~ ^[[:space:]]*# || "${line}" != *=* ]] && continue
    key="${line%%=*}"; key="${key//[[:space:]]/}"
    [[ "${key}" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    value="${line#*=}"; value="${value%$'\r'}"
    value="${value#\"}"; value="${value%\"}"
    value="${value#\'}"; value="${value%\'}"
    if [[ -n "${value}" || -z "${!key+x}" ]]; then export "${key}=${value}"; fi
  done < "${env_file}"
}

load_env "${REPO_ROOT}/infra/.env"
load_env "${CONTROL_ENV}"
: "${AZURE_SUBSCRIPTION_ID:?Set AZURE_SUBSCRIPTION_ID in .env}"
: "${AZURE_RESOURCE_GROUP:?Set AZURE_RESOURCE_GROUP in .env}"
: "${PRIPRE003_POLICY_DEFINITION_NAME:?Set PRIPRE003_POLICY_DEFINITION_NAME in .env}"
: "${PRIPRE003_POLICY_ASSIGNMENT_NAME:?Set PRIPRE003_POLICY_ASSIGNMENT_NAME in .env}"

az account set --subscription "${AZURE_SUBSCRIPTION_ID}"
scope="/subscriptions/${AZURE_SUBSCRIPTION_ID}/resourceGroups/${AZURE_RESOURCE_GROUP}"

if az policy assignment show --name "${PRIPRE003_POLICY_ASSIGNMENT_NAME}" --scope "${scope}" --output none 2>/dev/null; then
  az policy assignment delete --name "${PRIPRE003_POLICY_ASSIGNMENT_NAME}" --scope "${scope}"
  echo "PRI-PRE-003 policy assignment deleted."
else
  echo "PRI-PRE-003 policy assignment is already absent."
fi

if az policy definition show --name "${PRIPRE003_POLICY_DEFINITION_NAME}" --output none 2>/dev/null; then
  az policy definition delete --name "${PRIPRE003_POLICY_DEFINITION_NAME}"
  echo "PRI-PRE-003 policy definition deleted."
else
  echo "PRI-PRE-003 policy definition is already absent."
fi
