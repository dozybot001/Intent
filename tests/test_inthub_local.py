from contextlib import contextmanager
from pathlib import Path

from apps.inthub_local import launcher


def test_local_launcher_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    parser = launcher.build_parser()
    args = parser.parse_args([])

    assert args.host == "127.0.0.1"
    assert args.port == 7210
    assert Path(args.db_path) == tmp_path / ".inthub" / "inthub.db"


def test_run_local_opens_browser_and_creates_db_dir(monkeypatch, tmp_path):
    opened = []
    captured = {}

    @contextmanager
    def fake_static_dir():
        static_dir = tmp_path / "static"
        static_dir.mkdir()
        yield static_dir

    class FakeServer:
        server_port = 7210

        def serve_forever(self):
            captured["served"] = True

        def server_close(self):
            captured["closed"] = True

    def fake_build_local_server(host, port, db_path, default_project_id=None, web_static_dir=None):
        captured["host"] = host
        captured["port"] = port
        captured["db_path"] = Path(db_path)
        captured["default_project_id"] = default_project_id
        captured["web_static_dir"] = Path(web_static_dir)
        return FakeServer()

    monkeypatch.setattr(launcher, "resolve_static_dir", fake_static_dir)
    monkeypatch.setattr(launcher, "build_local_server", fake_build_local_server)

    db_path = tmp_path / "state" / "inthub.db"
    launcher.run_local(
        db_path=db_path,
        default_project_id="proj_demo",
        open_browser=True,
        browser_opener=opened.append,
    )

    assert opened == ["http://127.0.0.1:7210"]
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 7210
    assert captured["db_path"] == db_path
    assert captured["default_project_id"] == "proj_demo"
    assert captured["web_static_dir"] == tmp_path / "static"
    assert captured["served"] is True
    assert captured["closed"] is True
    assert db_path.parent.is_dir()


