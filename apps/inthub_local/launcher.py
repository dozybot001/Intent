"""Launcher for a local IntHub instance."""

import argparse
from contextlib import contextmanager
from importlib import resources
from pathlib import Path
import webbrowser

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
