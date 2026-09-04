#!/usr/bin/env bash
# Validate a denied and a remediated PRI-PRE-001 request without creating a resource.
set -euo pipefail

CONTROL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${CONTROL_DIR}/../../.." && pwd)"
CONTROL_ENV="${CONTROL_DIR}/.env"
TEMP_OUTPUT="$(mktemp)"
trap 'rm -f "${TEMP_OUTPUT}"' EXIT

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

[[ -f "${CONTROL_ENV}" ]] || die "Copy .env.example to .env and deploy the policy first."
load_env "${REPO_ROOT}/infra/.env"
load_env "${CONTROL_ENV}"

require() { [[ -n "${!1:-}" ]] || die "Missing required environment variable '$1'."; }
require AZURE_SUBSCRIPTION_ID
require AZURE_RESOURCE_GROUP
require PRIPRE001_POLICY_DEFINITION_NAME
PRIPRE001_DEMO_RESOURCE_NAME="${PRIPRE001_DEMO_RESOURCE_NAME:-pripre001-demo}"

az account set --subscription "${AZURE_SUBSCRIPTION_ID}"

echo "1/2 Validating a high-risk go-live request without DPIA evidence..."
if az deployment group validate \
  --name pri-pre-001-missing-dpia \
  --resource-group "${AZURE_RESOURCE_GROUP}" \
  --template-file "${CONTROL_DIR}/demo-target.bicep" \
  --parameters demoResourceName="${PRIPRE001_DEMO_RESOURCE_NAME}" dpiaApproved=false \
  --output none >"${TEMP_OUTPUT}" 2>&1; then
  die "Azure allowed the missing-DPIA request. The assignment may still be propagating; retry in a few minutes."
fi

if ! grep -q 'RequestDisallowedByPolicy' "${TEMP_OUTPUT}"; then
  cat "${TEMP_OUTPUT}" >&2
  die "The validation failed, but not because PRI-PRE-001 denied it."
fi
echo "BLOCKED as expected by Azure Policy."

echo "2/2 Validating the same request with approved DPIA evidence..."
if ! az deployment group validate \
  --name pri-pre-001-approved-dpia \
  --resource-group "${AZURE_RESOURCE_GROUP}" \
  --template-file "${CONTROL_DIR}/demo-target.bicep" \
  --parameters demoResourceName="${PRIPRE001_DEMO_RESOURCE_NAME}" dpiaApproved=true \
  --output none >"${TEMP_OUTPUT}" 2>&1; then
  cat "${TEMP_OUTPUT}" >&2
  die "Azure did not validate the remediated request."
fi
echo "VALIDATED as expected by Azure Policy."

timestamp="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
cat <<JSON
{
  "control_id": "PRI-PRE-001",
  "policy_definition": "${PRIPRE001_POLICY_DEFINITION_NAME}",
  "policy_version": "1.0.0",
  "missing_dpia_result": "denied",
  "missing_dpia_correlation": "pri-pre-001-missing-dpia",
  "approved_dpia_result": "validated",
  "approved_dpia_correlation": "pri-pre-001-approved-dpia",
  "verified_at": "${timestamp}",
  "resource_created": false,
  "action": "block go-live until approved DPIA evidence is present",
  "accountable_role": "Data Protection Officer"
}
JSON
