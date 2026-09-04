#!/usr/bin/env bash
# Create, inspect, remediate, or clean up the one PRI-PRE-002 demo target.
set -euo pipefail

CONTROL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
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

[[ -f "${CONTROL_ENV}" ]] || die "Copy .env.example to .env and deploy the policy first."
load_env "${REPO_ROOT}/infra/.env"
load_env "${CONTROL_ENV}"

require() { [[ -n "${!1:-}" ]] || die "Missing required environment variable '$1'."; }
require AZURE_SUBSCRIPTION_ID
require AZURE_RESOURCE_GROUP
require PRIPRE002_POLICY_ASSIGNMENT_ID
PRIPRE002_DEMO_RESOURCE_NAME="${PRIPRE002_DEMO_RESOURCE_NAME:-pripre002-demo}"

az account set --subscription "${AZURE_SUBSCRIPTION_ID}"

resource_id() {
  az resource show \
    --resource-group "${AZURE_RESOURCE_GROUP}" \
    --resource-type Microsoft.Insights/actionGroups \
    --name "${PRIPRE002_DEMO_RESOURCE_NAME}" \
    --query id --output tsv 2>/dev/null
}

trigger_scan() {
  az policy state trigger-scan --resource-group "${AZURE_RESOURCE_GROUP}" --no-wait
  echo "Policy scan requested. Run '$0 status' after Azure has evaluated the resource."
}

case "${1:-}" in
  start)
    az deployment group create \
      --name pri-pre-002-noncompliant \
      --resource-group "${AZURE_RESOURCE_GROUP}" \
      --mode Incremental \
      --template-file "${CONTROL_DIR}/demo-target.bicep" \
      --parameters demoResourceName="${PRIPRE002_DEMO_RESOURCE_NAME}" remediated=false \
      --output none
    echo "Demo target deployed. Audit did not block the request."
    trigger_scan
    ;;
  remediate)
    resource_id >/dev/null || die "Demo target not found. Run '$0 start' first."
    az deployment group create \
      --name pri-pre-002-remediated \
      --resource-group "${AZURE_RESOURCE_GROUP}" \
      --mode Incremental \
      --template-file "${CONTROL_DIR}/demo-target.bicep" \
      --parameters demoResourceName="${PRIPRE002_DEMO_RESOURCE_NAME}" remediated=true \
      --output none
    echo "The same target now has a recognized basis and purpose reference."
    trigger_scan
    ;;
  status)
    demo_resource_id="$(resource_id)" || die "Demo target not found. Run '$0 start' first."
    state="$(az policy state list \
      --resource "${demo_resource_id}" \
      --filter "PolicyAssignmentId eq '${PRIPRE002_POLICY_ASSIGNMENT_ID}'" \
      --query '[0].{complianceState:complianceState,policyDefinitionId:policyDefinitionId,policyAssignmentId:policyAssignmentId,resourceId:resourceId,resourceType:resourceType,evaluatedAt:timestamp}' \
      --output json)"
    if [[ "${state}" == "null" || -z "${state}" ]]; then
      printf '{"complianceState":"Pending","message":"Azure Policy has not reported a state yet."}\n'
    else
      printf '%s\n' "${state}"
    fi
    ;;
  cleanup)
    if demo_resource_id="$(resource_id)"; then
      az resource delete --ids "${demo_resource_id}"
      echo "PRI-PRE-002 demo target deleted."
    else
      echo "PRI-PRE-002 demo target is already absent."
    fi
    ;;
  *)
    echo "Usage: $0 {start|status|remediate|cleanup}" >&2
    exit 2
    ;;
esac
