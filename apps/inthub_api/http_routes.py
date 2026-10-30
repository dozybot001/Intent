"""The API's reads and writes."""

import re
from intent_cli.store import StorageSecurityError, validate_object_id

from apps.inthub_api.common import APIError
from apps.inthub_api.history import link_history, push_history, read_history
from apps.inthub_api.limits import account_usage
from apps.inthub_api.projects import delete_project, export_project, rename_project, set_visibility, transfer_project
from apps.inthub_api.queries import SNAP_PAGE_MAX, get_decision_detail, get_intent_detail, get_snap_detail, list_projects, project_handoff, project_home, project_overview, project_snaps, search_project
from apps.inthub_api.revisions import project_revisions, revision_detail
from apps.inthub_api.teams import list_teams, preview_invite, team_detail
from apps.inthub_api.http_common import AUTH_BODY_LIMIT, REVISION_PAGE_MAX, _json_error, _json_success, _query_int


class HttpRoutes:
    def _handle_project_admin(self, path):
        account_id, body = self._browser_action()
        _, _, _, _, project_id, action = path.split("/")
        if action == "rename":
            result = rename_project(self.hub.db_path, project_id, body.get("name"), account_id)
        elif action == "delete":
            result = delete_project(self.hub.db_path, project_id, body.get("confirm"), account_id)
        elif not self.hub.auth_required:
            raise APIError("OBJECT_NOT_FOUND", "A hub without accounts has no owners or visibility.", 404)
        elif action == "visibility":
            result = set_visibility(self.hub.db_path, project_id, body.get("visibility"), body.get("confirm"), account_id, body.get("acknowledge_secrets"))
        else:
            result = transfer_project(self.hub.db_path, project_id, body.get("team_id"), body.get("confirm"), account_id)
        self._send_json(200, _json_success(result))

    def _handle_team_action(self, action, route_args):
        if not self.hub.auth_required:
            raise APIError("OBJECT_NOT_FOUND", "A hub without accounts has no teams.", 404)
        account_id, body = self._browser_action()
        self._send_json(200, _json_success(action(self.hub.db_path, account_id, body, *route_args)))

    def _handle_api_error(self, exc):
        headers = {"WWW-Authenticate": "Bearer"} if exc.status == 401 else None
        self._send_json(
            exc.status,
            _json_error(exc.code, exc.message, exc.details),
            headers,
        )

    def _route_post(self, path, account_id=None):
        # Match the route before reading any body.
        if path == "/api/v2/link":
            payload = self._read_json_body(limit=AUTH_BODY_LIMIT)
            self._send_json(200, _json_success(link_history(self.hub.db_path, payload.get("project_name"), account_id)))
            return
        if path == "/api/v2/history":
            self._send_json(200, _json_success(push_history(self.hub.db_path, self._read_json_body(), account_id)))
            return
        raise APIError("OBJECT_NOT_FOUND", f"Endpoint {path} not found.", status=404)

    def _route_get(self, path, query, account_id=None):
        if path == "/api/v2/history":
            self._send_json(200, _json_success(read_history(
                self.hub.db_path, query.get("project", [None])[0], account_id, project_id=query.get("project_id", [None])[0])), compact=True)
            return
        if path == "/api/v1/projects":
            self._send_json(
                200,
                _json_success(list_projects(self.hub.db_path, account_id=account_id)),
                compact=True,
            )
            return

        if path == "/api/v1/home":
            self._send_json(200, _json_success(project_home(self.hub.db_path, account_id=account_id)), compact=True)
            return

        if path == "/api/v1/teams" and self.hub.auth_required:
            self._send_json(200, _json_success(list_teams(self.hub.db_path, account_id)), compact=True)
            return

        if path == "/api/v1/usage" and self.hub.auth_required:
            self._send_json(200, _json_success(account_usage(self.hub.db_path, account_id)), compact=True)
            return

        if re.fullmatch(r"/api/v1/teams/[^/]+", path) and self.hub.auth_required:
            self._send_json(200, _json_success(team_detail(self.hub.db_path, path.split("/")[4], account_id)), compact=True)
            return

        if path == "/api/v1/invites/preview" and self.hub.auth_required:
            self._send_json(200, _json_success(preview_invite(self.hub.db_path, query.get("token", [None])[0], account_id)))
            return

        if path.startswith("/api/v1/projects/") and path.endswith("/overview"):
            project_id = path.split("/")[4]
            self._send_json(
                200,
                _json_success(
                    project_overview(self.hub.db_path, project_id, account_id=account_id)
                ),
                compact=True,
            )
            return

        if path.startswith("/api/v1/projects/") and path.endswith("/snaps"):
            project_id = path.split("/")[4]
            offset = _query_int(query, "offset", 0, 0, None)
            limit = _query_int(query, "limit", 50, 1, SNAP_PAGE_MAX)
            intent_id = query.get("intent_id", [None])[0]
            if intent_id is not None:
                try:
                    validate_object_id("intent", intent_id)
                except StorageSecurityError as exc:
                    raise APIError("INVALID_INPUT", "Invalid intent_id.", status=400) from exc
            self._send_json(
                200,
                _json_success(project_snaps(self.hub.db_path, project_id, offset, limit, intent_id, query.get("author", [None])[0], account_id=account_id)),
                compact=True,
            )
            return

        if path.startswith("/api/v1/projects/") and path.endswith("/revisions"):
            offset = _query_int(query, "offset", 0, 0, None)
            limit = _query_int(query, "limit", 30, 1, REVISION_PAGE_MAX)
            self._send_json(200, _json_success(project_revisions(self.hub.db_path, path.split("/")[4], offset, limit, account_id=account_id)), compact=True)
            return

        if re.fullmatch(r"/api/v1/projects/[^/]+/revisions/[^/]+", path):
            _, _, _, _, project_id, _, revision = path.split("/")
            self._send_json(200, _json_success(revision_detail(self.hub.db_path, project_id, revision, account_id=account_id)), compact=True)
            return

        if path.startswith("/api/v1/projects/") and path.endswith("/export"):
            self._send_json(200, _json_success(export_project(self.hub.db_path, path.split("/")[4], account_id=account_id)))
            return

        if path.startswith("/api/v1/projects/") and path.endswith("/handoff"):
            project_id = path.split("/")[4]
            self._send_json(
                200,
                _json_success(
                    project_handoff(self.hub.db_path, project_id, account_id=account_id)
                ),
                compact=True,
            )
            return

        if path.startswith("/api/v1/intents/"):
            remote_object_id = path.split("/")[4]
            self._send_json(
                200,
                _json_success(
                    get_intent_detail(self.hub.db_path, remote_object_id, account_id=account_id)
                ),
                compact=True,
            )
            return

        if path.startswith("/api/v1/decisions/"):
            remote_object_id = path.split("/")[4]
            self._send_json(
                200,
                _json_success(
                    get_decision_detail(self.hub.db_path, remote_object_id, account_id=account_id)
                ),
                compact=True,
            )
            return

        if path.startswith("/api/v1/snaps/"):
            remote_object_id = path.split("/")[4]
            self._send_json(
                200,
                _json_success(
                    get_snap_detail(self.hub.db_path, remote_object_id, account_id=account_id)
                ),
                compact=True,
            )
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
            self._send_json(
                200,
                _json_success(
                    search_project(
                        self.hub.db_path,
                        project_id,
                        search_query,
                        account_id=account_id,
                    )
                ),
                compact=True,
            )
            return

        raise APIError("OBJECT_NOT_FOUND", f"Endpoint {path} not found.", status=404)
