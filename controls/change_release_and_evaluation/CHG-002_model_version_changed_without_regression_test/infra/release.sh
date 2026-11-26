#!/usr/bin/env bash
# Release the gated candidate to production. Refuses unless the credential-free
# gate allows the committed candidate; then extends the Policy allow-list with
# exactly that model version, deploys it and points a new production agent
# version at it, and records the release baseline for QLT-006.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
[[ -f "${STATE}" || -n "${PROD_RG:-}" ]] || die "Run infra/deploy.sh first (or set PROD_RG and PROD_ACCOUNT in CI)."
cd "${CONTROL_DIR}"
"${PYTHON}" -m src.chg_002 gate --root candidate >/dev/null || die "Candidate gate blocked the release (run: python -m src.chg_002 gate)."
ASSET="$(candidate_asset)"
apply_policy "$(asset_of azure-openai "${BASELINE_MODEL}" "${BASELINE_VERSION}")" "${ASSET}" $(released_assets)
NAME="$("${PYTHON}" -c "import json;print(json.load(open('candidate/model-deployment.json'))['deploymentName'])")"
read -r MODEL MVERSION < <("${PYTHON}" -c "import json;d=json.load(open('candidate/model-deployment.json'));print(d['model']['name'],d['model']['version'])")
put_deployment "$(state PROD_RG)" "$(state PROD_ACCOUNT)" "${NAME}" "${MODEL}" "${MVERSION}" NoAutoUpgrade \
  || die "Production deployment of ${NAME} failed."
VERSION="$(FOUNDRY_PROJECT_ENDPOINT="$(state PROD_ENDPOINT)" "${PYTHON}" -m src.chg_002 agent-version --deployment "${NAME}" | awk '{print $3}')"
mkdir -p "$(dirname "${STATE}")"; printf "PROD_LIVE_VERSION=%s\n" "${VERSION}" >> "${STATE}"
"${PYTHON}" -m src.chg_002 release --root candidate --production-agent-version "${VERSION}"
