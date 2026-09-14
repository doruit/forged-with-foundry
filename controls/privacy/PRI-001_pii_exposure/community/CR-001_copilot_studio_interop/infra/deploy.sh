#!/usr/bin/env bash
# Deploy CR-001's App Service (hosts the MCP server) and its code package.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXTENSION_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
CONTROL_DIR="$(cd "${EXTENSION_DIR}/../.." && pwd)"
REPO_ROOT="$(cd "${CONTROL_DIR}/../../.." && pwd)"
SHARED_ENV="${REPO_ROOT}/infra/.env"
CONTROL_ENV="${CONTROL_DIR}/.env"
DEPLOYMENT_NAME="cr-001-copilot-studio-interop"

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
require AZURE_LANGUAGE_ACCOUNT_NAME
require PII_STORAGE_ACCOUNT_NAME

export CR001_APP_SERVICE_NAME="${CR001_APP_SERVICE_NAME:-fwf-cr001-mcp}"
export CR001_APP_SERVICE_PLAN_NAME="${CR001_APP_SERVICE_PLAN_NAME:-fwf-cr001-plan}"

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

APP_SERVICE_HOSTNAME="$(echo "${OUTPUTS}" | python3 -c "import sys, json; print(json.load(sys.stdin)['appServiceHostName']['value'])")"
APP_SERVICE_NAME="$(echo "${OUTPUTS}" | python3 -c "import sys, json; print(json.load(sys.stdin)['appServiceName']['value'])")"

echo "App Service provisioned: https://${APP_SERVICE_HOSTNAME}"

# --- Package and deploy the code (core PRI-001 package + CR-001 extension) --
BUILD_DIR="$(mktemp -d)"
trap 'rm -rf "${BUILD_DIR}"' EXIT

mkdir -p "${BUILD_DIR}/src"
cp -R "${CONTROL_DIR}/src/pri_001" "${BUILD_DIR}/src/pri_001"
cp -R "${EXTENSION_DIR}/src/cr001_interop" "${BUILD_DIR}/src/cr001_interop"
cat "${CONTROL_DIR}/requirements.txt" "${EXTENSION_DIR}/requirements.txt" > "${BUILD_DIR}/requirements.txt"

ZIP_PATH="${BUILD_DIR}.zip"
(cd "${BUILD_DIR}" && zip -qr "${ZIP_PATH}" .)

az webapp deploy \
  --resource-group "${AZURE_RESOURCE_GROUP}" \
  --subscription "${AZURE_SUBSCRIPTION_ID}" \
  --name "${APP_SERVICE_NAME}" \
  --type zip \
  --src-path "${ZIP_PATH}"

rm -f "${ZIP_PATH}"

echo "✅ CR-001 App Service deployed: https://${APP_SERVICE_HOSTNAME}/mcp"
