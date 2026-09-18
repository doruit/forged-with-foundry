#!/usr/bin/env bash
# The Forged with Foundry deployment enforcement boundary.
#
# Sequence (never reordered):
#   1. determine deployment targets and policy profile   (--manifest / --profile)
#   2. discover and structurally validate contracts       (scripts/build_deployment_plan.py)
#   3. evaluate Conftest policies                         (conftest test policy/governance-contract)
#   4. allow deployment only when every required check succeeds
#
# This is a GATE command: it exits non-zero on denial OR execution failure, and is meant
# to block a real deployment job (see docs/governance-contract.md#policy-layer for how a
# real pipeline wires this in). It is not a report-only command; for a structural-only,
# non-blocking check use scripts/validate_governance_contract.py without --enforce.
set -euo pipefail

usage() {
  echo "usage: $0 --manifest PATH --profile NAME --root PATH [--evidence-out PATH]" >&2
  exit 2
}

MANIFEST=""
PROFILE=""
ROOT=""
EVIDENCE_OUT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --manifest) MANIFEST="$2"; shift 2 ;;
    --profile) PROFILE="$2"; shift 2 ;;
    --root) ROOT="$2"; shift 2 ;;
    --evidence-out) EVIDENCE_OUT="$2"; shift 2 ;;
    *) usage ;;
  esac
done
[[ -n "${MANIFEST}" && -n "${PROFILE}" && -n "${ROOT}" ]] || usage

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
WORK_DIR="$(mktemp -d)"
PLAN_FILE="${WORK_DIR}/deployment-plan.json"
CONFTEST_OUTPUT="${WORK_DIR}/conftest-result.json"
trap 'rm -rf "${WORK_DIR}"' EXIT

command -v conftest >/dev/null 2>&1 || {
  echo "error: conftest is required (https://www.conftest.dev/install/) and was not found on PATH" >&2
  exit 2
}

echo "1/3 Building the deployment plan (profile: ${PROFILE})..."
python3 "${SCRIPT_DIR}/build_deployment_plan.py" --manifest "${MANIFEST}" --profile "${PROFILE}" --root "${ROOT}" > "${PLAN_FILE}"

echo "2/3 Evaluating the Conftest policy (policy/governance-contract)..."
conftest_exit=0
conftest test --policy "${REPO_ROOT}/policy/governance-contract" --output json "${PLAN_FILE}" > "${CONFTEST_OUTPUT}" || conftest_exit=$?

echo "3/3 Recording evidence..."
outcome="allowed"
[[ "${conftest_exit}" -eq 0 ]] || outcome="denied"
source_commit="$(git -C "${REPO_ROOT}" rev-parse HEAD 2>/dev/null || echo unknown)"
policy_schema_revision="$(git -C "${REPO_ROOT}" log -1 --format=%H -- schemas/governance-contract policy/governance-contract 2>/dev/null || echo unknown)"

evidence="$(python3 "${SCRIPT_DIR}/build_evidence.py" \
  --plan "${PLAN_FILE}" \
  --conftest-result "${CONFTEST_OUTPUT}" \
  --source-commit "${source_commit}" \
  --policy-schema-revision "${policy_schema_revision}" \
  --outcome "${outcome}")"

if [[ -n "${EVIDENCE_OUT}" ]]; then
  printf '%s\n' "${evidence}" > "${EVIDENCE_OUT}"
else
  printf '%s\n' "${evidence}"
fi

if [[ "${conftest_exit}" -ne 0 ]]; then
  cat "${CONFTEST_OUTPUT}" >&2
  echo "DENIED: one or more required checks failed. See the evidence artifact for detail." >&2
  exit 1
fi
echo "ALLOWED: every expected agent has a valid contract with every required control complete."
