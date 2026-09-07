#!/usr/bin/env bash
# Validate five retention-design scenarios for PRI-PRE-003 without creating a resource.
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
require PRIPRE003_POLICY_DEFINITION_NAME
PRIPRE003_DEMO_RESOURCE_NAME="${PRIPRE003_DEMO_RESOURCE_NAME:-pripre003-demo}"

az account set --subscription "${AZURE_SUBSCRIPTION_ID}"

# Runs one scenario and asserts the expected Azure Policy outcome; sets RESULT.
run_scenario() {
  local scenario="$1"
  local expect="$2"
  local correlation="pri-pre-003-${scenario}"
  if az deployment group validate \
    --name "${correlation}" \
    --resource-group "${AZURE_RESOURCE_GROUP}" \
    --template-file "${CONTROL_DIR}/infra/demo-target.bicep" \
    --parameters demoResourceName="${PRIPRE003_DEMO_RESOURCE_NAME}" scenario="${scenario}" \
    --output none >"${TEMP_OUTPUT}" 2>&1; then
    RESULT="validated"
  else
    RESULT="denied"
  fi

  if [[ "${expect}" == "denied" ]]; then
    [[ "${RESULT}" == "denied" ]] || die "Azure allowed the '${scenario}' request. The assignment may still be propagating; retry in a few minutes."
    grep -q 'RequestDisallowedByPolicy' "${TEMP_OUTPUT}" || { cat "${TEMP_OUTPUT}" >&2; die "The '${scenario}' validation failed, but not because PRI-PRE-003 denied it."; }
    echo "BLOCKED as expected (${scenario})."
  else
    [[ "${RESULT}" == "validated" ]] || { cat "${TEMP_OUTPUT}" >&2; die "Azure did not validate the '${scenario}' request."; }
    echo "VALIDATED as expected (${scenario})."
  fi
}

echo "1/5 Complete retention design..."
run_scenario healthy validated
healthy_result="${RESULT}"

echo "2/5 Retention tags entirely missing..."
run_scenario missing denied
missing_result="${RESULT}"

echo "3/5 Retention period is present but not a valid positive integer..."
run_scenario invalid-period denied
invalid_period_result="${RESULT}"

echo "4/5 Retention disposition is present but not 'delete' or 'archive'..."
run_scenario invalid-disposition denied
invalid_disposition_result="${RESULT}"

echo "5/5 No governed data present, so the gate does not apply..."
run_scenario not-applicable validated
not_applicable_result="${RESULT}"

timestamp="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
cat <<JSON
{
  "control_id": "PRI-PRE-003",
  "policy_definition": "${PRIPRE003_POLICY_DEFINITION_NAME}",
  "policy_version": "1.0.0",
  "healthy_result": "${healthy_result}",
  "missing_result": "${missing_result}",
  "invalid_period_result": "${invalid_period_result}",
  "invalid_disposition_result": "${invalid_disposition_result}",
  "not_applicable_result": "${not_applicable_result}",
  "verified_at": "${timestamp}",
  "resource_created": false,
  "action": "block go-live until a complete retention design is documented",
  "accountable_role": "Privacy Officer"
}
JSON
