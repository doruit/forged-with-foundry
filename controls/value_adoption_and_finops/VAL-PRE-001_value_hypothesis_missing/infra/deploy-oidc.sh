#!/usr/bin/env bash
# Deploy the OPTIONAL GitHub Actions OIDC identity for VAL-PRE-001's real CI/CD gate demo.
# Separate from infra/deploy.sh (the core, always-required Azure Policy gate): this script
# provisions real identity infrastructure (a managed identity, a federated credential, and a
# role assignment) and is only needed if you want to run
# .github/workflows/val-pre-001-value-gate-demo.yml for real. Run infra/deploy.sh first.
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
require VALPRE001_GITHUB_REPOSITORY
VALPRE001_GITHUB_ENVIRONMENT="${VALPRE001_GITHUB_ENVIRONMENT:-production}"
VALPRE001_OIDC_IDENTITY_NAME="${VALPRE001_OIDC_IDENTITY_NAME:-id-val-pre-001-github-oidc}"

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

echo "Deploying the GitHub OIDC identity, federated credential, and role assignment..."
VALPRE001_OIDC_CLIENT_ID="$(az deployment group create \
  --name val-pre-001-oidc-identity \
  --resource-group "${AZURE_RESOURCE_GROUP}" \
  --mode Incremental \
  --template-file "${SCRIPT_DIR}/oidc-identity.bicep" \
  --parameters identityName="${VALPRE001_OIDC_IDENTITY_NAME}" \
               githubRepository="${VALPRE001_GITHUB_REPOSITORY}" \
               githubEnvironment="${VALPRE001_GITHUB_ENVIRONMENT}" \
  --query properties.outputs.identityClientId.value \
  --output tsv)"
update_env VALPRE001_OIDC_CLIENT_ID "${VALPRE001_OIDC_CLIENT_ID}"

TENANT_ID="$(az account show --query tenantId --output tsv)"

echo
echo "OIDC identity ready. In the GitHub repository's '${VALPRE001_GITHUB_ENVIRONMENT}' environment,"
echo "set these Actions variables (Settings > Environments > ${VALPRE001_GITHUB_ENVIRONMENT} > Variables):"
echo "  AZURE_CLIENT_ID       = ${VALPRE001_OIDC_CLIENT_ID}"
echo "  AZURE_TENANT_ID       = ${TENANT_ID}"
echo "  AZURE_SUBSCRIPTION_ID = ${AZURE_SUBSCRIPTION_ID}"
echo "  AZURE_RESOURCE_GROUP  = ${AZURE_RESOURCE_GROUP}"
echo
echo "Then trigger the 'VAL-PRE-001: value hypothesis gate demo (optional, manual)' workflow via workflow_dispatch."
