#!/usr/bin/env bash
# Deploy only the additional Azure resources owned by PRI-PRE-001.
# Two stages: (1) a subscription-scope policy definition, (2) the usual
# resource-group-scope resources (Table Storage + policy assignment + RBAC).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${CONTROL_DIR}/../../.." && pwd)"
SHARED_ENV="${REPO_ROOT}/infra/.env"
CONTROL_ENV="${CONTROL_DIR}/.env"
SUB_DEPLOYMENT_NAME="pri-pre-001-dpia-gate-policy"
RG_DEPLOYMENT_NAME="pri-pre-001-dpia-required-but-missing"

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
require PRIPRE001_STORAGE_ACCOUNT_NAME
AZURE_LOCATION="${AZURE_LOCATION:-swedencentral}"
export AZURE_LOCATION

if [[ -z "${DEPLOYER_PRINCIPAL_ID:-}" ]]; then
  DEPLOYER_PRINCIPAL_ID="$(az ad signed-in-user show --query id --output tsv)"
  export DEPLOYER_PRINCIPAL_ID
fi

output_value() {
  python3 -c 'import json,sys; print(json.load(sys.stdin)["'"$1"'"]["value"])' <<< "$2"
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

echo "Step 1/2: deploying the subscription-scope DPIA-gate policy definition"
echo "(requires Resource Policy Contributor or equivalent at subscription scope)..."

az deployment sub validate \
  --name "${SUB_DEPLOYMENT_NAME}-validate" \
  --location "${AZURE_LOCATION}" \
  --subscription "${AZURE_SUBSCRIPTION_ID}" \
  --template-file "${SCRIPT_DIR}/policy-definition.bicep" \
  --parameters "${SCRIPT_DIR}/policy-definition.bicepparam" \
  --output none

SUB_OUTPUTS="$(az deployment sub create \
  --name "${SUB_DEPLOYMENT_NAME}" \
  --location "${AZURE_LOCATION}" \
  --subscription "${AZURE_SUBSCRIPTION_ID}" \
  --template-file "${SCRIPT_DIR}/policy-definition.bicep" \
  --parameters "${SCRIPT_DIR}/policy-definition.bicepparam" \
  --query properties.outputs \
  --output json)"

PRIPRE001_POLICY_DEFINITION_ID="$(output_value policyDefinitionId "${SUB_OUTPUTS}")"
export PRIPRE001_POLICY_DEFINITION_ID
update_env PRIPRE001_POLICY_DEFINITION_ID "${PRIPRE001_POLICY_DEFINITION_ID}"

echo "Step 2/2: deploying resource-group-scope storage and policy assignment..."

az deployment group validate \
  --name "${RG_DEPLOYMENT_NAME}-validate" \
  --resource-group "${AZURE_RESOURCE_GROUP}" \
  --subscription "${AZURE_SUBSCRIPTION_ID}" \
  --template-file "${SCRIPT_DIR}/main.bicep" \
  --parameters "${SCRIPT_DIR}/main.bicepparam" \
  --output none

RG_OUTPUTS="$(az deployment group create \
  --name "${RG_DEPLOYMENT_NAME}" \
  --resource-group "${AZURE_RESOURCE_GROUP}" \
  --subscription "${AZURE_SUBSCRIPTION_ID}" \
  --mode Incremental \
  --template-file "${SCRIPT_DIR}/main.bicep" \
  --parameters "${SCRIPT_DIR}/main.bicepparam" \
  --query properties.outputs \
  --output json)"

update_env PRIPRE001_TABLE_ENDPOINT "$(output_value storageTableEndpoint "${RG_OUTPUTS}")"
update_env PRIPRE001_TABLE_NAME "$(output_value tableName "${RG_OUTPUTS}")"
update_env PRIPRE001_POLICY_ASSIGNMENT_ID "$(output_value policyAssignmentId "${RG_OUTPUTS}")"

echo "✅ PRI-PRE-001 resources deployed incrementally; updated ${CONTROL_ENV}."
