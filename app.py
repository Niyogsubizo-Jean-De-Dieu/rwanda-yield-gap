"""
Open the Rwanda Yield Gap Explorer dashboard on your own machine.

    python3 app.py            # then open http://localhost:8000 (opens automatically)

Only Python's standard library is needed. The same dashboard (docs/index.html + docs/data.js) is published
online with GitHub Pages; see README.md. To refresh the numbers after rerunning the model:

    python3 src/build_dashboard_data.py
"""
import functools
import http.server
import socketserver
import sys
import threading
import webbrowser
from pathlib import Path

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
DOCS = Path(__file__).resolve().parent / "docs"


def main():
    if not (DOCS / "data.js").exists():
        sys.exit("docs/data.js is missing: run  python3 src/build_dashboard_data.py  first.")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DOCS))
    with socketserver.TCPServer(("127.0.0.1", PORT), handler) as httpd:
        url = f"http://localhost:{PORT}/"
        print(f"Rwanda Yield Gap Explorer running at {url}  (Ctrl+C to stop)")
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
