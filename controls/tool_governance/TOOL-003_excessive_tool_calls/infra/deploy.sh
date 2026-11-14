#!/usr/bin/env bash
# Deploy TOOL-003's control-owned Foundry project and register its prompt agent.
# Prerequisite: the shared root infra/ deployment and its infra/.env.
set -euo pipefail

CONTROL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${CONTROL_DIR}/../../.." && pwd)"
ENV_PATH="${REPO_ROOT}/infra/.env"
PYTHON="${PYTHON:-${REPO_ROOT}/.venv/bin/python}"

die() { echo "Error: $*" >&2; exit 1; }
[[ -f "${ENV_PATH}" ]] || die "Missing ${ENV_PATH}. Deploy the shared infra/ first."

env_value() { grep -E "^$1=" "${ENV_PATH}" | tail -1 | cut -d= -f2- | tr -d '"'"'"; }
SUBSCRIPTION_ID="$(env_value AZURE_SUBSCRIPTION_ID)"
RESOURCE_GROUP="$(env_value AZURE_RESOURCE_GROUP)"
ACCOUNT="$(env_value FOUNDRY_ACCOUNT_NAME)"
MODEL="$(env_value AZURE_OPENAI_CHAT_DEPLOYMENT)"
for name in SUBSCRIPTION_ID RESOURCE_GROUP ACCOUNT MODEL; do
  [[ -n "${!name}" ]] || die "Missing ${name} in ${ENV_PATH}"
done

CURRENT="$(az account show --query id -o tsv)"
[[ "${CURRENT}" == "${SUBSCRIPTION_ID}" ]] || die "Azure CLI subscription does not match infra/.env; run: az account set --subscription <id>"

az cognitiveservices account deployment show -g "${RESOURCE_GROUP}" -n "${ACCOUNT}" \
  --deployment-name "${MODEL}" --query name -o tsv >/dev/null \
  || die "Shared model deployment '${MODEL}' not found on ${ACCOUNT}"

PRINCIPAL_ID="$(az ad signed-in-user show --query id -o tsv)"

echo "Deploying TOOL-003 project into ${RESOURCE_GROUP} (account ${ACCOUNT})..."
OUTPUTS="$(az deployment group create \
  --resource-group "${RESOURCE_GROUP}" \
  --name tool-003 \
  --template-file "${CONTROL_DIR}/infra/main.bicep" \
  --parameters foundryAccountName="${ACCOUNT}" setupPrincipalId="${PRINCIPAL_ID}" \
  --query properties.outputs -o json)"

output() { "${PYTHON}" -c "import json,sys; print(json.load(sys.stdin)['$1']['value'])" <<<"${OUTPUTS}"; }

"${PYTHON}" "${CONTROL_DIR}/infra/agent_registry.py" register \
  --endpoint "$(output projectEndpoint)" \
  --model "${MODEL}" \
  --project-id "$(output projectId)" \
  --role-assignment-id "$(output roleAssignmentId)"

echo "TOOL-003 deployed. Next: cd ${CONTROL_DIR} && ${PYTHON} -m src.tool_003 run --scenario healthy"
