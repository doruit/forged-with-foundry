#!/usr/bin/env bash
# Independent Azure Policy experiment on the production resource group. It never
# authorizes a release: both requests are expected to be denied.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
[[ -f "${STATE}" || -n "${PROD_RG:-}" ]] || die "Run infra/deploy.sh first (or set PROD_RG and PROD_ACCOUNT in CI)."
attempt() { # attempt <label> <deployment-name> <model> <version> <upgrade>
  echo "== $1"
  if out="$(put_deployment "$(state PROD_RG)" "$(state PROD_ACCOUNT)" "$2" "$3" "$4" "$5" 2>&1)"; then
    echo "UNEXPECTED: the deployment was created; removing it."; az cognitiveservices account deployment delete \
      -g "$(state PROD_RG)" -n "$(state PROD_ACCOUNT)" --deployment-name "$2" -o none; return 1
  fi
  # Only a policy error counts as a denial; any other failure is reported as such.
  if ! printf '%s\n' "${out}" | grep -qE "RequestDisallowedByPolicy|PolicyViolation|policy"; then
    echo "FAILED for a reason other than Azure Policy:"; printf '%s\n' "${out}" | head -5; return 1
  fi
  printf '%s\n' "${out}" | grep -oE "RequestDisallowedByPolicy|PolicyViolation|chg-002-[a-z-]+|aafe3651-[0-9a-f-]+|[^.\"]*[Pp]olicy[^.\"]*\." | sort -u | head -6
}
rc=0
attempt "Unreleased model version (not on the allow-list)" chg002-direct "${WEAK_MODEL}" "${WEAK_VERSION}" NoAutoUpgrade || rc=1
attempt "Released model, but set to upgrade automatically" chg002-autoupgrade "${BASELINE_MODEL}" "${BASELINE_VERSION}" OnceNewDefaultVersionAvailable || rc=1
exit "${rc}"
