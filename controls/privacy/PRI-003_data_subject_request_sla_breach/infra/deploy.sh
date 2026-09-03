#!/usr/bin/env bash
# Deploy only the additional Azure resources owned by PRI-003.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${CONTROL_DIR}/../../.." && pwd)"
SHARED_ENV="${REPO_ROOT}/infra/.env"
CONTROL_ENV="${CONTROL_DIR}/.env"
DEPLOYMENT_NAME="pri-003-dsr-sla-breach"

die() { echo "Error: $*" >&2; exit 1; }

load_env() {
  local path="$1" line key value
  [[ -f "${path}" ]] || die "No environment file found at ${path}."
  while IFS= read -r line || [[ -n "${line}" ]]; do
    [[ -z "${line}" || "${line}" =~ ^[[:space:]]*# || "${line}" != *=* ]] && continue
    key="$(echo "${line%%=*}" | xargs)"
    value="${line#*=}"; value="${value%$'\r'}"
    value="${value#\"}"; value="${value%\"}"
    value="${value#\'}"; value="${value%\'}"
    export "${key}=${value}"
  done < "${path}"
}

load_env "${SHARED_ENV}"
load_env "${CONTROL_ENV}"

require() { [[ -n "${!1:-}" ]] || die "Missing required environment variable '$1'."; }
require AZURE_SUBSCRIPTION_ID
require AZURE_RESOURCE_GROUP
require PRI003_STORAGE_ACCOUNT_NAME
AZURE_LOCATION="${AZURE_LOCATION:-swedencentral}"
export AZURE_LOCATION

if [[ -z "${DEPLOYER_PRINCIPAL_ID:-}" ]]; then
  DEPLOYER_PRINCIPAL_ID="$(az ad signed-in-user show --query id --output tsv)"
  export DEPLOYER_PRINCIPAL_ID
fi

az deployment group validate \
  --name "${DEPLOYMENT_NAME}-validate" \
  --resource-group "${AZURE_RESOURCE_GROUP}" \
  --subscription "${AZURE_SUBSCRIPTION_ID}" \
  --template-file "${SCRIPT_DIR}/main.bicep" \
  --parameters "${SCRIPT_DIR}/main.bicepparam" \
  --output none

OUTPUTS="$(az deployment group create \
  --name "${DEPLOYMENT_NAME}" \
  --resource-group "${AZURE_RESOURCE_GROUP}" \
  --subscription "${AZURE_SUBSCRIPTION_ID}" \
  --mode Incremental \
  --template-file "${SCRIPT_DIR}/main.bicep" \
  --parameters "${SCRIPT_DIR}/main.bicepparam" \
  --query properties.outputs \
  --output json)"

output_value() {
  python3 -c 'import json,sys; print(json.load(sys.stdin)["'"$1"'"]["value"])' <<< "${OUTPUTS}"
}

update_env() {
  local key="$1" value="$2" tmp
  if grep -qE "^${key}=" "${CONTROL_ENV}"; then
    tmp="$(mktemp)"
    sed "s|^${key}=.*|${key}=${value}|" "${CONTROL_ENV}" > "${tmp}"
    mv "${tmp}" "${CONTROL_ENV}"
  else
    printf '%s=%s\n' "${key}" "${value}" >> "${CONTROL_ENV}"
  fi
}

update_env PRI003_TABLE_ENDPOINT "$(output_value storageTableEndpoint)"
update_env PRI003_TABLE_NAME "$(output_value tableName)"

echo "✅ PRI-003 resources deployed incrementally; updated ${CONTROL_ENV}."
