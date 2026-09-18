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

# Determine the exact OIDC subject GitHub will present, without deliberately
# failing azure/login first to read it from an AADSTS700213 error message.
# GitHub's subject can be the legacy "repo:owner/repo:environment:name" form
# or the current immutable "repo:owner@ownerId/repo@repoId:environment:name"
# form; an explicit override always wins.
if [[ -n "${VALPRE001_GITHUB_OIDC_SUBJECT:-}" ]]; then
  OIDC_SUBJECT="${VALPRE001_GITHUB_OIDC_SUBJECT}"
  echo "Using the explicit VALPRE001_GITHUB_OIDC_SUBJECT override."
else
  command -v gh >/dev/null 2>&1 || die "gh (GitHub CLI) is required to derive the current OIDC subject automatically. Install it, run 'gh auth login', or set VALPRE001_GITHUB_OIDC_SUBJECT explicitly (see docs/OIDC-DEMO.md)."
  gh auth status >/dev/null 2>&1 || die "gh is installed but not authenticated. Run 'gh auth login', or set VALPRE001_GITHUB_OIDC_SUBJECT explicitly (see docs/OIDC-DEMO.md)."

  repo_json="$(gh api "repos/${VALPRE001_GITHUB_REPOSITORY}" --jq '{owner: .owner.login, ownerId: .owner.id, repo: .name, repoId: .id}' 2>&1)" \
    || die "Could not read repository '${VALPRE001_GITHUB_REPOSITORY}' via gh api: ${repo_json}"
  owner="$(echo "${repo_json}" | python3 -c 'import json, sys; print(json.load(sys.stdin)["owner"])')"
  owner_id="$(echo "${repo_json}" | python3 -c 'import json, sys; print(json.load(sys.stdin)["ownerId"])')"
  repo_name="$(echo "${repo_json}" | python3 -c 'import json, sys; print(json.load(sys.stdin)["repo"])')"
  repo_id="$(echo "${repo_json}" | python3 -c 'import json, sys; print(json.load(sys.stdin)["repoId"])')"
  [[ -n "${owner}" && -n "${owner_id}" && -n "${repo_name}" && -n "${repo_id}" ]] \
    || die "gh api returned an incomplete repository record for '${VALPRE001_GITHUB_REPOSITORY}'."

  OIDC_SUBJECT="repo:${owner}@${owner_id}/${repo_name}@${repo_id}:environment:${VALPRE001_GITHUB_ENVIRONMENT}"
  echo "Derived the current immutable GitHub OIDC subject via 'gh api'."
fi
echo "OIDC subject this identity will trust: ${OIDC_SUBJECT}"

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
               subject="${OIDC_SUBJECT}" \
  --query properties.outputs.identityClientId.value \
  --output tsv)"
update_env VALPRE001_OIDC_CLIENT_ID "${VALPRE001_OIDC_CLIENT_ID}"

TENANT_ID="$(az account show --query tenantId --output tsv)"

echo
echo "OIDC identity ready, trusting repository '${VALPRE001_GITHUB_REPOSITORY}' and"
echo "GitHub Environment '${VALPRE001_GITHUB_ENVIRONMENT}' via subject:"
echo "  ${OIDC_SUBJECT}"
echo
echo "In the GitHub repository, create that Environment if it does not exist yet"
echo "(Settings > Environments) and set these Actions variables on it:"
echo "  AZURE_CLIENT_ID       = ${VALPRE001_OIDC_CLIENT_ID}"
echo "  AZURE_TENANT_ID       = ${TENANT_ID}"
echo "  AZURE_SUBSCRIPTION_ID = ${AZURE_SUBSCRIPTION_ID}"
echo "  AZURE_RESOURCE_GROUP  = ${AZURE_RESOURCE_GROUP}"
echo
echo "Then trigger the 'VAL-PRE-001: CI check + CD deployment gate demo' workflow via workflow_dispatch."
