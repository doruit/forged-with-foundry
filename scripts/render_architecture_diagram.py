"""Render an architecture-beta Mermaid diagram with real service icons to a static image.

One-time authoring tool, not a runtime dependency of any control's demo.
GitHub does not render Mermaid's icon packs for ``architecture-beta``
diagrams (confirmed 2026-09-23): a live code block using icon syntax like
``service agent(logos:microsoft-azure)`` shows a diagram with missing or
broken icons on GitHub, because GitHub's built-in Mermaid renderer never
calls ``registerIconPacks()``. This script pre-renders the diagram locally,
with the icon packs actually resolved by a real headless browser, to a
static SVG/PNG committed alongside the Mermaid source -- the same
"capture once, commit the artifact" pattern this repository already uses
for screenshots (see ``scripts/capture_teams_card.py``).

Setup (author-only; do not add to any control's requirements.txt or the
repository's Python dependencies):

    npm install --prefix .tooling/mermaid @mermaid-js/mermaid-cli @iconify-json/logos

Usage:

    python scripts/render_architecture_diagram.py \\
        --input controls/<category>/<ID>/docs/architecture.mmd \\
        --output controls/<category>/<ID>/media/architecture.png

Icon packs used by default:

* ``@iconify-json/logos`` -- official brand SVGs, installed locally.
  Confirmed present in this collection (2026-09-23): ``logos:azure``,
  ``logos:microsoft-azure``, ``logos:microsoft``, ``logos:microsoft-teams``,
  ``logos:github``, ``logos:github-actions``, ``logos:github-copilot``,
  ``logos:python``, ``logos:openai``, ``logos:microsoft-power-bi``. Check
  ``node_modules/@iconify-json/logos/icons.json`` for the full list before
  assuming an icon exists.
* ``azure:<name>`` -- a community Iconify-format Azure architecture icon set
  (per-service icons: Machine Learning, Key Vault, Storage, and similar),
  fetched directly by URL via ``--iconPacksNamesAndUrls`` -- confirmed
  reachable and renders real icons (2026-09-23), no local install needed.
  Browse available names at
  https://github.com/NakayamaKento/AzureIcons/blob/main/icons.json.

If a diagram needs an icon that is not in either pack, fall back to a plain
architecture-beta ``service`` with no icon reference (renders as a neutral
box) rather than inventing an icon name that will silently fail to resolve.

If this machine has no usable headless Chrome and cannot download one
(restricted network), point --chrome at an already-installed system browser
instead:

    --chrome "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
"""

import argparse
import functools
import http.server
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading

DEFAULT_AZURE_ICON_PACK = (
    "azure#https://raw.githubusercontent.com/NakayamaKento/AzureIcons/refs/heads/main/icons.json"
)


class _CORSHandler(http.server.SimpleHTTPRequestHandler):
    """Serve a local icon pack with the CORS header Mermaid's browser-side fetch requires.

    Confirmed 2026-09-23: a locally-built Iconify pack fetched by Mermaid
    inside Puppeteer's headless browser silently fails to resolve (icons
    render as "?") without ``Access-Control-Allow-Origin`` -- the fetch is
    treated as cross-origin and mermaid-cli swallows the resulting error.
    """

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def log_message(self, *_args) -> None:  # quiet by default
        pass


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True, type=Path,
                        help="Path to the architecture-beta Mermaid source (.mmd)")
    parser.add_argument("--output", required=True, type=Path,
                        help="Destination image path (.svg or .png)")
    parser.add_argument("--mmdc", type=Path, default=Path(".tooling/mermaid/node_modules/.bin/mmdc"),
                        help="Path to the mmdc executable (default: .tooling/mermaid install location)")
    parser.add_argument("--icon-packs", nargs="*", default=["@iconify-json/logos"],
                        help="Locally-installed npm icon packs to pass to --iconPacks")
    parser.add_argument("--extra-icon-urls", nargs="*", default=[DEFAULT_AZURE_ICON_PACK],
                        help="prefix#url pairs to pass to --iconPacksNamesAndUrls")
    parser.add_argument("--local-icon-pack", action="append", default=[],
                        help="prefix#path pairs for a locally-built Iconify JSON pack "
                             "(see build_icon_pack.py); served over a throwaway local "
                             "HTTP server with CORS enabled for the duration of this render")
    parser.add_argument("--background", default="white",
                        help="Background color: white, transparent, or a hex value (default: white)")
    parser.add_argument("--scale", type=int, default=2, help="Puppeteer scale factor (default: 2, for crisp text)")
    parser.add_argument("--chrome", help="Path to an existing Chrome/Edge executable to reuse, "
                                         "instead of Puppeteer's managed download")
    return parser


def main() -> int:
    args = create_parser().parse_args()
    if not args.input.is_file():
        print(f"Input file not found: {args.input}", file=sys.stderr)
        return 1
    if not args.mmdc.is_file():
        print(f"mmdc executable not found at {args.mmdc}. Run the setup command in this "
              "script's own docstring first.", file=sys.stderr)
        return 1

    extra_icon_urls = list(args.extra_icon_urls)
    servers = []
    for entry in args.local_icon_pack:
        prefix, _, path_str = entry.partition("#")
        pack_path = Path(path_str).resolve()
        if not pack_path.is_file():
            print(f"Local icon pack not found: {pack_path}", file=sys.stderr)
            return 1
        port = _free_port()
        handler = functools.partial(_CORSHandler, directory=str(pack_path.parent))
        server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        extra_icon_urls.append(f"{prefix}#http://127.0.0.1:{port}/{pack_path.name}")

    command = [
        str(args.mmdc), "-i", str(args.input), "-o", str(args.output),
        "-b", args.background, "-s", str(args.scale),
    ]
    if args.icon_packs:
        command += ["--iconPacks", *args.icon_packs]
    if extra_icon_urls:
        command += ["--iconPacksNamesAndUrls", *extra_icon_urls]

    puppeteer_config_path = None
    if args.chrome:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as handle:
            json.dump({"executablePath": args.chrome, "args": ["--no-sandbox"]}, handle)
            puppeteer_config_path = handle.name
        command += ["--puppeteerConfigFile", puppeteer_config_path]

    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    finally:
        if puppeteer_config_path:
            Path(puppeteer_config_path).unlink(missing_ok=True)
        for server in servers:
            server.shutdown()

    if result.returncode:
        print(result.stdout, file=sys.stdout)
        print(result.stderr, file=sys.stderr)
        return result.returncode

    print(f"Rendered {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
