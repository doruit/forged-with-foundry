"""Capture a specific Teams Adaptive Card as proof a control's demo ran.

One-time authoring tool, not a runtime dependency of any control's demo.
Launches a visible (headed) Chromium browser and waits for you to sign in to
Teams interactively -- it never automates, stores, or requests Microsoft
Entra credentials. Once you confirm the target card is visible, it locates
the smallest element containing the given match text and screenshots that
element's bounding box directly to the destination path, which crops out
personal navigation and tenant chrome by construction (only the matched
element is captured) instead of a manual full-window screenshot.

Setup (author-only; do not add to any control's requirements.txt):

    .venv/bin/pip install playwright
    .venv/bin/python -m playwright install chromium

Usage:

    .venv/bin/python scripts/capture_teams_card.py \\
        --match "VAL-002" \\
        --out controls/value_adoption_and_finops/VAL-002_benefits_realisation_gap/media/teams-cards-both-decisions.png

If no element containing --match is found once you confirm readiness, the
script falls back to a full-viewport screenshot and prints a warning --
crop and mask it manually before adding it to the repository, following
.github/instructions/screenshot-capture-workflow.instructions.md.
"""

import argparse
from pathlib import Path
import sys

TEAMS_URL = "https://teams.microsoft.com"


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--match", required=True,
                        help="Visible text uniquely identifying the target card, e.g. 'VAL-002'")
    parser.add_argument("--out", required=True, type=Path,
                        help="Destination PNG path; parent directories are created if needed")
    parser.add_argument("--url", default=TEAMS_URL, help="Page to open (default: Teams web app)")
    parser.add_argument("--levels", type=int, default=4,
                        help="Ancestor levels to walk up from the matched text before "
                             "screenshotting, to capture the whole card rather than a text "
                             "fragment (default: 4; adjust if the crop is too tight or too wide)")
    return parser


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright is not installed. Run:\n"
              "  .venv/bin/pip install playwright\n"
              "  .venv/bin/python -m playwright install chromium", file=sys.stderr)
        return 1

    args = create_parser().parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        page.goto(args.url)

        print(f"Opened {args.url} in a visible browser window.")
        print("Sign in interactively, open the Workflows chat, and make sure the")
        print(f"card containing {args.match!r} is visible on screen.")
        input("Press Enter here once ready to capture... ")

        locator = page.get_by_text(args.match, exact=False).first
        try:
            locator.wait_for(state="visible", timeout=5000)
            target = locator
            for _ in range(args.levels):
                parent = target.locator("xpath=..")
                if parent.count() == 0:
                    break
                target = parent
            target.screenshot(path=str(args.out))
            print(f"Saved element screenshot to {args.out}")
        except Exception as error:
            print(f"Could not locate an element matching {args.match!r} ({error}).",
                  file=sys.stderr)
            print("Falling back to a full-viewport screenshot -- crop and mask it "
                  "manually before committing.", file=sys.stderr)
            page.screenshot(path=str(args.out))
            print(f"Saved full-viewport screenshot to {args.out}")

        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
