"""HTTP server for the IntHub V1 API."""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from apps.inthub_api.common import APIError
from apps.inthub_api.ingest import link_project, store_sync_batch
from apps.inthub_api.queries import (
    get_snap_detail,
    get_decision_detail,
    get_intent_detail,
    list_projects,
    project_handoff,
    project_overview,
    search_project,
)


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


def make_handler(db_path):
    class IntHubHandler(BaseHTTPRequestHandler):
        server_version = "IntHubAPI/0.1"

        def _send_json(self, status, payload):
            body = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.end_headers()
            self.wfile.write(body)

        def _read_json_body(self):
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8") if length else "{}"
            try:
                return json.loads(raw or "{}")
            except json.JSONDecodeError as exc:
                raise APIError("INVALID_INPUT", "Request body must be valid JSON.", status=400, details={"error": str(exc)})

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
                    raise APIError("INVALID_INPUT", "Missing query parameter 'project_id'.", status=400)
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
                self._send_json(500, _json_error("INTERNAL_ERROR", "Unhandled server error.", {"error": str(exc)}))

        def do_GET(self):
            parsed = urlparse(self.path)
            try:
                self._route_get(parsed.path, parse_qs(parsed.query))
            except APIError as exc:
                self._handle_api_error(exc)
            except Exception as exc:  # pragma: no cover - defensive fallback
                self._send_json(500, _json_error("INTERNAL_ERROR", "Unhandled server error.", {"error": str(exc)}))

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.end_headers()

        def log_message(self, _format, *_args):
            return

    return IntHubHandler


def run_server(host, port, db_path):
    server = ThreadingHTTPServer((host, port), make_handler(db_path))
    print(f"IntHub API listening on http://{host}:{server.server_port} using {db_path}")
    server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description="Run the IntHub V1 API server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db-path", default=".inthub/inthub.db")
    args = parser.parse_args()
    run_server(args.host, args.port, args.db_path)


if __name__ == "__main__":
    main()
