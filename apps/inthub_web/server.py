"""Static server for the read-only IntHub web app."""

import argparse
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


STATIC_DIR = Path(__file__).with_name("static")


def make_handler(api_base_url, default_project_id=None, static_dir=None):
    root = Path(static_dir or STATIC_DIR)
    config = {
        "apiBaseUrl": api_base_url.rstrip("/"),
        "defaultProjectId": default_project_id,
    }

    class IntHubWebHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root), **kwargs)

        def _send_json(self, payload):
            body = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _serve_index(self):
            index = root / "index.html"
            body = index.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/config.json":
                self._send_json(config)
                return

            if parsed.path == "/" or (not Path(parsed.path).suffix and not parsed.path.startswith("/config")):
                self._serve_index()
                return

            self.path = parsed.path
            super().do_GET()

        def log_message(self, _format, *_args):
            return

    return IntHubWebHandler


def run_server(host, port, api_base_url, default_project_id=None):
    server = ThreadingHTTPServer(
        (host, port),
        make_handler(api_base_url=api_base_url, default_project_id=default_project_id),
    )
    print(
        f"IntHub Web listening on http://{host}:{server.server_port} using API {api_base_url}"
    )
    server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description="Run the read-only IntHub web app.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3000)
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--default-project-id")
    args = parser.parse_args()
    run_server(
        host=args.host,
        port=args.port,
        api_base_url=args.api_base_url,
        default_project_id=args.default_project_id,
    )


if __name__ == "__main__":
    main()
