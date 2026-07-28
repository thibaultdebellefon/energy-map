"""Serve the Energy Map frontend locally and open it in the browser.

    python app/serve.py            # http://localhost:8000
    python app/serve.py 8080       # custom port

Data must be built first: `python app/build_data.py`.
"""
from __future__ import annotations

import http.server
import socketserver
import sys
import webbrowser
from functools import partial
from pathlib import Path

PUBLIC = Path(__file__).resolve().parent / "public"


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    """Serve fresh assets every time — avoids stale app.js/style.css in the tab."""

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    if not (PUBLIC / "data.json").exists():
        raise SystemExit("Missing public/data.json — run: python app/build_data.py")
    handler = partial(NoCacheHandler, directory=str(PUBLIC))
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", port), handler) as httpd:
        url = f"http://localhost:{port}"
        print(f"Energy Map running at {url}  (Ctrl-C to stop)")
        try:
            webbrowser.open(url)
        except Exception:
            pass
        httpd.serve_forever()


if __name__ == "__main__":
    main()
