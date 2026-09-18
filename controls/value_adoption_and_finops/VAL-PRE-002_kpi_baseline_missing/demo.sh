#!/usr/bin/env bash
# Validate a denied and a remediated VAL-PRE-002 request without creating a resource.
set -euo pipefail

CONTROL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${CONTROL_DIR}/../../.." && pwd)"
CONTROL_ENV="${CONTROL_DIR}/.env"
TEMP_OUTPUT="$(mktemp)"
trap 'rm -f "${TEMP_OUTPUT}"' EXIT

COMPLETE_CONTRACT="${CONTROL_DIR}/fixtures/complete-workload/.fwf/agents/helpdesk-tier1-triage/governance.yaml"
INCOMPLETE_CONTRACT="${CONTROL_DIR}/fixtures/incomplete-workload/.fwf/agents/helpdesk-tier1-triage/governance.yaml"

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

# Runs the shared FwF governance-contract validator (scripts/validate_governance_contract.py)
# against one workload's .fwf/agents/<agent-id>/governance.yaml and maps its generic
# CONTROL_STATUS output to this control's own Azure Policy tag name (kpiBaselineStatus).
assess_contract() {
  local governance_yaml="$1" key value
  CONTROL_STATUS=""
  while IFS='=' read -r key value; do
    case "${key}" in
      CONTROL_STATUS) CONTROL_STATUS="${value}" ;;
    esac
  done < <(python3 "${REPO_ROOT}/scripts/validate_governance_contract.py" \
    --contract "${governance_yaml}" --control VAL-PRE-002 --shell)
  [[ -n "${CONTROL_STATUS}" ]] || die "Shared validator did not return a status for ${governance_yaml}."
}

[[ -f "${CONTROL_ENV}" ]] || die "Copy .env.example to .env and deploy the policy first."
load_env "${REPO_ROOT}/infra/.env"
load_env "${CONTROL_ENV}"

require() { [[ -n "${!1:-}" ]] || die "Missing required environment variable '$1'."; }
require AZURE_SUBSCRIPTION_ID
require AZURE_RESOURCE_GROUP
require VALPRE002_POLICY_DEFINITION_NAME
VALPRE002_DEMO_RESOURCE_NAME="${VALPRE002_DEMO_RESOURCE_NAME:-valpre002-demo}"

command -v python3 >/dev/null 2>&1 || die "python3 is required to run the shared governance-contract validator (scripts/validate_governance_contract.py)."
python3 -c "import jsonschema, yaml" 2>/dev/null || die "jsonschema + PyYAML are required. Run: pip install -r ${REPO_ROOT}/schemas/governance-contract/requirements.txt"

az account set --subscription "${AZURE_SUBSCRIPTION_ID}"

echo "1/2 Assessing a workload with a missing KPI baseline..."
assess_contract "${INCOMPLETE_CONTRACT}"
echo "Validating a go-live request with kpiBaselineStatus=${CONTROL_STATUS}..."
if az deployment group validate \
  --name val-pre-002-incomplete-baseline \
  --resource-group "${AZURE_RESOURCE_GROUP}" \
  --template-file "${CONTROL_DIR}/infra/demo-target.bicep" \
  --parameters demoResourceName="${VALPRE002_DEMO_RESOURCE_NAME}" \
               kpiBaselineStatus="${CONTROL_STATUS}" \
  --output none >"${TEMP_OUTPUT}" 2>&1; then
  die "Azure allowed the incomplete-baseline request. The assignment may still be propagating; retry in a few minutes."
fi

if ! grep -q 'RequestDisallowedByPolicy' "${TEMP_OUTPUT}"; then
  cat "${TEMP_OUTPUT}" >&2
  die "The validation failed, but not because VAL-PRE-002 denied it."
fi
echo "BLOCKED as expected by Azure Policy."

echo "2/2 Assessing a workload with a recorded KPI baseline..."
assess_contract "${COMPLETE_CONTRACT}"
echo "Validating the same request with kpiBaselineStatus=${CONTROL_STATUS}..."
if ! az deployment group validate \
  --name val-pre-002-complete-baseline \
  --resource-group "${AZURE_RESOURCE_GROUP}" \
  --template-file "${CONTROL_DIR}/infra/demo-target.bicep" \
  --parameters demoResourceName="${VALPRE002_DEMO_RESOURCE_NAME}" \
               kpiBaselineStatus="${CONTROL_STATUS}" \
  --output none >"${TEMP_OUTPUT}" 2>&1; then
  cat "${TEMP_OUTPUT}" >&2
  die "Azure did not validate the remediated request."
fi
echo "VALIDATED as expected by Azure Policy."

timestamp="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
cat <<JSON
{
  "control_id": "VAL-PRE-002",
  "policy_definition": "${VALPRE002_POLICY_DEFINITION_NAME}",
  "policy_version": "1.0.0",
  "incomplete_baseline_result": "denied",
  "incomplete_baseline_correlation": "val-pre-002-incomplete-baseline",
  "complete_baseline_result": "validated",
  "complete_baseline_correlation": "val-pre-002-complete-baseline",
  "verified_at": "${timestamp}",
  "resource_created": false,
  "action": "block go-live until a measured KPI baseline is recorded",
  "accountable_role": "Business Owner"
}
JSON
