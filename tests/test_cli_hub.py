import json
import subprocess
from urllib.request import urlopen

from tests.cli_support import _add_github_remote, _get_json, _global_auth_env, _init_git_repo, _run, inthub_server, inthub_web_server, workspace


class TestHub:
    def test_hub_status_is_read_only_and_reports_missing_binding(
        self, workspace,
    ):
        auth_env = _global_auth_env(workspace)
        r = _run(workspace, "hub", "status", extra_env=auth_env)

        assert r["ok"] is True
        assert r["action"] == "hub.status"
        assert r["result"]["linked"] is False
        assert r["result"]["credential_available"] is False
        assert r["result"]["api_base_url"] == "https://inthub.tenon.asia"
        assert r["result"]["project_id"] is None
        assert r["result"]["revision"] is None
        assert not (workspace / ".intent" / "hub.json").exists()

    def test_global_auth_reused_by_two_projects_and_push_alias(
        self, workspace, inthub_server,
    ):
        auth_env = _global_auth_env(workspace)
        token = "ith_pat_test-global"
        login = _run(
            workspace,
            "auth",
            "login",
            "--api-base-url",
            inthub_server,
            "--token",
            token,
            extra_env=auth_env,
        )
        assert login["ok"] is True
        assert login["result"]["credential_store"] == "git-credential-helper"

        _add_github_remote(workspace)
        first_link = _run(workspace, "hub", "link", extra_env=auth_env)
        _run(workspace, "intent", "create", "First goal", extra_env=auth_env)
        first_push = _run(workspace, "push", extra_env=auth_env)
        assert first_push["ok"] is True
        assert first_push["action"] == "push"

        second = workspace / "second-project"
        second.mkdir()
        _init_git_repo(second)
        _add_github_remote(second, "https://github.com/example/second.git")
        assert _run(second, "init", extra_env=auth_env)["ok"] is True
        second_link = _run(second, "hub", "link", extra_env=auth_env)
        _run(second, "intent", "create", "Second goal", extra_env=auth_env)
        second_push = _run(second, "push", "--dry-run", extra_env=auth_env)

        assert first_link["result"]["api_base_url"] == inthub_server
        assert second_link["result"]["api_base_url"] == inthub_server
        assert first_link["result"]["project_id"] != second_link["result"]["project_id"]
        assert second_push["ok"] is True
        assert second_push["action"] == "push"
        assert second_push["result"]["dry_run"] is True

        hub_status = _run(workspace, "hub", "status", extra_env=auth_env)
        assert hub_status["result"]["linked"] is True
        assert hub_status["result"]["credential_available"] is True
        assert hub_status["result"]["revision"] == first_push["result"]["revision"]

        first_hub = json.loads((workspace / ".intent" / "hub.json").read_text())
        global_config = json.loads(
            (workspace / "global-intent-config" / "config.json").read_text()
        )
        assert "auth_token" not in first_hub
        assert token not in json.dumps(first_hub)
        assert token not in json.dumps(global_config)

        status = _run(workspace, "auth", "status", extra_env=auth_env)
        assert status["result"]["authenticated"] is True
        assert status["result"]["token_source"] == "credential-helper"

        logout = _run(workspace, "auth", "logout", extra_env=auth_env)
        assert logout["result"]["credential_removed"] is True
        status = _run(workspace, "auth", "status", extra_env=auth_env)
        assert status["result"]["authenticated"] is False

    def test_link_configures_and_binds(self, workspace, inthub_server):
        _add_github_remote(workspace)
        r = _run(workspace, "hub", "link", "--api-base-url", inthub_server,
                 "--project-name", "Demo Project")
        assert r["ok"] is True
        hub_config = json.loads((workspace / ".intent" / "hub.json").read_text())
        assert hub_config["api_base_url"] == inthub_server
        assert hub_config["project_id"]
        assert hub_config["project_name"] == "Demo Project"
        assert "workspace_id" not in hub_config

    def test_link_is_independent_of_git_remote(self, workspace, inthub_server):
        _add_github_remote(workspace, "git@example.com:foo/bar.git")
        r = _run(workspace, "hub", "link", "--api-base-url", inthub_server)
        assert r["ok"] is True
        assert r["result"]["format_version"] == 2

    def test_link_and_push_support_gitee_without_changing_origin(
        self, workspace, inthub_server,
    ):
        remote = "https://gitee.com/dozybot/WeSaid.git"
        _add_github_remote(workspace, remote)

        linked = _run(workspace, "hub", "link", "--api-base-url", inthub_server)
        pushed = _run(workspace, "push", "--dry-run")

        assert linked["ok"] is True
        assert linked["result"]["format_version"] == 2
        assert pushed["ok"] is True
        assert pushed["result"]["project_name"] == workspace.name
        configured = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=workspace,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert configured == remote

    def test_push_ignores_code_origin_changes(
        self, workspace, inthub_server,
    ):
        _add_github_remote(workspace)
        _run(workspace, "hub", "link", "--api-base-url", inthub_server)
        subprocess.run(
            ["git", "remote", "set-url", "origin", "git@gitee.com:example/demo.git"],
            cwd=workspace,
            capture_output=True,
            check=True,
        )

        r = _run(workspace, "push", "--dry-run")

        assert r["ok"] is True
        assert r["result"]["changed"] is False

    def test_sync_empty_history_needs_no_link(self, workspace, inthub_server):
        _add_github_remote(workspace)
        r = _run(workspace, "hub", "sync", "--api-base-url", inthub_server)
        assert r["ok"] is True
        assert r["result"]["changed"] is False

    def test_sync_dry_run(self, workspace, inthub_server):
        _add_github_remote(workspace)
        _run(workspace, "hub", "link", "--api-base-url", inthub_server,
             "--project-name", "Demo Project")
        _run(workspace, "intent", "create", "Goal")
        r = _run(workspace, "hub", "sync", "--dry-run")
        assert r["ok"] is True
        assert r["result"]["dry_run"] is True
        assert r["result"]["changed"] is True
        assert r["result"]["project_name"] == "Demo Project"

    def test_sync_updates_overview_and_handoff(self, workspace, inthub_server):
        _add_github_remote(workspace)
        _run(workspace, "hub", "link", "--api-base-url", inthub_server,
             "--project-name", "Demo Project")
        _run(workspace, "intent", "create", "Goal", "--why", "why?")
        _run(workspace, "decision", "create", "Rule", "--why", "reason")
        _run(workspace, "snap", "create", "Did X", "--intent", "intent-001",
             "--why", "details")
        r = _run(workspace, "hub", "sync")
        assert r["ok"] is True

        hub_config = json.loads((workspace / ".intent" / "hub.json").read_text())
        project_id = hub_config["project_id"]
        overview = _get_json(f"{inthub_server}/api/v1/projects/{project_id}/overview")
        assert overview["ok"] is True
        assert len(overview["result"]["active_intents"]) == 1
        assert overview["result"]["active_intents"][0]["id"] == "intent-001"
        assert len(overview["result"]["recent_snaps"]) == 1
        snap_remote_id = overview["result"]["recent_snaps"][0]["remote_id"]

        handoff = _get_json(f"{inthub_server}/api/v1/projects/{project_id}/handoff")
        assert handoff["ok"] is True
        assert handoff["result"]["intents"][0]["latest_snap"]["id"] == "snap-001"

        projects = _get_json(f"{inthub_server}/api/v1/projects")
        assert projects["ok"] is True
        assert projects["result"]["projects"][0]["id"] == project_id

        search = _get_json(f"{inthub_server}/api/v1/search?project_id={project_id}&q=Goal")
        assert search["ok"] is True
        assert search["result"]["matches"][0]["id"] == "intent-001"

        snap_detail = _get_json(f"{inthub_server}/api/v1/snaps/{snap_remote_id}")
        assert snap_detail["ok"] is True
        assert snap_detail["result"]["snap"]["id"] == "snap-001"

    def test_read_only_web_shell_serves_config(self, inthub_web_server, inthub_server):
        config = _get_json(f"{inthub_web_server}/config.json")
        assert config["apiBaseUrl"] == inthub_server
        assert config["authRequired"] is False
        assert config["authMode"] == "none"
        html = urlopen(f"{inthub_web_server}/").read().decode("utf-8")
        assert "IntHub" in html
        assert 'id="detail-content"' in html and 'id="search-dialog"' in html
        deep_link = urlopen(f"{inthub_web_server}/projects/demo").read().decode("utf-8")
        assert "IntHub" in deep_link
        assert "itt push" in urlopen(f"{inthub_web_server}/js/setup-guide.js").read().decode("utf-8")
        assert ".list-row" in urlopen(f"{inthub_web_server}/css/lists.css").read().decode("utf-8")
