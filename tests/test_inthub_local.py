from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
import zipfile

from apps.inthub_local import launcher
from scripts.build_inthub_local import build_release_asset


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


def test_build_inthub_local_release_asset(tmp_path):
    result = build_release_asset(output_dir=tmp_path, hub_version="0.2.0-test")
    zip_path = Path(result["zip_path"])

    assert zip_path.exists()
    with zipfile.ZipFile(zip_path) as bundle:
        names = set(bundle.namelist())
        assert "inthub-local.pyz" in names
        assert "inthub-local" in names
        assert "inthub-local.cmd" in names
        assert "README.txt" in names

        pyz_bytes = bundle.read("inthub-local.pyz")
        with zipfile.ZipFile(BytesIO(pyz_bytes)) as pyz:
            pyz_names = set(pyz.namelist())
            assert "__main__.py" in pyz_names
            assert "apps/inthub_api/server.py" in pyz_names
            assert "apps/inthub_local/launcher.py" in pyz_names
            assert "apps/inthub_web/static/index.html" in pyz_names
