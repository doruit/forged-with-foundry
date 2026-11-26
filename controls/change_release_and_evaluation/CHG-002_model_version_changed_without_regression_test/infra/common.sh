# Shared helpers for CHG-002 scripts. Sourced, never executed.
CONTROL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${CONTROL_DIR}/../../.." && pwd)"
PYTHON="${PYTHON:-${REPO_ROOT}/.venv/bin/python}"
STATE="${CONTROL_DIR}/.state/env"
die() { echo "Error: $*" >&2; exit 1; }
state() { # environment variable first (CI), then .state/env (local)
  if [[ -n "${!1:-}" ]]; then echo "${!1}"; else { grep -E "^$1=" "${STATE}" 2>/dev/null || true; } | tail -1 | cut -d= -f2-; fi; }
asset_of() { # asset_of <format/registry> <name> <version>
  echo "azureml://registries/$1/models/$2/versions/$3"; }
BASELINE_MODEL=gpt-4.1-mini; BASELINE_VERSION=2025-04-14
WEAK_MODEL=gpt-4.1-nano;     WEAK_VERSION=2025-04-14
deployment_json() { # deployment_json <name> <model> <version>
  printf '{"name":"%s","model":{"format":"OpenAI","name":"%s","version":"%s"},"sku":{"name":"GlobalStandard","capacity":10},"versionUpgradeOption":"NoAutoUpgrade"}' "$1" "$2" "$3"; }
candidate_json() {
  "${PYTHON}" - "${CONTROL_DIR}/candidate/model-deployment.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
print(json.dumps({"name": d["deploymentName"], "model": d["model"], "sku": d["sku"], "versionUpgradeOption": d["versionUpgradeOption"]}))
PY
}
candidate_asset() {
  "${PYTHON}" -c "import json,sys; d=json.load(open(sys.argv[1])); m=d['model']; print(f\"azureml://registries/{d['registry']}/models/{m['name']}/versions/{m['version']}\")" "${CONTROL_DIR}/candidate/model-deployment.json"; }
released_assets() { # asset ID from this environment's release baseline record, if any
  [[ -f "${CONTROL_DIR}/release/release-baseline.json" ]] || return 0
  "${PYTHON}" -c "import json,sys; print(json.load(open(sys.argv[1]))['model']['assetId'])" "${CONTROL_DIR}/release/release-baseline.json"; }
put_deployment() { # put_deployment <rg> <account> <name> <model> <version> <upgrade>; ARM PUT because az CLI has no upgrade-option flag
  local url
  url="https://management.azure.com/subscriptions/$(az account show --query id -o tsv)/resourceGroups/$1/providers/Microsoft.CognitiveServices/accounts/$2/deployments/$3?api-version=2025-06-01"
  az rest --method put --url "${url}" -o none --body \
    "$(printf '{"sku":{"name":"GlobalStandard","capacity":10},"properties":{"model":{"format":"OpenAI","name":"%s","version":"%s"},"versionUpgradeOption":"%s","raiPolicyName":"Microsoft.DefaultV2"}}' "$4" "$5" "$6")" || return 1
  local s
  for _ in $(seq 60); do
    s="$(az cognitiveservices account deployment show -g "$1" -n "$2" --deployment-name "$3" --query properties.provisioningState -o tsv)"
    [[ "${s}" == "Succeeded" ]] && return 0
    [[ "${s}" == "Failed" ]] && { echo "Deployment $3 failed to provision." >&2; return 1; }
    sleep 5
  done
  echo "Deployment $3 did not finish provisioning." >&2; return 1; }
apply_policy() { # apply_policy <asset>...
  local ids; ids="$("${PYTHON}" -c 'import json,sys; print(json.dumps(sorted(set(sys.argv[1:]))))' "$@")"
  az deployment sub create --location "$(state LOCATION)" --name chg-002-policy \
    --template-file "${CONTROL_DIR}/infra/policy.bicep" \
    --parameters prodResourceGroupName="$(state PROD_RG)" allowedAssetIds="${ids}" -o none
  echo "Azure Policy allow-list on $(state PROD_RG): ${ids}"; }
