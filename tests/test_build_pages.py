import json

from scripts import build_pages


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_static_intent_detail_contains_linked_decisions(tmp_path, monkeypatch):
    project_dir = tmp_path / "showcase" / "demo"
    intent = {
        "id": "intent-001",
        "object": "intent",
        "status": "active",
        "what": "Resume safely",
        "why": "A later session needs the boundary",
        "snap_ids": ["snap-001"],
        "decision_ids": ["decision-001"],
    }
    snap = {
        "id": "snap-001",
        "object": "snap",
        "intent_id": "intent-001",
        "what": "Reached the handoff boundary",
        "why": "Implementation can continue from here",
    }
    decision = {
        "id": "decision-001",
        "object": "decision",
        "status": "active",
        "what": "Keep the format backward compatible",
        "why": "Existing readers depend on it",
        "intent_ids": ["intent-001"],
    }
    _write_json(project_dir / "intents" / "intent-001.json", intent)
    _write_json(project_dir / "snaps" / "snap-001.json", snap)
    _write_json(project_dir / "decisions" / "decision-001.json", decision)

    output_dir = tmp_path / "pages"
    monkeypatch.setattr(build_pages, "OUT_DIR", output_dir)
    build_pages.build_project(project_dir)

    detail_path = (
        output_dir / "api" / "v1" / "intents"
        / "wks_showcase_demo__intent-001.json"
    )
    detail = json.loads(detail_path.read_text(encoding="utf-8"))["result"]
    assert detail["intent"] == intent
    assert detail["snaps"] == [snap]
    assert detail["decisions"] == [decision]

    handoff_path = (
        output_dir / "api" / "v1" / "projects"
        / "showcase_demo" / "handoff.json"
    )
    handoff = json.loads(handoff_path.read_text(encoding="utf-8"))["result"]
    assert handoff["intents"][0]["latest_snap"] == snap
    assert handoff["active_decisions"][0]["id"] == "decision-001"
