#!/usr/bin/env bash
# Validate a denied and a remediated VAL-PRE-001 request without creating a resource.
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

# Runs the Python configuration assessment against an agent.yaml fixture and
# fills VALUE_HYPOTHESIS_STATUS / BUSINESS_CASE_ID with its result.
assess_agent_yaml() {
  local fixture="$1" line key value
  VALUE_HYPOTHESIS_STATUS=""
  BUSINESS_CASE_ID=""
  while IFS='=' read -r key value; do
    case "${key}" in
      VALUE_HYPOTHESIS_STATUS) VALUE_HYPOTHESIS_STATUS="${value}" ;;
      BUSINESS_CASE_ID) BUSINESS_CASE_ID="${value}" ;;
    esac
  done < <(python3 "${CONTROL_DIR}/scripts/validate_value_hypothesis.py" "${fixture}" --shell)
  [[ -n "${VALUE_HYPOTHESIS_STATUS}" ]] || die "Configuration assessment did not return a status for ${fixture}."
}

[[ -f "${CONTROL_ENV}" ]] || die "Copy .env.example to .env and deploy the policy first."
load_env "${REPO_ROOT}/infra/.env"
load_env "${CONTROL_ENV}"

require() { [[ -n "${!1:-}" ]] || die "Missing required environment variable '$1'."; }
require AZURE_SUBSCRIPTION_ID
require AZURE_RESOURCE_GROUP
require VALPRE001_POLICY_DEFINITION_NAME
VALPRE001_DEMO_RESOURCE_NAME="${VALPRE001_DEMO_RESOURCE_NAME:-valpre001-demo}"

command -v python3 >/dev/null 2>&1 || die "python3 is required to run the configuration assessment (scripts/validate_value_hypothesis.py)."
python3 -c "import yaml" 2>/dev/null || die "PyYAML is required. Run: pip install -r ${CONTROL_DIR}/requirements.txt"

az account set --subscription "${AZURE_SUBSCRIPTION_ID}"

echo "1/2 Assessing an agent.yaml with an incomplete value hypothesis..."
assess_agent_yaml "${CONTROL_DIR}/fixtures/agent.incomplete.yaml"
echo "Validating a go-live request with valueHypothesisStatus=${VALUE_HYPOTHESIS_STATUS}..."
if az deployment group validate \
  --name val-pre-001-incomplete-hypothesis \
  --resource-group "${AZURE_RESOURCE_GROUP}" \
  --template-file "${CONTROL_DIR}/infra/demo-target.bicep" \
  --parameters demoResourceName="${VALPRE001_DEMO_RESOURCE_NAME}" \
               valueHypothesisStatus="${VALUE_HYPOTHESIS_STATUS}" \
               businessCaseId="${BUSINESS_CASE_ID}" \
  --output none >"${TEMP_OUTPUT}" 2>&1; then
  die "Azure allowed the incomplete-hypothesis request. The assignment may still be propagating; retry in a few minutes."
fi

if ! grep -q 'RequestDisallowedByPolicy' "${TEMP_OUTPUT}"; then
  cat "${TEMP_OUTPUT}" >&2
  die "The validation failed, but not because VAL-PRE-001 denied it."
fi
echo "BLOCKED as expected by Azure Policy."

echo "2/2 Assessing an agent.yaml with a complete, measurable value hypothesis..."
assess_agent_yaml "${CONTROL_DIR}/fixtures/agent.yaml"
echo "Validating the same request with valueHypothesisStatus=${VALUE_HYPOTHESIS_STATUS}..."
if ! az deployment group validate \
  --name val-pre-001-complete-hypothesis \
  --resource-group "${AZURE_RESOURCE_GROUP}" \
  --template-file "${CONTROL_DIR}/infra/demo-target.bicep" \
  --parameters demoResourceName="${VALPRE001_DEMO_RESOURCE_NAME}" \
               valueHypothesisStatus="${VALUE_HYPOTHESIS_STATUS}" \
               businessCaseId="${BUSINESS_CASE_ID}" \
  --output none >"${TEMP_OUTPUT}" 2>&1; then
  cat "${TEMP_OUTPUT}" >&2
  die "Azure did not validate the remediated request."
fi
echo "VALIDATED as expected by Azure Policy."

timestamp="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
cat <<JSON
{
  "control_id": "VAL-PRE-001",
  "policy_definition": "${VALPRE001_POLICY_DEFINITION_NAME}",
  "policy_version": "2.0.0",
  "incomplete_hypothesis_result": "denied",
  "incomplete_hypothesis_correlation": "val-pre-001-incomplete-hypothesis",
  "complete_hypothesis_result": "validated",
  "complete_hypothesis_correlation": "val-pre-001-complete-hypothesis",
  "verified_at": "${timestamp}",
  "resource_created": false,
  "action": "block go-live until a measurable value hypothesis is present",
  "accountable_role": "Business Owner"
}
JSON
