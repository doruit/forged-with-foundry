"""
Governance control demo entrypoint.

The `controls/` folder mirrors the Governance Signal / Control Repository
(see docs/Governance Signals Repo.pdf), organised as:

    controls/<category>/<control-id_control-name>/

Each control folder contains a README.md with its metadata (ID, lifecycle
phase, evidence, trigger/threshold, action/gate effect, accountable role)
and is the place to add the detection/evaluation implementation.

To (re)generate the folder structure from the repository data, run:

    python scripts/scaffold_controls.py
"""

if __name__ == "__main__":
    print(
        "Browse controls/ by category, then by control.\n"
        "Run 'python scripts/scaffold_controls.py' to regenerate the structure."
    )
