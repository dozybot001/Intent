"""Relations between Intents, Decision sources, and the paged IntHub views."""

import copy
import json
import os
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path

import pytest

from apps.inthub_api.queries import project_overview, project_snaps, search_project
from apps.inthub_api.server import build_server
from intent_cli import relations, store
from intent_cli.hub.snapshots import SnapshotError, require_fast_forward, validate_snapshot
from intent_cli.maintenance_hooks import _context

ROOT = Path(__file__).resolve().parents[1]


def itt(cwd, *args):
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(ROOT / "src"), str(ROOT)]),
               INTENT_CONFIG_HOME=str(cwd.parent / "config"), GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    env.pop("INTHUB_TOKEN", None)
    result = subprocess.run([sys.executable, "-m", "intent_cli", *args], cwd=cwd, env=env, capture_output=True, text=True)
    payload = json.loads(result.stdout)
    assert result.returncode == (0 if payload["ok"] else 1), result.stderr
    return payload


def stored(project, intent_id):
    return json.loads((project / ".intent" / "intents" / f"{intent_id}.json").read_text(encoding="utf-8"))


def failure(payload, code):
    assert payload["ok"] is False and payload["error"]["code"] == code, payload
    return payload["error"]["message"]


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    assert itt(root, "init")["ok"]
    for what in ("Support mobile payments", "Upgrade the Stripe SDK"):
        assert itt(root, "intent", "create", what, "--why", "test")["ok"]
    return root


def test_relations_are_recorded_on_the_declaring_intent_and_absent_otherwise(project):
    created = itt(project, "intent", "create", "Add Apple Pay", "--part-of", "intent-001", "--depends-on", "intent-002")
    assert [(entry["type"], entry["intent"]) for entry in created["result"]["relations"]] == [
        ("part_of", "intent-001"), ("depends_on", "intent-002")]
    assert "relations" not in stored(project, "intent-001")  # plain intents keep the 7.1 shape
    shown = itt(project, "show", "intent-001")["result"]["relations"]
    assert shown == [{"type": "part_of", "direction": "in", "state": "in_progress",
                      "intent": {"id": "intent-003", "what": "Add Apple Pay", "status": "active"}}]
    entry = next(item for item in itt(project, "inspect")["active_intents"] if item["id"] == "intent-003")
    assert [(row["type"], row["state"]) for row in entry["relations"]] == [("part_of", "in_progress"), ("depends_on", "blocked")]
    assert itt(project, "doctor")["result"]["healthy"] is True


@pytest.mark.parametrize("args, code", [
    (("intent", "relate", "intent-001", "--depends-on", "intent-001"), "INVALID_RELATION"),
    (("intent", "relate", "intent-001", "--depends-on", "intent-404"), "OBJECT_NOT_FOUND"),
    (("intent", "relate", "intent-404", "--depends-on", "intent-001"), "OBJECT_NOT_FOUND"),
    (("intent", "create", "Twice", "--part-of", "intent-001", "--derived-from", "intent-002"), None),
])
def test_relation_input_errors_write_nothing(project, args, code):
    before = {path.name: path.read_bytes() for path in (project / ".intent" / "intents").iterdir()}
    if code is None:  # argparse rejects two parents before anything runs
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        assert subprocess.run([sys.executable, "-m", "intent_cli", *args], cwd=project, env=env,
                              capture_output=True).returncode != 0
    else:
        failure(itt(project, *args), code)
    assert {path.name: path.read_bytes() for path in (project / ".intent" / "intents").iterdir()} == before


def test_rules_one_relation_per_pair_one_parent_no_cycles(project):
    assert itt(project, "intent", "relate", "intent-001", "--depends-on", "intent-002")["ok"]
    assert "already related" in failure(itt(project, "intent", "relate", "intent-002", "--conflicts-with", "intent-001"), "INVALID_RELATION")
    assert itt(project, "intent", "create", "Part", "--part-of", "intent-001")["ok"]  # intent-003
    assert "already has a parent" in failure(itt(project, "intent", "relate", "intent-003", "--derived-from", "intent-002"), "INVALID_RELATION")
    assert itt(project, "intent", "create", "Sub-part", "--derived-from", "intent-003")["ok"]  # intent-004
    assert "cycle" in failure(itt(project, "intent", "relate", "intent-001", "--part-of", "intent-004"), "INVALID_RELATION")
    assert itt(project, "intent", "create", "Stage 2", "--succeeds", "intent-002")["ok"]  # intent-005
    assert itt(project, "intent", "create", "Stage 3", "--succeeds", "intent-005")["ok"]  # intent-006
    assert "cycle" in failure(itt(project, "intent", "relate", "intent-002", "--succeeds", "intent-006"), "INVALID_RELATION")
    assert itt(project, "intent", "done", "intent-002")["ok"]
    assert "ended" in failure(itt(project, "intent", "relate", "intent-006", "--part-of", "intent-002"), "INVALID_RELATION")


def test_unrelate_withdraws_on_whichever_side_declared_it(project):
    assert itt(project, "intent", "relate", "intent-002", "--depends-on", "intent-001")["ok"]
    withdrawn = itt(project, "intent", "unrelate", "intent-001", "intent-002")["result"]
    assert withdrawn["id"] == "intent-002" and "removed_at" in withdrawn["relation"]
    assert relations.active_entries(stored(project, "intent-002")) == []
    assert len(stored(project, "intent-002")["relations"]) == 1  # append-only: the record stays
    failure(itt(project, "intent", "unrelate", "intent-001", "intent-002"), "OBJECT_NOT_FOUND")
    assert itt(project, "intent", "relate", "intent-001", "--conflicts-with", "intent-002")["ok"]


def test_ending_into_a_successor_and_resolving_a_conflict(project):
    # intent-002 declared the conflict, so the record lives on the intent being cancelled.
    assert itt(project, "intent", "relate", "intent-002", "--conflicts-with", "intent-001")["ok"]
    cancelled = itt(project, "intent", "cancel", "intent-002", "--into", "intent-001", "--reason", "One approach")
    assert cancelled["result"]["successor"] == "intent-001" and cancelled["result"]["status"] == "cancelled"
    assert relations.active_entries(stored(project, "intent-002")) == []
    assert [(e["type"], e["intent"]) for e in relations.active_entries(stored(project, "intent-001"))] == [("succeeds", "intent-002")]
    assert itt(project, "doctor")["result"]["healthy"] is True
    assert itt(project, "intent", "create", "Part", "--part-of", "intent-001")["ok"]  # intent-003
    failure(itt(project, "intent", "done", "intent-003", "--into", "intent-001"), "INVALID_RELATION")
    assert stored(project, "intent-003")["status"] == "active"


def test_decision_source_is_optional_and_shown(project):
    sourced = itt(project, "decision", "create", "Payments use PaymentIntents", "--from", "intent-001")["result"]
    assert sourced["source_intent_id"] == "intent-001" and len(sourced["intent_ids"]) == 2  # still global
    assert itt(project, "show", "decision-001")["result"]["source_intent"]["id"] == "intent-001"
    plain = itt(project, "decision", "create", "Keep the API stable")["result"]
    assert "source_intent_id" not in plain
    assert itt(project, "show", "decision-002")["result"]["source_intent"] is None
    failure(itt(project, "decision", "create", "Orphan", "--from", "intent-404"), "OBJECT_NOT_FOUND")


def test_states_follow_both_statuses():
    def state(kind, subject, target):
        return relations.state(kind, {"status": subject}, {"status": target})
    assert [state("part_of", s, t) for s, t in (("active", "active"), ("done", "active"), ("cancelled", "active"), ("active", "done"))] == [
        "in_progress", "done", "dropped", "orphaned"]
    assert [state("depends_on", "active", t) for t in ("active", "done", "cancelled")] == ["blocked", "satisfied", "broken"]
    assert [state("succeeds", "active", t) for t in ("suspend", "cancelled")] == ["pending", "handed_over"]
    assert [state("conflicts_with", "active", t) for t in ("active", "done")] == ["unresolved", "resolved"]
    assert state("derived_from", "active", "active") is None


def test_doctor_reports_hand_edited_relation_problems(project):
    for subject, target in (("intent-001", "intent-002"), ("intent-002", "intent-001")):
        path = project / ".intent" / "intents" / f"{subject}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["relations"] = [{"type": "depends_on", "intent": target, "created_at": "2026-11-01T00:00:00+00:00"},
                             {"type": "succeeds", "intent": "intent-404", "created_at": "2026-11-01T00:00:00+00:00"}]
        path.write_text(json.dumps(data), encoding="utf-8")
    codes = {issue["code"] for issue in itt(project, "doctor")["result"]["issues"]}
    assert codes == {"INVALID_RELATION", "MISSING_REFERENCE"}


def test_hook_context_carries_relations(project):
    assert itt(project, "intent", "relate", "intent-002", "--depends-on", "intent-001")["ok"]
    graph = store.load_graph_once(project / ".intent")
    text = _context(project / ".intent", "turn", {"entry_error": None}, graph)
    records = json.loads(text[text.index("{"):])
    entry = next(item for item in records["active_intents"] if item["id"] == "intent-002")
    assert entry["relations"] == [{"type": "depends_on", "direction": "out", "intent": "intent-001", "state": "blocked"}]


def _snapshot():
    common = {"created_at": "2026-11-01T00:00:00+00:00", "why": "", "origin": "pytest"}
    intents = [{**common, "id": f"intent-00{n}", "object": "intent", "what": f"Goal {n}", "status": "active",
                "decision_ids": [], "snap_ids": []} for n in (1, 2)]
    return {"intents": intents, "snaps": [], "decisions": []}


def test_fast_forward_lets_relations_grow_but_never_rewrites_them():
    before = _snapshot()
    entry = {"type": "depends_on", "intent": "intent-001", "created_at": "2026-11-02T00:00:00+00:00"}
    grown = copy.deepcopy(before)
    grown["intents"][1]["relations"] = [entry]
    validate_snapshot(grown)
    require_fast_forward(before, grown)
    withdrawn = copy.deepcopy(grown)
    withdrawn["intents"][1]["relations"][0]["removed_at"] = "2026-11-03T00:00:00+00:00"
    require_fast_forward(grown, withdrawn)
    for broken in ({**entry, "type": "succeeds"}, None):
        rewritten = copy.deepcopy(withdrawn)
        rewritten["intents"][1]["relations"] = [broken] if broken else []
        with pytest.raises(SnapshotError):
            require_fast_forward(withdrawn, rewritten)
    restored = copy.deepcopy(withdrawn)
    del restored["intents"][1]["relations"][0]["removed_at"]
    with pytest.raises(SnapshotError):
        require_fast_forward(withdrawn, restored)
    # A finished intent may gain a successor record, and nothing else.
    done = copy.deepcopy(before)
    done["intents"][0]["status"] = "done"
    succeeded = copy.deepcopy(done)
    succeeded["intents"][0]["relations"] = [{**entry, "type": "succeeds", "intent": "intent-002"}]
    require_fast_forward(done, succeeded)
    renamed = copy.deepcopy(succeeded)
    renamed["intents"][0]["what"] = "Renamed"
    with pytest.raises(SnapshotError):
        require_fast_forward(succeeded, renamed)


@pytest.mark.parametrize("entry", [
    {"type": "blocks", "intent": "intent-001", "created_at": "x"},
    {"type": "depends_on", "intent": "snap-001", "created_at": "x"},
    {"type": "depends_on", "intent": "intent-001"},
])
def test_snapshots_reject_malformed_relations(entry):
    snapshot = _snapshot()
    snapshot["intents"][1]["relations"] = [entry]
    with pytest.raises(SnapshotError):
        validate_snapshot(snapshot)


@pytest.fixture
def hub(tmp_path):
    db = str(tmp_path / "hub.db")
    server = build_server("127.0.0.1", 0, db)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield db, f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_overview_is_capped_and_the_timeline_is_paged(hub, project):
    db, url = hub
    for number in range(1, 46):
        intent_id = "intent-001" if number % 3 else "intent-002"
        assert itt(project, "snap", "create", f"Checkpoint {number:02d}", "--intent", intent_id)["ok"]
    assert itt(project, "remote", "add", "origin", url, "--project", "paging")["ok"]
    project_id = itt(project, "push")["result"]["project_id"]

    overview = project_overview(db, project_id)
    assert len(overview["recent_snaps"]) == 20 and overview["total_snaps"] == 45
    assert overview["recent_snaps"][0]["what"] == "Checkpoint 45"
    page = project_snaps(db, project_id, offset=40, limit=10)
    assert [snap["what"] for snap in page["snaps"]][-1] == "Checkpoint 01" and page["has_more"] is False
    only = project_snaps(db, project_id, limit=200, intent_id="intent-002")
    assert only["total"] == 15 and {snap["intent_id"] for snap in only["snaps"]} == {"intent-002"}

    with urllib.request.urlopen(f"{url}/api/v1/projects/{project_id}/snaps?offset=5&limit=3") as response:
        body = json.load(response)["result"]
    assert [snap["what"] for snap in body["snaps"]] == ["Checkpoint 40", "Checkpoint 39", "Checkpoint 38"]
    for query in ("limit=0", "limit=201", "offset=-1", "limit=x", "intent_id=snap-001"):
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(f"{url}/api/v1/projects/{project_id}/snaps?{query}")
        assert error.value.code == 400

    found = search_project(db, project_id, "checkpoint")
    assert len(found["matches"]) == 45 and found["truncated"] is False
    assert itt(project, "snap", "create", "Checkpoint 46", "--intent", "intent-001")["ok"]
    for number in range(47, 52):
        assert itt(project, "snap", "create", f"Checkpoint {number}", "--intent", "intent-001")["ok"]
    assert itt(project, "push")["ok"]
    capped = search_project(db, project_id, "checkpoint")
    assert len(capped["matches"]) == 50 and capped["total"] == 51 and capped["truncated"] is True
