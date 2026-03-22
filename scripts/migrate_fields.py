"""One-time migration: rename old field names to new ones across .intent/ and showcase/."""

import json
import sys
from pathlib import Path

RENAMES = {
    "title": "what",
    "rationale": "why",
    "summary": "why",
    "source_query": "query",
    "deprecated_reason": "reason",
}

REMOVE = {"feedback", "status"}  # only remove from snaps

FILL_DEFAULTS = {
    "query": "-",
    "why": "-",
    "origin": "",
}


def migrate_file(path):
    obj = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    is_snap = obj.get("object") == "snap"

    # Rename fields
    for old, new in RENAMES.items():
        if old in obj and new not in obj:
            obj[new] = obj.pop(old)
            changed = True
        elif old in obj and new in obj:
            obj.pop(old)
            changed = True

    # Remove snap-only legacy fields
    if is_snap:
        for field in REMOVE:
            if field in obj:
                obj.pop(field)
                changed = True
        # Add next if missing
        if "next" not in obj:
            obj["next"] = "-"
            changed = True

    # Fill missing shared fields with placeholder
    for field, default in FILL_DEFAULTS.items():
        if field not in obj and default:
            obj[field] = default
            changed = True

    if changed:
        path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    return changed


def migrate_dir(base):
    count = 0
    for subdir in ("intents", "snaps", "decisions"):
        d = base / subdir
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.json")):
            if migrate_file(f):
                count += 1
                print(f"  migrated: {f.name}")
    return count


def main():
    targets = []

    # .intent/
    intent_dir = Path(".intent")
    if intent_dir.is_dir():
        targets.append((".intent/", intent_dir))

    # showcase/
    showcase_dir = Path("showcase")
    if showcase_dir.is_dir():
        for project_dir in sorted(showcase_dir.iterdir()):
            if project_dir.is_dir() and (project_dir / "config.json").exists():
                targets.append((f"showcase/{project_dir.name}/", project_dir))

    if not targets:
        print("Nothing to migrate.")
        return

    total = 0
    for label, base in targets:
        print(f"[{label}]")
        n = migrate_dir(base)
        if n == 0:
            print("  (no changes)")
        total += n

    print(f"\nDone. {total} file(s) migrated.")


if __name__ == "__main__":
    main()
