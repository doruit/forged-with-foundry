#!/usr/bin/env bash
# Remove only CHG-002's own resources: its two resource groups (after checking
# their control-id tag), the soft-deleted Foundry accounts, and its custom
# policy definition. The shared infra/ resource group is never touched.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
[[ -f "${STATE}" ]] || die "Nothing to clean up: .state/env not found."
for rg in "$(state EVAL_RG)" "$(state PROD_RG)"; do
  tag="$(az group show -n "${rg}" --query "tags.\"control-id\"" -o tsv 2>/dev/null || true)"
  if [[ -z "${tag}" ]]; then echo "${rg}: already absent"; continue; fi
  [[ "${tag}" == "CHG-002" ]] || die "${rg} is not tagged control-id=CHG-002; refusing to delete it."
  echo "Deleting ${rg}..."; az group delete -n "${rg}" --yes -o none
done
for account in "$(state EVAL_ACCOUNT)" "$(state PROD_ACCOUNT)"; do
  az cognitiveservices account purge -l "$(state LOCATION)" -g "$(state EVAL_RG)" -n "${account}" -o none 2>/dev/null \
    || az cognitiveservices account purge -l "$(state LOCATION)" -g "$(state PROD_RG)" -n "${account}" -o none 2>/dev/null || true
done
az policy definition delete -n chg-002-deny-model-auto-upgrade -o none 2>/dev/null || true
echo "Verifying..."
for rg in "$(state EVAL_RG)" "$(state PROD_RG)"; do [[ "$(az group exists -n "${rg}")" == false ]] || die "${rg} still exists"; done
az policy definition show -n chg-002-deny-model-auto-upgrade -o none 2>/dev/null && die "custom policy definition still exists"
echo "Cleanup verified: both CHG-002 resource groups and the custom policy definition are gone."
rm -f "${STATE}"
