"""Build a local Iconify-format icon pack JSON from official brand SVG/PNG assets.

One-time authoring tool, not a runtime dependency of any control's demo. Use
this to turn hand-sourced official icons (for example downloaded from a
Microsoft brand/asset page) into a pack ``scripts/render_architecture_diagram.py``
can reference as ``--local-icon-pack <prefix>#<path-to-json>``.

Each source file becomes one icon, named after its filename (without
extension, non-alphanumeric characters replaced with ``-``):

* ``.svg`` files are inlined as-is: the outer ``<svg ...>`` wrapper is
  stripped and the inner markup becomes the icon's ``body``, with the
  original ``viewBox``/``width``/``height`` preserved.
* ``.png``/``.jpg`` files are embedded as a base64 data URI inside a single
  ``<image>`` element -- not a true vector icon, but it renders correctly in
  Mermaid's ``architecture-beta`` icon slots, confirmed 2026-09-23. Prefer a
  real ``.svg`` source when the brand page offers one.

Usage:

    python scripts/build_icon_pack.py \\
        --source-dir media/icons \\
        --output media/icons/fwf-icons.json \\
        --prefix fwf \\
        --icons ai-foundry.png ai-agents.svg

Omit ``--icons`` to include every ``.svg``/``.png``/``.jpg`` file directly in
``--source-dir`` (not recursive).

``--icons`` entries may include a subfolder, which is how to pull from the
official Azure Public Service Icons set at
``media/icons/Azure_Public_Service_Icons/Icons/`` (714 SVGs across ~29
category folders) -- search
``media/icons/Azure_Public_Service_Icons/icon-index.jsonl`` (built by
``scripts/index_azure_icons.py``) for a matching service, then pass its
``path`` field, for example::

    python scripts/build_icon_pack.py \\
        --source-dir media/icons/Azure_Public_Service_Icons/Icons \\
        --output media/icons/fwf-icons.json --prefix fwf \\
        --icons "compute/10021-icon-service-Virtual-Machine.svg"
"""

import argparse
import base64
import json
from pathlib import Path
import re
import sys

SLUG_PATTERN = re.compile(r"[^a-z0-9]+")
# Strips the official Azure Public Service Icons filename boilerplate (e.g.
# "10021-icon-service-Virtual-Machine" -> "Virtual-Machine") so icons built
# from that set (see scripts/index_azure_icons.py) get the same short,
# human-chosen key recorded as "slug" in its generated icon-index.jsonl,
# instead of the numeric id and "icon-service" noise becoming part of the key.
AZURE_ICON_SERVICE_PREFIX = re.compile(r"^\s*\d+\s*-icon-service-", re.IGNORECASE)


def slug(name: str) -> str:
    name = AZURE_ICON_SERVICE_PREFIX.sub("", name)
    return SLUG_PATTERN.sub("-", name.lower()).strip("-")


def svg_to_icon(path: Path) -> dict:
    text = path.read_text()
    match = re.search(r"<svg([^>]*)>(.*)</svg>", text, re.DOTALL)
    if not match:
        raise ValueError(f"{path}: could not find an <svg>...</svg> wrapper")
    attrs, inner = match.group(1), match.group(2).strip()
    width = re.search(r'width="([\d.]+)"', attrs)
    height = re.search(r'height="([\d.]+)"', attrs)
    icon = {"body": inner}
    if width:
        icon["width"] = float(width.group(1))
    if height:
        icon["height"] = float(height.group(1))
    return icon


def raster_to_icon(path: Path) -> dict:
    from PIL import Image

    with Image.open(path) as image:
        width, height = image.size
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode()
    body = f'<image href="data:{mime};base64,{encoded}" width="{width}" height="{height}"/>'
    return {"body": body, "width": width, "height": height}


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--prefix", required=True, help="Iconify prefix, referenced as <prefix>:<icon-name>")
    parser.add_argument("--icons", nargs="*", help="Specific filenames within --source-dir; default: all of them")
    parser.add_argument("--width", type=int, default=256, help="Pack-level default width (default: 256)")
    parser.add_argument("--height", type=int, default=256, help="Pack-level default height (default: 256)")
    return parser


def main() -> int:
    args = create_parser().parse_args()
    if args.icons:
        files = [args.source_dir / name for name in args.icons]
    else:
        files = sorted(p for p in args.source_dir.iterdir() if p.suffix.lower() in (".svg", ".png", ".jpg", ".jpeg"))

    icons = {}
    for path in files:
        if not path.is_file():
            print(f"Skipping missing file: {path}", file=sys.stderr)
            continue
        name = slug(path.stem)
        try:
            if path.suffix.lower() == ".svg":
                icons[name] = svg_to_icon(path)
            else:
                icons[name] = raster_to_icon(path)
        except Exception as error:  # noqa: BLE001 -- report and continue with the rest
            print(f"Skipping {path}: {error}", file=sys.stderr)

    if not icons:
        print("No icons produced; nothing written.", file=sys.stderr)
        return 1

    pack = {"prefix": args.prefix, "icons": icons, "width": args.width, "height": args.height}
    args.output.write_text(json.dumps(pack))
    print(f"Wrote {args.output} with {len(icons)} icon(s): {', '.join(sorted(icons))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
