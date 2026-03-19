"""HTTP server for the IntHub V1 API."""

import argparse
import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from apps.inthub_api.common import APIError
from apps.inthub_api.ingest import link_project, store_sync_batch
from apps.inthub_api.queries import (
    get_decision_detail,
    get_intent_detail,
    get_snap_detail,
    list_projects,
    project_handoff,
    project_overview,
    search_project,
)

STATIC_DIR = Path(__file__).resolve().parents[1] / "inthub_web" / "static"


def _json_success(result):
    return {"ok": True, "result": result}


def _json_error(code, message, details=None):
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
    }


def _env_flag(name, default=False):
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def make_handler(
    db_path,
    serve_web=False,
    public_api_base_url=None,
    default_project_id=None,
    web_static_dir=None,
):
    root = Path(web_static_dir or STATIC_DIR).resolve()

    class IntHubHandler(BaseHTTPRequestHandler):
        server_version = "IntHubAPI/0.1"

        def _send_json(self, status, payload):
            body = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
            self._send_bytes(status, body, "application/json; charset=utf-8")

        def _send_bytes(self, status, body, content_type):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.end_headers()
            self.wfile.write(body)

        def _request_base_url(self):
            if public_api_base_url:
                return public_api_base_url.rstrip("/")
            proto = self.headers.get("X-Forwarded-Proto", "http")
            host = self.headers.get("Host")
            if not host:
                host = f"{self.server.server_address[0]}:{self.server.server_address[1]}"
            return f"{proto}://{host}"

        def _send_file(self, path):
            body = path.read_bytes()
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            if content_type.startswith("text/") or content_type in {
                "application/javascript",
                "application/json",
            }:
                content_type = f"{content_type}; charset=utf-8"
            self._send_bytes(200, body, content_type)

        def _serve_index(self):
            self._send_file(root / "index.html")

        def _serve_web(self, path):
            if path == "/config.json":
                self._send_json(
                    200,
                    {
                        "apiBaseUrl": self._request_base_url(),
                        "defaultProjectId": default_project_id,
                    },
                )
                return True

            if path == "/" or (not Path(path).suffix and not path.startswith("/api/")):
                self._serve_index()
                return True

            candidate = (root / path.lstrip("/")).resolve()
            try:
                candidate.relative_to(root)
            except ValueError as exc:
                raise APIError("OBJECT_NOT_FOUND", f"Asset {path} not found.", status=404) from exc
            if candidate.is_file():
                self._send_file(candidate)
                return True
            return False

        def _read_json_body(self):
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8") if length else "{}"
            try:
                return json.loads(raw or "{}")
            except json.JSONDecodeError as exc:
                raise APIError(
                    "INVALID_INPUT",
                    "Request body must be valid JSON.",
                    status=400,
                    details={"error": str(exc)},
                ) from exc

        def _handle_api_error(self, exc):
            self._send_json(exc.status, _json_error(exc.code, exc.message, exc.details))

        def _route_post(self, path):
            payload = self._read_json_body()
            if path == "/api/v1/hub/link":
                result = link_project(
                    db_path=db_path,
                    project_name=payload.get("project_name"),
                    repo=payload.get("repo", {}),
                    workspace_id=payload.get("workspace", {}).get("workspace_id"),
                )
                self._send_json(200, _json_success(result))
                return

            if path == "/api/v1/sync-batches":
                result = store_sync_batch(db_path=db_path, payload=payload)
                self._send_json(200, _json_success(result))
                return

            raise APIError("OBJECT_NOT_FOUND", f"Endpoint {path} not found.", status=404)

        def _route_get(self, path, query):
            if path == "/api/v1/projects":
                self._send_json(200, _json_success(list_projects(db_path)))
                return

            if path.startswith("/api/v1/projects/") and path.endswith("/overview"):
                project_id = path.split("/")[4]
                self._send_json(200, _json_success(project_overview(db_path, project_id)))
                return

            if path.startswith("/api/v1/projects/") and path.endswith("/handoff"):
                project_id = path.split("/")[4]
                self._send_json(200, _json_success(project_handoff(db_path, project_id)))
                return

            if path.startswith("/api/v1/intents/"):
                remote_object_id = path.split("/")[4]
                self._send_json(200, _json_success(get_intent_detail(db_path, remote_object_id)))
                return

            if path.startswith("/api/v1/decisions/"):
                remote_object_id = path.split("/")[4]
                self._send_json(200, _json_success(get_decision_detail(db_path, remote_object_id)))
                return

            if path.startswith("/api/v1/snaps/"):
                remote_object_id = path.split("/")[4]
                self._send_json(200, _json_success(get_snap_detail(db_path, remote_object_id)))
                return

            if path == "/api/v1/search":
                project_id = query.get("project_id", [None])[0]
                if not project_id:
                    raise APIError(
                        "INVALID_INPUT",
                        "Missing query parameter 'project_id'.",
                        status=400,
                    )
                search_query = query.get("q", [""])[0]
                self._send_json(200, _json_success(search_project(db_path, project_id, search_query)))
                return

            raise APIError("OBJECT_NOT_FOUND", f"Endpoint {path} not found.", status=404)

        def do_POST(self):
            parsed = urlparse(self.path)
            try:
                self._route_post(parsed.path)
            except APIError as exc:
                self._handle_api_error(exc)
            except Exception as exc:  # pragma: no cover - defensive fallback
                self._send_json(
                    500,
                    _json_error("INTERNAL_ERROR", "Unhandled server error.", {"error": str(exc)}),
                )

        def do_GET(self):
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/healthz":
                    self._send_json(
                        200,
                        _json_success(
                            {
                                "service": "inthub-api",
                                "serve_web": serve_web,
                            }
                        ),
                    )
                    return

                if parsed.path.startswith("/api/"):
                    self._route_get(parsed.path, parse_qs(parsed.query))
                    return

                if serve_web and self._serve_web(parsed.path):
                    return

                self._route_get(parsed.path, parse_qs(parsed.query))
            except APIError as exc:
                self._handle_api_error(exc)
            except Exception as exc:  # pragma: no cover - defensive fallback
                self._send_json(
                    500,
                    _json_error("INTERNAL_ERROR", "Unhandled server error.", {"error": str(exc)}),
                )

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.end_headers()

        def log_message(self, _format, *_args):
            return

    return IntHubHandler


def run_server(
    host,
    port,
    db_path,
    serve_web=False,
    public_api_base_url=None,
    default_project_id=None,
    web_static_dir=None,
):
    server = ThreadingHTTPServer(
        (host, port),
        make_handler(
            db_path,
            serve_web=serve_web,
            public_api_base_url=public_api_base_url,
            default_project_id=default_project_id,
            web_static_dir=web_static_dir,
        ),
    )
    web_status = " + Web" if serve_web else ""
    print(f"IntHub API{web_status} listening on http://{host}:{server.server_port} using {db_path}")
    server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description="Run the IntHub V1 API server.")
    parser.add_argument("--host", default=os.getenv("INTHUB_HOST", "127.0.0.1"))
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", os.getenv("INTHUB_PORT", "8000"))),
    )
    parser.add_argument("--db-path", default=os.getenv("INTHUB_DB_PATH", ".inthub/inthub.db"))
    parser.add_argument(
        "--serve-web",
        action="store_true",
        default=_env_flag("INTHUB_SERVE_WEB", False),
    )
    parser.add_argument("--public-api-base-url", default=os.getenv("INTHUB_API_BASE_URL"))
    parser.add_argument("--default-project-id", default=os.getenv("INTHUB_DEFAULT_PROJECT_ID"))
    parser.add_argument("--web-static-dir", default=os.getenv("INTHUB_WEB_STATIC_DIR"))
    args = parser.parse_args()
    run_server(
        args.host,
        args.port,
        args.db_path,
        serve_web=args.serve_web,
        public_api_base_url=args.public_api_base_url,
        default_project_id=args.default_project_id,
        web_static_dir=args.web_static_dir,
    )


if __name__ == "__main__":
    main()
