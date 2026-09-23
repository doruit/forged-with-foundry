"""Capture a Teams card, Foundry portal page, or similar UI as demo proof.

One-time authoring tool, not a runtime dependency of any control's demo.
Subcommands are split so the browser can stay open across separate
invocations while a human signs in interactively in between:

  launch   Start a visible system Chrome with remote debugging enabled and
           navigate to Teams (or another --url). Never automates, stores,
           or requests Microsoft Entra credentials -- exits immediately,
           leaving the browser open for you to sign in and navigate to the
           target page at your own pace.
  goto     Open a new tab at a different URL in that same already-running,
           already-signed-in browser, instead of calling 'launch' again.
           'launch' always starts a brand-new, empty Chrome profile, so a
           second 'launch' forces signing in again from scratch; 'goto'
           reuses the existing session so you only sign in once per browser
           session, even across a Teams capture and a Foundry portal
           capture.
  capture  Reconnect to that already-running Chrome, locate the smallest
           element containing --match, and screenshot its bounding box
           directly to --out. This crops out personal navigation and
           tenant chrome by construction (only the matched element is
           captured) instead of a manual full-window screenshot.

Setup (author-only; do not add to any control's requirements.txt):

    .venv/bin/pip install playwright

Uses your already-installed system Chrome (--channel chrome) by default, so
no Playwright browser-binary download is required -- useful on a network
that blocks Playwright's own CDN (cdn.playwright.dev). Pass --channel ''
to use Playwright's bundled Chromium instead, which does require
`python -m playwright install chromium` first.

Usage:

    .venv/bin/python scripts/capture_teams_card.py launch
    # ... sign in, open the Workflows chat, confirm the card is visible ...
    .venv/bin/python scripts/capture_teams_card.py capture \\
        --match "VAL-002" \\
        --out controls/value_adoption_and_finops/VAL-002_benefits_realisation_gap/media/teams-cards-both-decisions.png

If no element containing --match is found, `capture` falls back to a
full-viewport screenshot and prints a warning -- crop and mask it manually
before adding it to the repository, following
.github/instructions/screenshot-capture-workflow.instructions.md.
"""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

TEAMS_URL = "https://teams.microsoft.com"
DEBUG_PORT = 9333
STATE_FILE = Path(tempfile.gettempdir()) / "fwf-capture-teams-card.json"


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    launch = sub.add_parser("launch", help="Open a visible Chrome window for interactive sign-in")
    launch.add_argument("--url", default=TEAMS_URL, help="Page to open (default: Teams web app)")
    launch.add_argument("--channel", default="chrome",
                        help="'chrome' or 'msedge' use an already-installed system browser "
                             "(no download required); pass '' for Playwright's bundled "
                             "Chromium, which requires `python -m playwright install chromium` "
                             "first and is blocked on networks that don't allow "
                             "cdn.playwright.dev.")

    capture = sub.add_parser("capture", help="Screenshot the target card from the running browser")
    capture.add_argument("--match", required=True,
                         help="Visible text uniquely identifying the target card, e.g. 'VAL-002'")
    capture.add_argument("--out", required=True, type=Path,
                         help="Destination PNG path; parent directories are created if needed")
    capture.add_argument("--levels", type=int, default=4,
                         help="Ancestor levels to walk up from the matched text before "
                              "screenshotting, to capture the whole card rather than a text "
                              "fragment (default: 4; adjust if the crop is too tight or too wide)")

    goto = sub.add_parser("goto", help="Open a new tab at a URL in the already-running, already-signed-in browser")
    goto.add_argument("url", help="Page to open, e.g. a Foundry portal or Teams URL")

    sub.add_parser("close", help="Close the browser started by 'launch'")
    return parser


CHROME_PATHS = {
    "chrome": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "msedge": "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
}


def cmd_launch(args: argparse.Namespace) -> int:
    # Spawn the browser as a genuinely independent OS process, not through
    # Playwright's launch_persistent_context: that ties the browser's
    # lifecycle to Playwright's Node.js driver process, which is itself a
    # child of this script and gets torn down (taking the browser with it)
    # the moment this script exits. start_new_session detaches fully so the
    # browser survives after this one-shot CLI invocation returns.
    channel = args.channel or "chrome"
    exe = CHROME_PATHS.get(channel)
    if not exe or not Path(exe).exists():
        print(f"Could not find a '{channel}' executable at the expected macOS path "
              f"({exe}). Pass --channel chrome or --channel msedge.", file=sys.stderr)
        return 1

    profile_dir = tempfile.mkdtemp(prefix="fwf-capture-profile-")
    process = subprocess.Popen(
        [exe, f"--remote-debugging-port={DEBUG_PORT}", f"--user-data-dir={profile_dir}",
         "--no-first-run", "--no-default-browser-check", args.url],
        start_new_session=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    # Give Chrome a moment to actually start listening on the debug port
    # before any 'capture' invocation tries to connect to it.
    import urllib.request
    for _ in range(20):
        try:
            urllib.request.urlopen(f"http://localhost:{DEBUG_PORT}/json/version", timeout=0.5)
            break
        except OSError:
            time.sleep(0.5)
    else:
        print("Chrome did not open its debug port in time; it may still be starting -- "
              "try 'capture' anyway in a few seconds.", file=sys.stderr)

    STATE_FILE.write_text(json.dumps({"port": DEBUG_PORT, "profile_dir": profile_dir, "pid": process.pid}))

    print(f"Opened {args.url} in a visible Chrome window (pid {process.pid}, "
          f"remote debugging on :{DEBUG_PORT}). It runs independently of this "
          "script -- closing this terminal will not close it.")
    print("Sign in interactively, open the Workflows chat, and make sure the target")
    print("card is visible on screen. Then run:")
    print('  .venv/bin/python scripts/capture_teams_card.py capture --match "<text>" --out <path>')
    return 0


def _connect(playwright):
    if not STATE_FILE.exists():
        print("No running capture session found. Run the 'launch' subcommand first.", file=sys.stderr)
        return None
    state = json.loads(STATE_FILE.read_text())
    try:
        return playwright.chromium.connect_over_cdp(f"http://localhost:{state['port']}")
    except Exception as error:
        print(f"Could not reconnect to the browser on port {state['port']} ({error}). "
              "It may have been closed manually; run 'launch' again.", file=sys.stderr)
        return None


def cmd_capture(args: argparse.Namespace) -> int:
    from playwright.sync_api import sync_playwright

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = _connect(playwright)
        if browser is None:
            return 1
        page = browser.contexts[0].pages[-1]

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
    return 0


def cmd_goto(args: argparse.Namespace) -> int:
    """Reuse the already-launched, already-signed-in browser instead of a fresh profile.

    Each 'launch' starts a brand-new, empty Chrome profile, so switching
    pages by relaunching forces sign-in again every time. Opening a new tab
    in the same running browser keeps whatever Entra/Teams session is
    already active in it.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = _connect(playwright)
        if browser is None:
            return 1
        page = browser.contexts[0].new_page()
        page.goto(args.url)
        print(f"Opened {args.url} in a new tab of the already-running browser.")
        print("Sign in if prompted, then run 'capture' as usual.")
    return 0


def cmd_close(_args: argparse.Namespace) -> int:
    if not STATE_FILE.exists():
        print("No running capture session found.")
        return 0
    state = json.loads(STATE_FILE.read_text())
    try:
        subprocess.run(["pkill", "-f", f"remote-debugging-port={state['port']}"], check=False)
    finally:
        STATE_FILE.unlink(missing_ok=True)
    print("Closed the capture browser session.")
    return 0


def main() -> int:
    args = create_parser().parse_args()
    return {"launch": cmd_launch, "capture": cmd_capture, "goto": cmd_goto, "close": cmd_close}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
