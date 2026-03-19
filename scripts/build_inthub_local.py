"""Build a distributable IntHub Local release asset."""

import argparse
import json
from pathlib import Path
import shutil
import tempfile
import zipapp
import zipfile


REPO_ROOT = Path(__file__).resolve().parents[1]
PYZ_NAME = "inthub-local.pyz"
UNIX_LAUNCHER_NAME = "inthub-local"
WINDOWS_LAUNCHER_NAME = "inthub-local.cmd"


def current_versions(repo_root):
    project_version = (repo_root / "VERSION").read_text(encoding="utf-8").strip()
    manifest_path = repo_root / "releases" / f"v{project_version}.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        "project_version": project_version,
        "hub_version": payload["hub"]["version"],
    }


def _copy_tree(src, dst):
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def stage_zipapp_tree(repo_root, staging_dir):
    apps_dst = staging_dir / "apps"
    apps_dst.mkdir(parents=True, exist_ok=True)
    shutil.copy2(repo_root / "apps" / "__init__.py", apps_dst / "__init__.py")
    _copy_tree(repo_root / "apps" / "inthub_api", apps_dst / "inthub_api")
    _copy_tree(repo_root / "apps" / "inthub_web", apps_dst / "inthub_web")
    _copy_tree(repo_root / "apps" / "inthub_local", apps_dst / "inthub_local")
    (staging_dir / "__main__.py").write_text(
        "from apps.inthub_local.launcher import main\n\nmain()\n",
        encoding="utf-8",
    )


def unix_launcher_text():
    return (
        "#!/bin/sh\n"
        'SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"\n'
        'exec "$SCRIPT_DIR/inthub-local.pyz" "$@"\n'
    )


def windows_launcher_text():
    return '@echo off\r\npy -3 "%~dp0\\inthub-local.pyz" %*\r\n'


def asset_readme_text(hub_version):
    return f"""IntHub Local {hub_version}

This asset starts a local IntHub instance on http://127.0.0.1:7210 by default.

Quick start:
1. Run ./inthub-local (or inthub-local.cmd on Windows)
2. In your project repo, run:
   itt hub login --api-base-url http://127.0.0.1:7210
   itt hub link
   itt hub sync
3. Open http://127.0.0.1:7210 in your browser

Requirements:
- Python 3.9+
- A local project repo that already uses Intent
- A GitHub origin remote for IntHub V1 linking
"""


def build_release_asset(repo_root=REPO_ROOT, output_dir=None, hub_version=None):
    repo_root = Path(repo_root).resolve()
    versions = current_versions(repo_root)
    hub_version = hub_version or versions["hub_version"]
    output_root = Path(output_dir or (repo_root / "dist")).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    asset_basename = f"inthub-local-v{hub_version}"
    pyz_path = output_root / f"{asset_basename}.pyz"
    zip_path = output_root / f"{asset_basename}.zip"

    with tempfile.TemporaryDirectory(prefix="inthub-local-build-") as tmpdir:
        staging_root = Path(tmpdir)
        zipapp_root = staging_root / "zipapp"
        bundle_root = staging_root / asset_basename
        zipapp_root.mkdir()
        bundle_root.mkdir()

        stage_zipapp_tree(repo_root, zipapp_root)
        zipapp.create_archive(zipapp_root, target=pyz_path, interpreter="/usr/bin/env python3")

        shutil.copy2(pyz_path, bundle_root / PYZ_NAME)
        unix_launcher = bundle_root / UNIX_LAUNCHER_NAME
        unix_launcher.write_text(unix_launcher_text(), encoding="utf-8")
        unix_launcher.chmod(0o755)
        (bundle_root / WINDOWS_LAUNCHER_NAME).write_text(windows_launcher_text(), encoding="utf-8")
        (bundle_root / "README.txt").write_text(asset_readme_text(hub_version), encoding="utf-8")

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(bundle_root.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(bundle_root))

    return {
        "hub_version": hub_version,
        "pyz_path": str(pyz_path),
        "zip_path": str(zip_path),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build an IntHub Local release asset.")
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "dist"))
    parser.add_argument("--hub-version")
    args = parser.parse_args(argv)
    result = build_release_asset(output_dir=args.output_dir, hub_version=args.hub_version)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
