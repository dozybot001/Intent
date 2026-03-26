"""Sync .intent/ data to showcase/intent-project/ on gh-pages branch.

Checks out gh-pages, updates showcase data, rebuilds static site,
and pushes back. Run from the repo root.

Note: showcase/intent-legacy/ contains frozen history from earlier schema
iterations and is NOT updated by this script.
"""

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / ".intent"
DIRS = ("intents", "snaps", "decisions")


def update():
    if not SOURCE.exists():
        print(f".intent/ not found at {SOURCE}")
        return

    # Fetch latest gh-pages showcase into a temp checkout
    subprocess.run(["git", "fetch", "origin", "gh-pages"], cwd=REPO_ROOT, check=True)
    subprocess.run(
        ["git", "checkout", "origin/gh-pages", "--", "showcase/"],
        cwd=REPO_ROOT, check=True,
    )

    target = REPO_ROOT / "showcase" / "intent-project"
    for name in DIRS:
        dst = target / name
        if dst.exists():
            shutil.rmtree(dst)
        src = SOURCE / name
        if src.exists():
            shutil.copytree(src, dst)

    config_src = SOURCE / "config.json"
    if config_src.exists():
        shutil.copy2(config_src, target / "config.json")

    intents = len(list((target / "intents").glob("*.json"))) if (target / "intents").exists() else 0
    snaps = len(list((target / "snaps").glob("*.json"))) if (target / "snaps").exists() else 0
    decisions = len(list((target / "decisions").glob("*.json"))) if (target / "decisions").exists() else 0
    print(f"Showcase updated: {intents} intents, {snaps} snaps, {decisions} decisions")

    # Build pages and push to gh-pages
    subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "build_pages.py")], cwd=REPO_ROOT, check=True)

    # Unstage showcase from main's index (it lives only on gh-pages)
    subprocess.run(["git", "reset", "HEAD", "--", "showcase/"], cwd=REPO_ROOT, check=True)
    shutil.rmtree(REPO_ROOT / "showcase")

    print("Run `git push` or let the workflow handle deployment.")


if __name__ == "__main__":
    update()
