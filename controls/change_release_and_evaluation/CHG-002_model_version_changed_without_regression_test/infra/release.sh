#!/usr/bin/env bash
# Release the gated candidate to production. Refuses unless the credential-free
# gate allows the committed candidate; then extends the Policy allow-list with
# exactly that model version, deploys it and points a new production agent
# version at it, and records the release baseline for QLT-006.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
[[ -f "${STATE}" ]] || die "Run infra/deploy.sh first."
cd "${CONTROL_DIR}"
"${PYTHON}" -m src.chg_002 gate --root candidate >/dev/null || die "Candidate gate blocked the release (run: python -m src.chg_002 gate)."
ASSET="$(candidate_asset)"
apply_policy "$(asset_of azure-openai "${BASELINE_MODEL}" "${BASELINE_VERSION}")" "${ASSET}" $(released_assets)
NAME="$("${PYTHON}" -c "import json;print(json.load(open('candidate/model-deployment.json'))['deploymentName'])")"
az deployment group create -g "$(state PROD_RG)" --name chg-002-prod-release --template-file infra/foundry.bicep \
  --parameters stage=prod accountName="$(state PROD_ACCOUNT)" setupPrincipalId="$(az ad signed-in-user show --query id -o tsv)" \
  deployments="[$(deployment_json chg002-baseline "${BASELINE_MODEL}" "${BASELINE_VERSION}"),$(deployment_json chg002-judge "${BASELINE_MODEL}" "${BASELINE_VERSION}"),$(candidate_json)]" -o none
VERSION="$(FOUNDRY_PROJECT_ENDPOINT="$(state PROD_ENDPOINT)" "${PYTHON}" -m src.chg_002 agent-version --deployment "${NAME}" | awk '{print $3}')"
printf 'PROD_LIVE_VERSION=%s\n' "${VERSION}" >> "${STATE}"
"${PYTHON}" -m src.chg_002 release --root candidate --production-agent-version "${VERSION}"
