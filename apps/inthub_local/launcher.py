"""Launcher for a local IntHub instance."""

import argparse
from contextlib import contextmanager
from importlib import resources
import json
from pathlib import Path
import webbrowser

from apps.inthub_api.ingest import link_project, store_sync_batch
from apps.inthub_api.server import build_server

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7210


def default_db_path(home=None):
    root = Path(home).expanduser() if home is not None else Path.home()
    return root / ".inthub" / "inthub.db"


def public_base_url(host, port):
    public_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    return f"http://{public_host}:{port}"


@contextmanager
def resolve_static_dir():
    static_root = resources.files("apps.inthub_web").joinpath("static")
    with resources.as_file(static_root) as static_dir:
        yield Path(static_dir)


def build_local_server(host, port, db_path, default_project_id=None, web_static_dir=None):
    return build_server(
        host,
        port,
        str(db_path),
        serve_web=True,
        public_api_base_url=public_base_url(host, port),
        default_project_id=default_project_id,
        web_static_dir=str(web_static_dir) if web_static_dir is not None else None,
    )


def _load_showcase(db_path, showcase_dir):
    """Import showcase projects into IntHub on startup."""
    for project_dir in sorted(showcase_dir.iterdir()):
        if not project_dir.is_dir():
            continue
        config_path = project_dir / "config.json"
        if not config_path.exists():
            continue

        project_name = project_dir.name
        repo_id = f"showcase/{project_name}"
        repo = {
            "provider": "github",
            "repo_id": repo_id,
            "owner": "showcase",
            "name": project_name,
        }

        result = link_project(
            db_path=str(db_path),
            project_name=project_name,
            repo=repo,
            workspace_id=f"wks_showcase_{project_name}",
        )

        config = json.loads(config_path.read_text(encoding="utf-8"))
        intents = []
        snaps = []
        decisions = []

        for subdir, target in [("intents", intents), ("snaps", snaps), ("decisions", decisions)]:
            obj_dir = project_dir / subdir
            if obj_dir.is_dir():
                for f in sorted(obj_dir.iterdir()):
                    if f.suffix == ".json":
                        target.append(json.loads(f.read_text(encoding="utf-8")))

        # Use the latest object timestamp as generated_at
        all_objects = intents + snaps + decisions
        latest_ts = max((o.get("created_at", "") for o in all_objects), default="")

        payload = {
            "sync_batch_id": f"sync_showcase_{project_name}",
            "generated_at": latest_ts,
            "client": {"name": "showcase", "version": "0"},
            "project_id": result["project_id"],
            "repo": repo,
            "workspace": {"workspace_id": result["workspace_id"]},
            "git": {"branch": "main", "head_commit": "", "dirty": False, "remote_url": ""},
            "snapshot": {
                "intents": intents,
                "snaps": snaps,
                "decisions": decisions,
            },
        }

        batch = store_sync_batch(db_path=str(db_path), payload=payload)
        if not batch.get("duplicate"):
            print(f"  Showcase loaded: {project_name} ({len(intents)} intents, {len(snaps)} snaps, {len(decisions)} decisions)")


def run_local(
    host=DEFAULT_HOST,
    port=DEFAULT_PORT,
    db_path=None,
    default_project_id=None,
    open_browser=True,
    browser_opener=None,
):
    database_path = Path(db_path).expanduser() if db_path is not None else default_db_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)

    # Try package-relative showcase first, then cwd fallback
    package_showcase = Path(__file__).resolve().parents[2] / "showcase"
    cwd_showcase = Path.cwd() / "showcase"
    showcase_dir = package_showcase if package_showcase.is_dir() else cwd_showcase
    if showcase_dir.is_dir():
        _load_showcase(database_path, showcase_dir)

    with resolve_static_dir() as static_dir:
        server = build_local_server(
            host,
            port,
            database_path,
            default_project_id=default_project_id,
            web_static_dir=static_dir,
        )
        url = public_base_url(host, server.server_port)
        print(f"IntHub Local listening on {url} using {database_path}")
        if open_browser:
            opener = browser_opener or webbrowser.open
            opener(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()


def build_parser():
    parser = argparse.ArgumentParser(description="Run IntHub Local.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--db-path", default=str(default_db_path()))
    parser.add_argument("--default-project-id")
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Do not open the browser automatically.",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    run_local(
        host=args.host,
        port=args.port,
        db_path=args.db_path,
        default_project_id=args.default_project_id,
        open_browser=not args.no_open,
    )
