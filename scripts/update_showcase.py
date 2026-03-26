"""Sync .intent/ data to showcase/intent-project/ for distribution.

Note: showcase/intent-legacy/ contains frozen history from earlier schema
iterations and is NOT updated by this script.
"""

import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / ".intent"
TARGET = REPO_ROOT / "showcase" / "intent-project"
DIRS = ("intents", "snaps", "decisions")


def update():
    if not SOURCE.exists():
        print(f".intent/ not found at {SOURCE}")
        return

    for name in DIRS:
        dst = TARGET / name
        if dst.exists():
            shutil.rmtree(dst)
        src = SOURCE / name
        if src.exists():
            shutil.copytree(src, dst)

    config_src = SOURCE / "config.json"
    if config_src.exists():
        shutil.copy2(config_src, TARGET / "config.json")

    intents = len(list((TARGET / "intents").glob("*.json"))) if (TARGET / "intents").exists() else 0
    snaps = len(list((TARGET / "snaps").glob("*.json"))) if (TARGET / "snaps").exists() else 0
    decisions = len(list((TARGET / "decisions").glob("*.json"))) if (TARGET / "decisions").exists() else 0
    print(f"Showcase updated: {intents} intents, {snaps} snaps, {decisions} decisions")


if __name__ == "__main__":
    update()
