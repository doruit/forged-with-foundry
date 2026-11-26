#!/usr/bin/env bash
# Remove only CHG-002's own resources: its two resource groups (after checking
# their control-id tag), the soft-deleted Foundry accounts, its custom policy
# definition and the local state and release record. The shared infra/ resource group is never touched.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
[[ -f "${STATE}" ]] || die "Nothing to clean up: .state/env not found."
for rg in "$(state EVAL_RG)" "$(state PROD_RG)"; do
  tag="$(az group show -n "${rg}" --query "tags.\"control-id\"" -o tsv 2>/dev/null || true)"
  if [[ -z "${tag}" ]]; then echo "${rg}: already absent"; continue; fi
  [[ "${tag}" == "CHG-002" ]] || die "${rg} is not tagged control-id=CHG-002; refusing to delete it."
  echo "Deleting ${rg}..."; az group delete -n "${rg}" --yes -o none
done
# Purge each soft-deleted account with its own resource group (a purge with the
# wrong group returns success without purging; observed live).
az cognitiveservices account purge -l "$(state LOCATION)" -g "$(state EVAL_RG)" -n "$(state EVAL_ACCOUNT)" -o none 2>/dev/null || true
az cognitiveservices account purge -l "$(state LOCATION)" -g "$(state PROD_RG)" -n "$(state PROD_ACCOUNT)" -o none 2>/dev/null || true
az policy definition delete -n chg-002-deny-model-auto-upgrade -o none 2>/dev/null || true
echo "Verifying..."
for rg in "$(state EVAL_RG)" "$(state PROD_RG)"; do [[ "$(az group exists -n "${rg}")" == false ]] || die "${rg} still exists"; done
az policy definition show -n chg-002-deny-model-auto-upgrade -o none 2>/dev/null && die "custom policy definition still exists"
left="$(az cognitiveservices account list-deleted --query "[?name=='$(state EVAL_ACCOUNT)' || name=='$(state PROD_ACCOUNT)'].name" -o tsv)"
[[ -z "${left}" ]] || die "soft-deleted Foundry account(s) not purged: ${left}"
echo "Cleanup verified: both CHG-002 resource groups, their Foundry accounts and the custom policy definition are gone."
# The local release record cites runs that no longer exist; a stale record must
# not put its model on the next deployment's allow-list.
rm -f "${STATE}" "${CONTROL_DIR}/release/release-baseline.json"
