#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Deploy the Microsoft Foundry infrastructure defined in infra/main.bicep.
#
# Reads configuration from `infra/.env`, ensures the target
# resource group exists, runs the Bicep deployment via the Azure CLI, and writes
# the resulting project endpoint and deployment names back into `.env`.
#
# Prerequisites:
#   - `az login` already completed
#   - Azure CLI installed (the Bicep CLI is auto-installed by `az` when needed)
#
# Usage:
#   ./infra/deploy.sh
# -----------------------------------------------------------------------------
set -euo pipefail

# Resolve repo paths regardless of where the script is invoked from.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_PATH="${SCRIPT_DIR}/.env"
BICEP_TEMPLATE="${SCRIPT_DIR}/main.bicep"
BICEP_PARAMS="${SCRIPT_DIR}/main.bicepparam"

DEPLOYMENT_NAME="foundry-governance-demo"

die() { echo "Error: $*" >&2; exit 1; }

# --- Load .env --------------------------------------------------------------
[[ -f "${ENV_PATH}" ]] || die "No .env found at ${ENV_PATH}. Copy infra/.env.example to infra/.env and fill it in."

# Parse .env safely (values may contain spaces and need no quoting in the file).
# We read line by line, skip comments/blank lines, and export KEY=VALUE verbatim.
while IFS= read -r line || [[ -n "${line}" ]]; do
  [[ -z "${line}" || "${line}" =~ ^[[:space:]]*# ]] && continue
  [[ "${line}" != *=* ]] && continue
  key="${line%%=*}"
  value="${line#*=}"
  # Trim surrounding whitespace on the key; strip optional surrounding quotes.
  key="$(echo "${key}" | xargs)"
  value="${value%$'\r'}"
  value="${value#\"}"; value="${value%\"}"
  value="${value#\'}"; value="${value%\'}"
  export "${key}=${value}"
done < "${ENV_PATH}"

require() {
  local var="$1"
  [[ -n "${!var:-}" ]] || die "Missing required environment variable '${var}'. Set it in ${ENV_PATH}."
}

require AZURE_SUBSCRIPTION_ID
require AZURE_RESOURCE_GROUP
require FOUNDRY_ACCOUNT_NAME
AZURE_LOCATION="${AZURE_LOCATION:-swedencentral}"

# --- Ensure resource group --------------------------------------------------
echo ""
echo "\$ az group create --name ${AZURE_RESOURCE_GROUP} --location ${AZURE_LOCATION}"
echo ""
az group create \
  --name "${AZURE_RESOURCE_GROUP}" \
  --location "${AZURE_LOCATION}" \
  --subscription "${AZURE_SUBSCRIPTION_ID}" \
  --output none

# --- Deploy the Bicep template ----------------------------------------------
# The .bicepparam file reads the remaining values from the exported environment.
echo ""
echo "\$ az deployment group validate --name ${DEPLOYMENT_NAME}-validate ..."
echo ""
az deployment group validate \
  --name "${DEPLOYMENT_NAME}-validate" \
  --resource-group "${AZURE_RESOURCE_GROUP}" \
  --subscription "${AZURE_SUBSCRIPTION_ID}" \
  --template-file "${BICEP_TEMPLATE}" \
  --parameters "${BICEP_PARAMS}" \
  --output none

echo ""
echo "\$ az deployment group create --name ${DEPLOYMENT_NAME} ..."
echo ""
OUTPUTS="$(az deployment group create \
  --name "${DEPLOYMENT_NAME}" \
  --resource-group "${AZURE_RESOURCE_GROUP}" \
  --subscription "${AZURE_SUBSCRIPTION_ID}" \
  --mode Incremental \
  --template-file "${BICEP_TEMPLATE}" \
  --parameters "${BICEP_PARAMS}" \
  --query properties.outputs \
  --output json)"

# Extract an output value by name using the Azure CLI's bundled Python (avoids a
# hard dependency on `jq`).
az_jq() {
  python3 -c 'import sys, json; print(json.load(sys.stdin)["'"$1"'"]["value"])' <<< "${OUTPUTS}"
}

PROJECT_ENDPOINT="$(az_jq projectEndpoint)"
CHAT_DEPLOYMENT="$(az_jq chatDeploymentName)"
MINI_DEPLOYMENT="$(az_jq miniDeploymentName)"
EMBEDDING_DEPLOYMENT="$(az_jq embeddingDeploymentName)"
ACCOUNT_ENDPOINT="$(az_jq accountEndpoint)"

# --- Write results back into .env -------------------------------------------
update_env() {
  local key="$1" value="$2"
  if grep -qE "^${key}=" "${ENV_PATH}"; then
    # Replace the existing line (portable in-place edit).
    local tmp
    tmp="$(mktemp)"
    sed "s|^${key}=.*|${key}=${value}|" "${ENV_PATH}" > "${tmp}"
    mv "${tmp}" "${ENV_PATH}"
  else
    printf '%s=%s\n' "${key}" "${value}" >> "${ENV_PATH}"
  fi
}

update_env AZURE_AI_PROJECT_ENDPOINT "${PROJECT_ENDPOINT}"
update_env AZURE_OPENAI_DEPLOYMENT "${MINI_DEPLOYMENT}"
update_env AZURE_OPENAI_CHAT_DEPLOYMENT "${CHAT_DEPLOYMENT}"
update_env AZURE_OPENAI_EMBEDDING_DEPLOYMENT "${EMBEDDING_DEPLOYMENT}"
update_env AZURE_CONTENT_SAFETY_ENDPOINT "${ACCOUNT_ENDPOINT}"

echo ""
echo "Updated ${ENV_PATH}"
echo ""
echo "✅ Deployment complete."
echo "   Project endpoint : ${PROJECT_ENDPOINT}"
echo "   Chat model       : ${CHAT_DEPLOYMENT}"
echo "   Mini model       : ${MINI_DEPLOYMENT}"
echo "   Embedding model  : ${EMBEDDING_DEPLOYMENT}"
