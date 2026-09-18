#!/usr/bin/env bash
# Remove only the OPTIONAL GitHub Actions OIDC identity owned by VAL-PRE-001.
# Does not touch the core Azure Policy definition/assignment (see infra/cleanup.sh).
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
VALPRE001_OIDC_IDENTITY_NAME="${VALPRE001_OIDC_IDENTITY_NAME:-id-val-pre-001-github-oidc}"

az account set --subscription "${AZURE_SUBSCRIPTION_ID}"

principal_id="$(az identity show \
  --name "${VALPRE001_OIDC_IDENTITY_NAME}" \
  --resource-group "${AZURE_RESOURCE_GROUP}" \
  --query principalId --output tsv 2>/dev/null || true)"

if [[ -n "${principal_id}" ]]; then
  az role assignment delete \
    --assignee "${principal_id}" \
    --resource-group "${AZURE_RESOURCE_GROUP}" 2>/dev/null || true
  az identity delete --name "${VALPRE001_OIDC_IDENTITY_NAME}" --resource-group "${AZURE_RESOURCE_GROUP}"
  echo "VAL-PRE-001 GitHub OIDC identity, federated credential, and role assignment deleted."
else
  echo "VAL-PRE-001 GitHub OIDC identity is already absent."
fi
