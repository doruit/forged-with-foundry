#!/usr/bin/env bash
# Independent Azure Policy experiment on the production resource group. It never
# authorizes a release: both requests are expected to be denied.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
[[ -f "${STATE}" ]] || die "Run infra/deploy.sh first."
attempt() { # attempt <label> <deployment-name> <model> <version> <upgrade>
  echo "== $1"
  if out="$(az cognitiveservices account deployment create -g "$(state PROD_RG)" -n "$(state PROD_ACCOUNT)" \
      --deployment-name "$2" --model-format OpenAI --model-name "$3" --model-version "$4" \
      --sku-name GlobalStandard --sku-capacity 10 --version-upgrade-option "$5" 2>&1)"; then
    echo "UNEXPECTED: the deployment was created; removing it."; az cognitiveservices account deployment delete \
      -g "$(state PROD_RG)" -n "$(state PROD_ACCOUNT)" --deployment-name "$2" -o none; return 1
  fi
  printf '%s\n' "${out}" | grep -oE "RequestDisallowedByPolicy|chg-002-[a-z-]+|Disallowed[A-Za-z]*|policy[^.]*\." | sort -u | head -5
}
attempt "Unreleased model version (not on the allow-list)" chg002-direct "${WEAK_MODEL}" "${WEAK_VERSION}" NoAutoUpgrade
attempt "Released model, but set to upgrade automatically" chg002-autoupgrade "${BASELINE_MODEL}" "${BASELINE_VERSION}" OnceNewDefaultVersionAvailable
