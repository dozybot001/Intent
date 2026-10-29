"""Readable output for people, the JSON contract for agents, and the log/show views."""

import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from intent_cli import output
from intent_cli.cli import _invoke
from intent_cli.store import _entry_order

ROOT = Path(__file__).resolve().parents[1]


def _itt(cwd, *args, env=None):
    environment = {**os.environ, "PYTHONPATH": os.pathsep.join([str(ROOT / "src"), str(ROOT)]), **(env or {})}
    return subprocess.run([sys.executable, "-m", "intent_cli", *args], cwd=cwd, capture_output=True, text=True, env=environment)


@pytest.fixture
def project(tmp_path):
    assert _itt(tmp_path, "init").returncode == 0
    _itt(tmp_path, "intent", "create", "Ship guest checkout", "--why", "Mobile buyers abandon at sign-up.")
    _itt(tmp_path, "snap", "create", "Guest flow works in staging", "--next", "Run the A/B test", "--blocker", "none")
    _itt(tmp_path, "snap", "create", "Verified: A/B test lifted conversion. Next: roll out to 100%.")
    _itt(tmp_path, "decision", "create", "Card payments only go through PaymentIntents", "--why", "One SCA path.")
    return tmp_path


class _Terminal(io.StringIO):
    def isatty(self):
        return True


def test_json_unless_a_person_is_at_a_terminal(monkeypatch):
    for name in ("ITT_FORMAT", *output.AGENT_ENVIRONMENT):
        monkeypatch.delenv(name, raising=False)
    output.set_format(None)
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    assert output.json_mode() is True  # pipes and subprocesses
    monkeypatch.setattr(sys, "stdout", _Terminal())
    assert output.json_mode() is False
    monkeypatch.setenv("CLAUDECODE", "1")
    assert output.json_mode() is True  # agent shells may allocate a terminal
    monkeypatch.setenv("ITT_FORMAT", "text")
    assert output.json_mode() is False
    output.set_format("json")
    assert output.json_mode() is True
    output.set_format(None)


def test_readable_views_and_errors_for_people(project):
    text = {"ITT_FORMAT": "text"}
    inspect = _itt(project, "inspect", env=text)
    assert inspect.returncode == 0 and not inspect.stdout.lstrip().startswith("{")
    assert "intent-001" in inspect.stdout and "Next" in inspect.stdout and "roll out to 100%" in inspect.stdout
    assert "decision-001" in inspect.stdout
    log = _itt(project, "log", env=text).stdout
    assert log.index("snap-002") < log.index("snap-001")
    assert "Next: Run the A/B test" in log
    show = _itt(project, "show", "intent-001", env=text).stdout
    assert "Snaps (2)" in show and "Decisions (1)" in show
    snap = _itt(project, "show", "snap-001", env=text).stdout  # checkpoint without --verified
    assert re.search(r"^ +Verified +Guest flow works in staging$", snap, re.M)
    failure = _itt(project, "show", "intent-404", env=text)
    assert failure.returncode == 1 and failure.stdout == ""
    assert failure.stderr.startswith("error: intent-404 not found.")
    forced = _itt(project, "--json", "show", "intent-001", env=text)
    assert json.loads(forced.stdout)["result"]["object"]["id"] == "intent-001"


def test_log_and_show_json_results(project):
    log = json.loads(_itt(project, "log", "-n", "1").stdout)["result"]
    assert [snap["id"] for snap in log["snaps"]] == ["snap-002"]
    assert log["total"] == 2 and log["has_more"] is True
    assert log["snaps"][0]["intent"] == {"id": "intent-001", "what": "Ship guest checkout", "status": "active"}
    every = json.loads(_itt(project, "log", "--all", "--intent", "intent-001").stdout)["result"]
    assert [snap["id"] for snap in every["snaps"]] == ["snap-002", "snap-001"] and every["has_more"] is False
    snap = json.loads(_itt(project, "show", "snap-001").stdout)["result"]
    assert snap["object"]["checkpoint"] == {"next": "Run the A/B test", "blocker": "none"}
    assert snap["intent"]["id"] == "intent-001"
    decision = json.loads(_itt(project, "show", "decision-001").stdout)["result"]
    assert [intent["id"] for intent in decision["intents"]] == ["intent-001"]
    assert json.loads(_itt(project, "show", "nonsense").stdout)["error"]["code"] == "INVALID_INPUT"
    assert json.loads(_itt(project, "log", "--intent", "intent-009").stdout)["error"]["code"] == "OBJECT_NOT_FOUND"


def test_inputs_and_unexpected_failures_stay_in_the_contract(project, capsys, monkeypatch):
    assert json.loads(_itt(project, "intent", "create", "   ").stdout)["error"]["code"] == "INVALID_INPUT"
    again = json.loads(_itt(project, "init").stdout)["error"]
    assert again["code"] == "ALREADY_EXISTS" and "maintenance on" in again["suggested_fix"]
    monkeypatch.delenv("ITT_DEBUG", raising=False)
    output.set_format("json")

    def broken(_args):
        raise ValueError("disk said no")

    with pytest.raises(SystemExit):
        _invoke(broken, None)
    error = json.loads(capsys.readouterr().out)["error"]
    assert error["code"] == "INTERNAL_ERROR" and "ValueError: disk said no" in error["message"]
    output.set_format(None)


def test_objects_list_in_numeric_order():
    names = [Path(name) for name in ("intent-1000.json", "intent-999.json", "intent-002.json")]
    assert [path.name for path in sorted(names, key=_entry_order)] == ["intent-002.json", "intent-999.json", "intent-1000.json"]
