from contextlib import contextmanager
from pathlib import Path
import os
import subprocess
import sys

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




def test_local_hub_imports_without_hosted_only_dependencies(tmp_path):
    # `itt hub start` must work from a plain CLI install without server extras.
    script = """
import importlib.abc, sys
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name.split('.')[0] in {'httpx', 'authlib', 'psycopg', 'psycopg_binary'}:
            raise ImportError(name=name)
sys.meta_path.insert(0, Block())
from apps.inthub_local.launcher import build_local_server
server = build_local_server('127.0.0.1', 0, sys.argv[1])
server.server_close()
print('ok')
"""
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path / "inthub.db")],
        cwd=root, env={**os.environ, "PYTHONPATH": f"{root}{os.pathsep}{root / 'src'}"},
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"
