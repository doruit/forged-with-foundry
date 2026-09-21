#!/usr/bin/env bash
set -euo pipefail

CONTROL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

demo_resources() {
  az resource list --resource-group "${AZURE_RESOURCE_GROUP}" \
    --resource-type Microsoft.Insights/actionGroups --output json |
    jq --arg name "${RESOURCE_NAME}" '[.[] | select(.name == $name)]'
}

demo_deployments() {
  az deployment group list --resource-group "${AZURE_RESOURCE_GROUP}" \
    --output json |
    jq --arg name "${RESOURCE_NAME}" '[.[] | select(.name == $name)]'
}

cleanup() {
  local resources deployments resource_id
  resources="$(demo_resources)" || return 1
  if [[ "$(jq 'length' <<< "${resources}")" != 0 ]]; then
    if ! jq -e --arg run "${DEMO_RUN_ID}" \
      'length == 1 and (.[0].tags | .["control-id"] == "VAL-PRE-002"
       and .purpose == "governance-control-demo" and .["demo-run-id"] == $run)' \
      <<< "${resources}" >/dev/null; then
      echo "ERROR: refusing cleanup of a resource without this demo ownership." >&2
      return 1
    fi
    resource_id="$(jq -r '.[0].id' <<< "${resources}")"
    az resource delete --ids "${resource_id}" || return 1
    resources="$(demo_resources)" || return 1
    [[ "$(jq 'length' <<< "${resources}")" == 0 ]] || return 1
  fi
  deployments="$(demo_deployments)" || return 1
  if [[ "$(jq 'length' <<< "${deployments}")" != 0 ]]; then
    if ! jq -e --arg run "${DEMO_RUN_ID}" --arg name "${RESOURCE_NAME}" \
      'length == 1 and (.[0].properties.parameters |
       .demoRunId.value == $run and .demoResourceName.value == $name)' \
      <<< "${deployments}" >/dev/null; then
      echo "ERROR: refusing cleanup of a deployment without this demo ownership." >&2
      return 1
    fi
    az deployment group delete --resource-group "${AZURE_RESOURCE_GROUP}" \
      --name "${RESOURCE_NAME}" || return 1
    deployments="$(demo_deployments)" || return 1
    [[ "$(jq 'length' <<< "${deployments}")" == 0 ]] || return 1
  fi
  echo "CLEANUP VERIFIED: ${RESOURCE_NAME} resource and deployment record absent."
}

finish() {
  local exit_code=$?
  trap - EXIT
  if ! cleanup; then
    echo "ERROR: cleanup failed for ${RESOURCE_NAME}; rerun cleanup-${MODE}." >&2
    exit_code=1
  fi
  rm -f "${ERROR_LOG}"
  exit "${exit_code}"
}

main() {
  local requested_mode="${1:-}" resources deployments deploy_exit=0
  case "${requested_mode}" in
    release|policy-only|cleanup-release|cleanup-policy-only) ;;
    *) echo "usage: $0 release|policy-only|cleanup-release|cleanup-policy-only" >&2; exit 2 ;;
  esac
  MODE="${requested_mode#cleanup-}"
  : "${AZURE_RESOURCE_GROUP:?Set AZURE_RESOURCE_GROUP}"
  : "${DEMO_RUN_ID:?Set DEMO_RUN_ID to the numeric run-id and attempt}"
  [[ "${DEMO_RUN_ID}" =~ ^[0-9]{1,20}-[0-9]{1,5}$ ]] || exit 2
  RESOURCE_NAME="valpre002-${MODE}-${DEMO_RUN_ID}"
  command -v az >/dev/null
  command -v jq >/dev/null
  if [[ "${requested_mode}" == cleanup-* ]]; then
    cleanup
    return
  fi
  if [[ "${MODE}" == release ]]; then
    [[ "${BASELINE_STATUS:-}" == complete ]] || {
      echo "ERROR: release requires the successful candidate gate's status." >&2
      exit 1
    }
  else
    BASELINE_STATUS=incomplete
  fi
  resources="$(demo_resources)"
  deployments="$(demo_deployments)"
  [[ "$(jq 'length' <<< "${resources}")" == 0 && \
     "$(jq 'length' <<< "${deployments}")" == 0 ]] || {
    echo "ERROR: demo name already exists; refusing to overwrite or delete it." >&2
    exit 1
  }
  ERROR_LOG="$(mktemp)"
  trap finish EXIT
  az deployment group create --name "${RESOURCE_NAME}" \
    --resource-group "${AZURE_RESOURCE_GROUP}" --mode Incremental \
    --template-file "${CONTROL_DIR}/infra/demo-target.bicep" \
    --parameters demoResourceName="${RESOURCE_NAME}" \
      kpiBaselineStatus="${BASELINE_STATUS}" demoRunId="${DEMO_RUN_ID}" \
    --output none >"${ERROR_LOG}" 2>&1 || deploy_exit=$?
  if [[ "${MODE}" == policy-only ]]; then
    [[ "${deploy_exit}" -ne 0 ]] && \
      grep -Fq RequestDisallowedByPolicy "${ERROR_LOG}" && \
      grep -Fq "${VALPRE002_POLICY_ASSIGNMENT_NAME:-val-pre-002-kpi-baseline-gate-assignment}" "${ERROR_LOG}" || {
        echo "ERROR: expected RequestDisallowedByPolicy from the VAL-PRE-002 assignment." >&2
        cat "${ERROR_LOG}" >&2
        exit 1
      }
    echo "DENIED: RequestDisallowedByPolicy from VAL-PRE-002; CI deliberately not used."
  else
    if [[ "${deploy_exit}" -ne 0 ]]; then
      cat "${ERROR_LOG}" >&2
      exit "${deploy_exit}"
    fi
    resources="$(demo_resources)"
    jq -e --arg run "${DEMO_RUN_ID}" \
      'length == 1 and (.[0].tags | .kpiBaselineStatus == "complete"
       and .["control-id"] == "VAL-PRE-002" and .["demo-run-id"] == $run)' \
      <<< "${resources}" >/dev/null
    echo "DEPLOYED: gated synthetic candidate; Azure accepted the tagged request."
  fi
}

main "$@"