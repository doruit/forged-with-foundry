"""Render a draw.io (mxGraph XML) architecture diagram to a static PNG.

One-time authoring tool, not a runtime dependency of any control's demo.
Companion to render_architecture_diagram.py (Mermaid): use this one instead
when a diagram needs official icons from the large Azure Public Service
Icons set or another asset in media/icons/, since draw.io ships proper
layout control and this repository already indexes that icon set (see
scripts/index_azure_icons.py) -- no CORS-server workaround or icon-pack
build step needed, unlike the Mermaid architecture-beta pipeline.

How this works: the installed VS Code "Draw.io Integration" extension
(hediet.vscode-drawio) bundles the actual diagrams.net web app locally.
This script serves that bundle over a throwaway local HTTP server (the app
needs http:// or https://, not file://, for its own internal resource
fetches), loads it in a headless browser, and drives it with draw.io's
documented "embed mode" postMessage protocol
(https://www.drawio.com/doc/faq/embed-mode): an iframe posts {event:"init"}
when ready, the parent replies with {action:"load", xml:...}, the iframe
confirms with {event:"load"}, and the parent then requests
{action:"export", format:"xmlpng", xml:...} -- which returns a PNG data URL
with the source XML embedded in its metadata, so the exported PNG is also
directly re-openable and re-editable in the VS Code extension (open the
committed media/*.png itself, not just the .drawio source).

Icon references: write the .drawio source with a placeholder instead of a
real image style value --

    style="shape=image;image=icon:media/icons/Azure_Public_Service_Icons/Icons/ai + machine learning/038470523-icon-service-Foundry-Agent-Service.svg;..."

-- and this script resolves each icon:<path> (relative to the .drawio
file's own directory) to a `data:image/svg+xml,<percent-encoded-svg>` URI
before rendering. This must be percent-encoded *without* base64: mxGraph's
style parser does a naive `style.split(';')` (confirmed by reading
mxgraph/src/view/mxStylesheet.js in the bundled extension, 2026-09-24), so
a raw `;` anywhere in an embedded value -- including the one in every
`data:image/svg+xml;base64,` prefix -- silently truncates it and renders a
broken-image glyph. A comma-form data URI with every character percent-
encoded (no `;base64,` segment, and no literal `;` from the SVG's own
markup either, since encoding covers that too) has no raw semicolon to
trip over.

Setup (author-only, per machine): none beyond what capture_teams_card.py
already needs (Playwright with a system Chrome channel) -- this script does
not add a new dependency, just a new use of one already in .venv.

Usage:

    .venv/bin/python scripts/render_drawio_diagram.py \\
        --input controls/<category>/<ID>/docs/architecture.drawio \\
        --output controls/<category>/<ID>/media/architecture.png

If Playwright's managed Chromium is not installed (common on a network-
restricted machine), this defaults to reusing the system Chrome via
--channel chrome, matching capture_teams_card.py's own default.
"""

import argparse
import base64
import functools
import http.server
import json
import re
import socket
import sys
import tempfile
import threading
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright

ICON_PLACEHOLDER = re.compile(r"icon:([^;\"]+\.svg)")

WRAPPER_TEMPLATE = """<!doctype html>
<html><body style="margin:0">
<iframe id="drawio" src="http://127.0.0.1:{port}/index.html?embed=1&proto=json&spin=1&ui=min"
        style="width:{width}px;height:{height}px;border:0"></iframe>
<script>
window.__diagramXml = {xml_json};
window.__exportData = null;
window.addEventListener("message", function(evt) {{
    var data = evt.data;
    if (typeof data === "string") {{ try {{ data = JSON.parse(data); }} catch (e) {{ return; }} }}
    var iframe = document.getElementById("drawio").contentWindow;
    if (data.event === "init") {{
        iframe.postMessage(JSON.stringify({{action: "load", xml: window.__diagramXml}}), "*");
    }} else if (data.event === "load") {{
        iframe.postMessage(JSON.stringify({{
            action: "export", format: "xmlpng", xml: window.__diagramXml,
            background: {background_json}, scale: {scale}
        }}), "*");
    }} else if (data.event === "export") {{
        window.__exportData = data.data;
    }}
}});
</script>
</body></html>
"""


def find_drawio_webapp() -> Path | None:
    candidates = sorted(
        Path.home().glob(".vscode*/extensions/hediet.vscode-drawio-*/drawio/src/main/webapp")
    )
    return candidates[-1] if candidates else None


def expand_icon_placeholders(xml: str, base_dir: Path) -> str:
    def replace(match: re.Match) -> str:
        relative = match.group(1)
        svg_path = (base_dir / relative).resolve()
        if not svg_path.is_file():
            raise FileNotFoundError(f"Icon referenced by the diagram not found: {svg_path}")
        svg_text = svg_path.read_text(encoding="utf-8")
        return "data:image/svg+xml," + quote(svg_text, safe="")

    return ICON_PLACEHOLDER.sub(replace, xml)


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True, type=Path,
                        help="Path to the .drawio (mxGraph XML) source")
    parser.add_argument("--output", required=True, type=Path, help="Destination .png path")
    parser.add_argument("--drawio-webapp", type=Path, default=find_drawio_webapp(),
                        help="Path to the bundled draw.io webapp directory "
                             "(default: auto-detected from the installed VS Code extension)")
    parser.add_argument("--background", default="#ffffff",
                        help="Background color, e.g. #ffffff or transparent (default: #ffffff)")
    parser.add_argument("--scale", type=int, default=2, help="Export scale factor (default: 2)")
    parser.add_argument("--width", type=int, default=1400, help="Iframe viewport width (default: 1400)")
    parser.add_argument("--height", type=int, default=1000, help="Iframe viewport height (default: 1000)")
    parser.add_argument("--channel", default="chrome",
                        help="Playwright browser channel (default: chrome, i.e. the system "
                             "install -- pass '' to use Playwright's own managed Chromium)")
    parser.add_argument("--timeout", type=int, default=20000, help="Timeout in ms (default: 20000)")
    return parser


def main() -> int:
    args = create_parser().parse_args()
    if not args.input.is_file():
        print(f"Input file not found: {args.input}", file=sys.stderr)
        return 1
    if args.drawio_webapp is None or not args.drawio_webapp.is_dir():
        print("Could not find the bundled draw.io webapp. Install the 'Draw.io Integration' "
              "VS Code extension (hediet.vscode-drawio) or pass --drawio-webapp explicitly.",
              file=sys.stderr)
        return 1

    xml = expand_icon_placeholders(args.input.read_text(encoding="utf-8"), args.input.parent)

    port = free_port()
    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=str(args.drawio_webapp))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    wrapper_html = WRAPPER_TEMPLATE.format(
        port=port, width=args.width, height=args.height,
        xml_json=json.dumps(xml), background_json=json.dumps(args.background), scale=args.scale,
    )

    wrapper_path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as handle:
            handle.write(wrapper_html)
            wrapper_path = Path(handle.name)

        with sync_playwright() as p:
            channel = args.channel or None
            browser = p.chromium.launch(headless=True, channel=channel)
            try:
                page = browser.new_page()
                page.goto(f"file://{wrapper_path}", wait_until="networkidle", timeout=args.timeout)
                page.wait_for_function("window.__exportData !== null", timeout=args.timeout)
                data_url = page.evaluate("window.__exportData")
            finally:
                browser.close()
    finally:
        server.shutdown()
        if wrapper_path is not None:
            wrapper_path.unlink(missing_ok=True)

    _header, b64_data = data_url.split(",", 1)
    args.output.write_bytes(base64.b64decode(b64_data))
    print(f"Rendered {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
