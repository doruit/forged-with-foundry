from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CONTROLS_ROOT = REPOSITORY_ROOT / "controls"
REQUIRED_SECTIONS = (
    "## Overview",
    "## Control contract",
    "## Control objective",
    "## Logical design",
    "## Infrastructure architecture",
    "## Implementation",
    "## Demo",
    "## Evidence and observability",
    "## Security and privacy",
    "## Validation",
    "## Cleanup",
    "## References",
)


def control_readmes() -> list[Path]:
    return sorted(CONTROLS_ROOT.glob("*/*/README.md"))


def test_catalog_contains_expected_control_count() -> None:
    assert len(control_readmes()) == 160


def test_every_control_readme_uses_standard_section_order() -> None:
    for readme in control_readmes():
        content = readme.read_text(encoding="utf-8")
        positions = [content.find(section) for section in REQUIRED_SECTIONS]

        assert all(position >= 0 for position in positions), readme
        assert positions == sorted(positions), readme


def test_every_control_readme_contains_both_mermaid_designs() -> None:
    for readme in control_readmes():
        content = readme.read_text(encoding="utf-8")

        assert content.count("```mermaid") >= 2, readme
