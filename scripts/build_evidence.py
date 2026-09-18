#!/usr/bin/env python3
"""Builds the compact JSON evidence artifact for one deployment_gate.sh run.

This is evaluation evidence, not proof that the underlying business
assertions in any contract are true, and not a cryptographic deployment
attestation -- it records what the gate checked and what it decided, using
a plain source-commit + content-hash trail an organisation can correlate
with its own commit signing / branch protection, not a substitute for
those controls. See docs/governance-contract.md#policy-layer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def build_evidence(
    plan: dict,
    conftest_result: object,
    *,
    source_commit: str,
    policy_schema_revision: str,
    outcome: str,
) -> dict:
    contract_hashes = {}
    for agent in plan.get("discoveredAgents", []):
        if agent.get("hasContract"):
            try:
                contract_hashes[agent["agentId"]] = hashlib.sha256(
                    Path(agent["contractPath"]).read_bytes()
                ).hexdigest()
            except OSError:
                continue
    return {
        "sourceCommit": source_commit,
        "policySchemaRevision": policy_schema_revision,
        "policyProfile": plan.get("policyProfile"),
        "expectedAgents": plan.get("expectedAgents", []),
        "evaluatedControls": plan.get("requiredControls", []),
        "contractHashes": contract_hashes,
        "outcome": outcome,
        "conftestResult": conftest_result,
        "disclaimer": (
            "This is evaluation evidence -- it records what the gate checked and "
            "decided, not proof that the underlying business assertions are true, "
            "and not a cryptographic deployment attestation."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--conftest-result", required=True, type=Path)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--policy-schema-revision", required=True)
    parser.add_argument("--outcome", required=True, choices=["allowed", "denied"])
    args = parser.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    conftest_result = json.loads(args.conftest_result.read_text(encoding="utf-8"))
    evidence = build_evidence(
        plan,
        conftest_result,
        source_commit=args.source_commit,
        policy_schema_revision=args.policy_schema_revision,
        outcome=args.outcome,
    )
    print(json.dumps(evidence, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
