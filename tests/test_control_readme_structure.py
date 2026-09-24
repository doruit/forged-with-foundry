import re
import struct
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CONTROLS_ROOT = REPOSITORY_ROOT / "controls"
THEMEPACK_ROOT = REPOSITORY_ROOT / "media" / "themepack"
BRAND_COLORS = (
    "#6E56CF",
    "#3B82F6",
    "#00D4FF",
    "#A855F7",
    "#0D1117",
    "#1F2937",
    "#22C55E",
    "#F59E0B",
)
# Keep in lockstep with docs/control-readme-template.md and
# scripts/scaffold_controls.py's template; a change here without updating
# both has silently drifted before (regressed once via an unrelated commit).
REQUIRED_SECTIONS = (
    "## Table of contents",
    "## Overview",
    "## Control contract",
    "## Control objective",
    "## Logical design",
    "## Demo infrastructure setup (simplified)",
    "## Implementation",
    "## Demo\n",
    "## Evidence and observability",
    "## Security and privacy",
    "## Validation",
    "## Cleanup",
    "## References",
)
IMPLEMENTED_STATUS = re.compile(r"> \*\*Status:\*\* (?:Implemented|Validated)")
COMMUNITY_DEMO_SECTIONS = (
    "## Demo profile",
    "## Demo scope",
    "### Core demo",
    "### Intentional simplifications",
    "### What this demo proves",
    "### What this demo does not prove",
    "## Demo\n",
)


def control_readmes() -> list[Path]:
    return sorted(CONTROLS_ROOT.glob("*/*/README.md"))


def repository_readmes() -> list[Path]:
    excluded_parts = {".git", ".pytest_cache", "__pycache__", "node_modules"}
    return sorted(
        readme
        for readme in REPOSITORY_ROOT.rglob("README.md")
        if not any(
            part in excluded_parts or part.startswith(".venv")
            for part in readme.relative_to(REPOSITORY_ROOT).parts
        )
    )


def has_valid_table_of_contents(content: str) -> bool:
    toc_matches = list(re.finditer(r"^## Table of contents$", content, re.MULTILINE))
    if len(toc_matches) != 1:
        return False

    toc_position = toc_matches[0].start()
    section_positions = [
        match.start()
        for match in re.finditer(
            r"^## (?!Table of contents$).+$",
            content,
            re.MULTILINE,
        )
    ]
    populated_toc = re.search(
        r"^## Table of contents\n\n(?:[*-] \[[^\n]+\]\(#[^)]+\)\n)+",
        content,
        re.MULTILINE,
    )

    return bool(populated_toc) and all(
        toc_position < section_position for section_position in section_positions
    )


def implemented_control_readmes() -> list[Path]:
    return [
        readme
        for readme in control_readmes()
        if IMPLEMENTED_STATUS.search(readme.read_text(encoding="utf-8"))
    ]


def png_width(path: Path) -> int:
    with path.open("rb") as image:
        signature = image.read(24)

    assert signature[:8] == b"\x89PNG\r\n\x1a\n", path
    assert signature[12:16] == b"IHDR", path
    return struct.unpack(">I", signature[16:20])[0]


def test_catalog_contains_expected_control_count() -> None:
    assert len(control_readmes()) == 161


def test_every_control_readme_uses_standard_section_order() -> None:
    for readme in control_readmes():
        content = readme.read_text(encoding="utf-8")
        positions = [content.find(section) for section in REQUIRED_SECTIONS]

        assert all(position >= 0 for position in positions), readme
        assert positions == sorted(positions), readme


def test_given_repository_readmes_when_checked_then_each_has_table_of_contents() -> None:
    # Arrange
    readmes = repository_readmes()

    # Act
    invalid = [
        readme
        for readme in readmes
        if not has_valid_table_of_contents(readme.read_text(encoding="utf-8"))
    ]

    # Assert
    assert not invalid, invalid


def test_every_control_readme_contains_at_least_one_mermaid_diagram() -> None:
    for readme in control_readmes():
        content = readme.read_text(encoding="utf-8")

        assert content.count("```mermaid") >= 1, readme


def test_implemented_demos_explain_their_scope_in_a_consistent_order() -> None:
    implemented = implemented_control_readmes()

    assert len(implemented) == 11
    for readme in implemented:
        content = readme.read_text(encoding="utf-8")
        positions = [content.find(section) for section in COMMUNITY_DEMO_SECTIONS]

        assert all(position >= 0 for position in positions), readme
        assert positions == sorted(positions), readme


def test_root_readme_links_every_implemented_demo() -> None:
    root_readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")

    for readme in implemented_control_readmes():
        relative = readme.relative_to(REPOSITORY_ROOT).as_posix()
        assessment = readme.with_name("ASSESSMENT.md").relative_to(REPOSITORY_ROOT).as_posix()

        assert f"]({relative})" in root_readme, readme
        assert f"]({relative}#demo)" in root_readme, readme
        assert f"]({relative}#demo-scope)" in root_readme, readme
        assert f"]({assessment})" in root_readme, readme


def test_every_control_readme_uses_brand_assets_and_palette() -> None:
    # docs/control-readme-template.md's Demo infrastructure setup (simplified)
    # diagram is the only one of the two canonical Mermaid diagrams whose
    # classDef block declares #1F2937 ("neutral"); Logical design's four
    # classDefs cover the other seven BRAND_COLORS on their own. A control may
    # replace Demo infrastructure setup (simplified) with a pre-rendered image
    # instead of a classDef'd flowchart (see scripts/render_architecture_diagram.py,
    # used when real service icons communicate the building blocks better than
    # a colored box); such a control has no classDef left to declare #1F2937
    # and is not required to invent one.
    infra_only_colors = {"#1F2937"}
    required_without_infra_diagram = set(BRAND_COLORS) - infra_only_colors

    for readme in control_readmes():
        content = readme.read_text(encoding="utf-8")

        assert "../../../media/themepack/" in content, readme
        assert "fwf-footer.png" in content, readme

        infra_section = re.search(
            r"^## Demo infrastructure setup \(simplified\)$(.*?)^## ", content, re.DOTALL | re.MULTILINE
        )
        has_infra_diagram = bool(infra_section) and "```mermaid" in infra_section.group(1)
        required_colors = set(BRAND_COLORS) if has_infra_diagram else required_without_infra_diagram
        assert all(color in content for color in required_colors), readme


def test_documentation_image_paths_resolve() -> None:
    readmes = [
        REPOSITORY_ROOT / "README.md",
        REPOSITORY_ROOT / "infra" / "README.md",
        REPOSITORY_ROOT / "docs" / "control-readme-template.md",
        *control_readmes(),
    ]

    for readme in readmes:
        content = readme.read_text(encoding="utf-8")
        images = re.findall(
            r'<img\s+src="([^"]+)"[^>]*\swidth="(\d+)"[^>]*>', content
        )
        assert images, readme
        for source, declared_width in images:
            image_path = (readme.parent / source).resolve()
            assert image_path.is_file(), (readme, source)
            assert int(declared_width) == png_width(image_path), (readme, source)


def test_themepack_contains_expected_assets() -> None:
    expected = {
        "fwf-banner-trans.png",
        "fwf-badge-small-one-control-a-week.png",
        "fwf-badge-small-only-logo.png",
        "fwf-picture-badge.png",
        "fwf-social.png",
        "fwf-footer.png",
    }

    assert {path.name for path in THEMEPACK_ROOT.glob("*.png")} == expected
