#!/usr/bin/env python3
"""Local preview server for the built site.

The built pages use root-absolute links prefixed with the deploy path
(e.g. /experiential-design-index/firms/...), so serving _site/ at the
server root breaks every internal link, and file:// doesn't work at all.
This server mounts _site/ at that same path locally so the site browses
exactly as it will when deployed.

Usage:
    python scripts/serve.py            # serve on port 8000, open browser
    python scripts/serve.py --port 8080
    python scripts/serve.py --no-open

Rebuild first (python scripts/build_site.py) to pick up data changes.
"""

import argparse
import functools
import http.server
import pathlib
import sys
import webbrowser

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from build_site import BASE, SITE  # single knob: SITE_URL in build_site.py


class BasePathHandler(http.server.SimpleHTTPRequestHandler):
    """Serve _site/ mounted at BASE instead of the server root."""

    def translate_path(self, path):
        # Strip query/fragment the same way the parent class does.
        path = path.split("?", 1)[0].split("#", 1)[0]
        if path == BASE or path.startswith(BASE + "/"):
            path = path[len(BASE):] or "/"
            return str(SITE / path.lstrip("/"))
        # Anything outside the base path 404s via a nonexistent file --
        # except "/", which redirects to the site home (see do_GET).
        return str(SITE / "__outside_base_path__")

    def do_GET(self):
        if self.path in ("/", ""):
            self.send_response(302)
            self.send_header("Location", f"{BASE}/index.html")
            self.end_headers()
            return
        super().do_GET()

    def log_message(self, fmt, *args):
        pass  # keep the console quiet; errors still surface as 404 pages


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-open", action="store_true",
                    help="don't open the browser automatically")
    args = ap.parse_args()

    if not (SITE / "index.html").exists():
        sys.exit("_site/ is missing or empty -- run scripts/build_site.py first.")

    url = f"http://localhost:{args.port}{BASE}/index.html"
    with http.server.ThreadingHTTPServer(("127.0.0.1", args.port), BasePathHandler) as httpd:
        print(f"Serving {SITE} at {url}  (Ctrl+C to stop)")
        if not args.no_open:
            webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
