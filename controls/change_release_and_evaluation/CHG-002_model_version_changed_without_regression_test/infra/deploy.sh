#!/usr/bin/env bash
# Deploy CHG-002: an evaluation stage and a production stage (each its own
# control-owned resource group), Azure Policy on production, and version 1 of
# the agent on the baseline model in both stages.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
ENV_PATH="${REPO_ROOT}/infra/.env"
[[ -f "${ENV_PATH}" ]] || die "Missing ${ENV_PATH}. Deploy the shared infra/ first (it sets the subscription and region)."
env_value() { grep -E "^$1=" "${ENV_PATH}" | tail -1 | cut -d= -f2- | tr -d '"'"'"; }
SUBSCRIPTION_ID="$(env_value AZURE_SUBSCRIPTION_ID)"; LOCATION="$(env_value AZURE_LOCATION)"; LOCATION="${LOCATION:-swedencentral}"
[[ "$(az account show --query id -o tsv)" == "${SUBSCRIPTION_ID}" ]] || die "Run: az account set --subscription <id from infra/.env>"

mkdir -p "$(dirname "${STATE}")"
SUFFIX="$(state SUFFIX)"; SUFFIX="${SUFFIX:-$(LC_ALL=C tr -dc 'a-z0-9' </dev/urandom | head -c 6)}"
EVAL_RG="rg-chg002-eval-${SUFFIX}"; PROD_RG="rg-chg002-prod-${SUFFIX}"
printf 'SUFFIX=%s\nLOCATION=%s\nEVAL_RG=%s\nPROD_RG=%s\nEVAL_ACCOUNT=chg002eval%s\nPROD_ACCOUNT=chg002prod%s\n' \
  "${SUFFIX}" "${LOCATION}" "${EVAL_RG}" "${PROD_RG}" "${SUFFIX}" "${SUFFIX}" > "${STATE}"
PRINCIPAL_ID="$(az ad signed-in-user show --query id -o tsv)"

for rg in "${EVAL_RG}" "${PROD_RG}"; do
  az group create -n "${rg}" -l "${LOCATION}" --tags control-id=CHG-002 purpose=synthetic-model-change-gate-demo -o none
done

stage() { # stage <eval|prod> <rg> <account> <deployments-json>
  az deployment group create -g "$2" --name "chg-002-$1" --template-file "${CONTROL_DIR}/infra/foundry.bicep" \
    --parameters stage="$1" accountName="$3" setupPrincipalId="${PRINCIPAL_ID}" deployments="$4" \
    --query properties.outputs.projectEndpoint.value -o tsv; }

BASE="$(deployment_json chg002-baseline "${BASELINE_MODEL}" "${BASELINE_VERSION}")"
JUDGE="$(deployment_json chg002-judge "${BASELINE_MODEL}" "${BASELINE_VERSION}")"
WEAK="$(deployment_json chg002-weak "${WEAK_MODEL}" "${WEAK_VERSION}")"
echo "Deploying the evaluation stage (baseline, judge, candidate and weak models)..."
EVAL_ENDPOINT="$(stage eval "${EVAL_RG}" "$(state EVAL_ACCOUNT)" "[${BASE},${JUDGE},$(candidate_json),${WEAK}]")"

# Production allows only released models and the judge. Policy goes first so
# the production deployments themselves are evaluated against it.
apply_policy "$(asset_of azure-openai "${BASELINE_MODEL}" "${BASELINE_VERSION}")" $(released_assets)
echo "Deploying the production stage (released baseline and judge only)..."
PROD_ENDPOINT="$(stage prod "${PROD_RG}" "$(state PROD_ACCOUNT)" "[${BASE},${JUDGE}]")"
printf 'EVAL_ENDPOINT=%s\nPROD_ENDPOINT=%s\n' "${EVAL_ENDPOINT}" "${PROD_ENDPOINT}" >> "${STATE}"

echo "Waiting 60 s for role assignments to propagate..."; sleep 60
cd "${CONTROL_DIR}"
EVAL_V1="$(FOUNDRY_PROJECT_ENDPOINT="${EVAL_ENDPOINT}" "${PYTHON}" -m src.chg_002 agent-version --deployment chg002-baseline | awk '{print $3}')"
PROD_V1="$(FOUNDRY_PROJECT_ENDPOINT="${PROD_ENDPOINT}" "${PYTHON}" -m src.chg_002 agent-version --deployment chg002-baseline | awk '{print $3}')"
printf 'EVAL_BASELINE_VERSION=%s\nPROD_LIVE_VERSION=%s\n' "${EVAL_V1}" "${PROD_V1}" >> "${STATE}"
echo
echo "Deployed. State in .state/env (not committed)."
echo "  Evaluation project: ${EVAL_ENDPOINT} (baseline agent version ${EVAL_V1})"
echo "  Production project: ${PROD_ENDPOINT} (live agent version ${PROD_V1})"
