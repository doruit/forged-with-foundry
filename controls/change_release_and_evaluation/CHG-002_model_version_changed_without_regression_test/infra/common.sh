# Shared helpers for CHG-002 scripts. Sourced, never executed.
CONTROL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${CONTROL_DIR}/../../.." && pwd)"
PYTHON="${PYTHON:-${REPO_ROOT}/.venv/bin/python}"
STATE="${CONTROL_DIR}/.state/env"
die() { echo "Error: $*" >&2; exit 1; }
state() { # environment variable first (CI), then .state/env (local)
  if [[ -n "${!1:-}" ]]; then echo "${!1}"; else grep -E "^$1=" "${STATE}" 2>/dev/null | tail -1 | cut -d= -f2-; fi; }
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
released_assets() { # asset IDs from the committed release baseline record, if any
  [[ -f "${CONTROL_DIR}/release/release-baseline.json" ]] || return 0
  "${PYTHON}" -c "import json,sys; print(json.load(open(sys.argv[1]))['model']['assetId'])" "${CONTROL_DIR}/release/release-baseline.json"; }
apply_policy() { # apply_policy <asset>...
  local ids; ids="$("${PYTHON}" -c 'import json,sys; print(json.dumps(sorted(set(sys.argv[1:]))))' "$@")"
  az deployment sub create --location "$(state LOCATION)" --name chg-002-policy \
    --template-file "${CONTROL_DIR}/infra/policy.bicep" \
    --parameters prodResourceGroupName="$(state PROD_RG)" allowedAssetIds="${ids}" -o none
  echo "Azure Policy allow-list on $(state PROD_RG): ${ids}"; }
