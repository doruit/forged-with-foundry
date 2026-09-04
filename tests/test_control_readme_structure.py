from pathlib import Path
import re
import struct


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
REQUIRED_SECTIONS = (
    "## Overview",
    "## Control contract",
    "## Control objective",
    "## Logical design",
    "## Infrastructure architecture",
    "## Implementation",
    "## Demo\n",
    "## Evidence and observability",
    "## Security and privacy",
    "## Validation",
    "## Cleanup",
    "## References",
)


def control_readmes() -> list[Path]:
    return sorted(CONTROLS_ROOT.glob("*/*/README.md"))


def png_width(path: Path) -> int:
    with path.open("rb") as image:
        signature = image.read(24)

    assert signature[:8] == b"\x89PNG\r\n\x1a\n", path
    assert signature[12:16] == b"IHDR", path
    return struct.unpack(">I", signature[16:20])[0]


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


def test_every_control_readme_uses_brand_assets_and_palette() -> None:
    for readme in control_readmes():
        content = readme.read_text(encoding="utf-8")

        assert "../../../media/themepack/" in content, readme
        assert "fwf-footer.png" in content, readme
        assert all(color in content for color in BRAND_COLORS), readme


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
        "fwf-badge-small-with-pic.png",
        "fwf-picture-badge.png",
        "fwf-social.png",
        "fwf-footer.png",
    }

    assert {path.name for path in THEMEPACK_ROOT.glob("*.png")} == expected
