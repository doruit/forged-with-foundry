"""Build a searchable index of the official Azure Public Service Icons set.

One-time/refresh authoring tool, not a runtime dependency of any control's
demo. `media/icons/Azure_Public_Service_Icons/Icons/` holds Microsoft's
official architecture icon set (714 SVGs across ~29 category folders,
downloaded from the Azure Architecture Center) -- too many to browse by hand
when picking an icon for a new `docs/architecture.mmd`. This script indexes
every SVG's category, official filename, and a cleaned display name into one
JSON Lines file so both a human and `scripts/build_icon_pack.py` callers can
grep it.

Usage:

    python scripts/index_azure_icons.py \\
        --source-dir media/icons/Azure_Public_Service_Icons/Icons \\
        --output media/icons/Azure_Public_Service_Icons/icon-index.jsonl

Re-run after adding or updating the icon set; the output is deterministic
(one line per SVG, sorted by relative path) so a re-run's diff shows only
real additions/removals.

Each line is a standalone JSON object:

    {"path": "ai + machine learning/00030-icon-service-Machine-Learning.svg",
     "category": "ai + machine learning", "id": "00030",
     "name": "Machine Learning", "slug": "machine-learning"}

Find a candidate icon with, for example:

    grep -i "machine learning" media/icons/Azure_Public_Service_Icons/icon-index.jsonl

Then build a local pack with the matched ``path`` and use ``slug`` as the
icon's name in `.mmd` (see scripts/build_icon_pack.py -- it strips the same
``<id>-icon-service-`` boilerplate when naming icons built from this set, so
the ``slug`` recorded here matches the key the pack will actually use):

    python scripts/build_icon_pack.py \\
        --source-dir media/icons/Azure_Public_Service_Icons/Icons \\
        --output media/icons/fwf-icons.json --prefix fwf \\
        --icons "ai + machine learning/00030-icon-service-Machine-Learning.svg"

Licensing note (not legal advice -- confirm with the appropriate function if
in doubt): the accompanying Azure_Icons_FAQ.pdf states these icons may only
represent the specific Microsoft product they were designed for, must not be
cropped/flipped/rotated/distorted, and must be labeled with the service's
full name near (not overlapping) the icon -- all satisfied by this
repository's existing render pipeline and diagram convention, but worth
re-checking against the Azure Architecture Center's brand guidelines before
using an icon in a new, different context.
"""

import argparse
import json
from pathlib import Path
import re
import sys

FILENAME_PATTERN = re.compile(r"^\s*(\d+)\s*-icon-service-(.+)$", re.IGNORECASE)


def parse_filename(stem: str) -> tuple[str, str] | None:
    match = FILENAME_PATTERN.match(stem)
    if not match:
        return None
    icon_id, name = match.groups()
    return icon_id, name.replace("-", " ").strip()


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source-dir", required=True, type=Path,
                        help="Root of the category-organized icon folders (e.g. .../Icons)")
    parser.add_argument("--output", required=True, type=Path,
                        help="Destination .jsonl path")
    return parser


def main() -> int:
    args = create_parser().parse_args()
    if not args.source_dir.is_dir():
        print(f"Source directory not found: {args.source_dir}", file=sys.stderr)
        return 1

    records = []
    unparsed = []
    for path in sorted(args.source_dir.rglob("*.svg")):
        relative = path.relative_to(args.source_dir)
        category = relative.parts[0] if len(relative.parts) > 1 else ""
        parsed = parse_filename(path.stem)
        if not parsed:
            unparsed.append(str(relative))
            continue
        icon_id, name = parsed
        records.append({
            "path": relative.as_posix(),
            "category": category,
            "id": icon_id,
            "name": name,
            "slug": slug(name),
        })

    with args.output.open("w") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")

    print(f"Wrote {args.output} with {len(records)} icon(s) across "
          f"{len({r['category'] for r in records})} categories")
    if unparsed:
        print(f"{len(unparsed)} file(s) did not match the expected naming "
              f"pattern and were skipped:", file=sys.stderr)
        for name in unparsed:
            print(f"  {name}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
