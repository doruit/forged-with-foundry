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
require AZURE_LANGUAGE_ACCOUNT_NAME
require PII_STORAGE_ACCOUNT_NAME
AZURE_LOCATION="${AZURE_LOCATION:-swedencentral}"

# Grant the signed-in principal only the data-plane roles needed by the local
# demo. This object ID is passed to Bicep and is not a secret.
if [[ -z "${DEPLOYER_PRINCIPAL_ID:-}" ]]; then
  DEPLOYER_PRINCIPAL_ID="$(az ad signed-in-user show --query id --output tsv)"
  export DEPLOYER_PRINCIPAL_ID
fi

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
LANGUAGE_ENDPOINT="$(az_jq languageEndpoint)"
PII_STORAGE_BLOB_ENDPOINT="$(az_jq piiStorageBlobEndpoint)"
PII_SOURCE_CONTAINER="$(az_jq piiSourceContainerName)"
PII_TARGET_CONTAINER="$(az_jq piiTargetContainerName)"

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
update_env AZURE_LANGUAGE_ENDPOINT "${LANGUAGE_ENDPOINT}"
update_env PII_STORAGE_BLOB_ENDPOINT "${PII_STORAGE_BLOB_ENDPOINT}"
update_env PII_SOURCE_CONTAINER "${PII_SOURCE_CONTAINER}"
update_env PII_TARGET_CONTAINER "${PII_TARGET_CONTAINER}"

echo ""
echo "Updated ${ENV_PATH}"
echo ""
echo "✅ Deployment complete."
echo "   Project endpoint : ${PROJECT_ENDPOINT}"
echo "   Chat model       : ${CHAT_DEPLOYMENT}"
echo "   Mini model       : ${MINI_DEPLOYMENT}"
echo "   Embedding model  : ${EMBEDDING_DEPLOYMENT}"
echo "   Language endpoint: ${LANGUAGE_ENDPOINT}"
echo "   PII blob endpoint: ${PII_STORAGE_BLOB_ENDPOINT}"
