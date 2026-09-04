#!/usr/bin/env bash
# Deploy only the Azure Policy definition and assignment owned by PRI-PRE-002.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${CONTROL_DIR}/../../.." && pwd)"
CONTROL_ENV="${CONTROL_DIR}/.env"

die() { echo "Error: $*" >&2; exit 1; }

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

[[ -f "${CONTROL_ENV}" ]] || die "Copy ${CONTROL_DIR}/.env.example to ${CONTROL_ENV} first."
load_env "${REPO_ROOT}/infra/.env"
load_env "${CONTROL_ENV}"

require() { [[ -n "${!1:-}" ]] || die "Missing required environment variable '$1'."; }
require AZURE_SUBSCRIPTION_ID
require AZURE_RESOURCE_GROUP
require PRIPRE002_POLICY_DEFINITION_NAME
require PRIPRE002_POLICY_ASSIGNMENT_NAME
AZURE_LOCATION="${AZURE_LOCATION:-swedencentral}"

update_env() {
  local key="$1" value="$2" temp_file
  if grep -qE "^${key}=" "${CONTROL_ENV}"; then
    temp_file="$(mktemp)"
    sed "s|^${key}=.*|${key}=${value}|" "${CONTROL_ENV}" > "${temp_file}"
    mv "${temp_file}" "${CONTROL_ENV}"
  else
    printf '%s=%s\n' "${key}" "${value}" >> "${CONTROL_ENV}"
  fi
}

az account set --subscription "${AZURE_SUBSCRIPTION_ID}"
az group show --name "${AZURE_RESOURCE_GROUP}" --output none

echo "1/2 Deploying the subscription-scope policy definition..."
PRIPRE002_POLICY_DEFINITION_ID="$(az deployment sub create \
  --name pri-pre-002-policy \
  --location "${AZURE_LOCATION}" \
  --template-file "${SCRIPT_DIR}/policy-definition.bicep" \
  --parameters policyDefinitionName="${PRIPRE002_POLICY_DEFINITION_NAME}" \
  --query properties.outputs.policyDefinitionId.value \
  --output tsv)"
export PRIPRE002_POLICY_DEFINITION_ID
update_env PRIPRE002_POLICY_DEFINITION_ID "${PRIPRE002_POLICY_DEFINITION_ID}"

echo "2/2 Assigning the policy to the selected resource group..."
PRIPRE002_POLICY_ASSIGNMENT_ID="$(az deployment group create \
  --name pri-pre-002-assignment \
  --resource-group "${AZURE_RESOURCE_GROUP}" \
  --mode Incremental \
  --template-file "${SCRIPT_DIR}/main.bicep" \
  --parameters policyDefinitionId="${PRIPRE002_POLICY_DEFINITION_ID}" \
               policyAssignmentName="${PRIPRE002_POLICY_ASSIGNMENT_NAME}" \
  --query properties.outputs.policyAssignmentId.value \
  --output tsv)"
update_env PRIPRE002_POLICY_ASSIGNMENT_ID "${PRIPRE002_POLICY_ASSIGNMENT_ID}"

echo "PRI-PRE-002 policy deployed. Azure compliance evaluation is asynchronous."
