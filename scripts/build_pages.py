"""Build static GitHub Pages site from showcase/ data.

Reads all showcase projects, generates pre-computed API JSON responses,
and copies web assets to pages/ for static hosting.

Usage:
    python3 scripts/build_pages.py
"""

import json
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SHOWCASE_DIR = REPO_ROOT / "pages" / "showcase"
WEB_STATIC = REPO_ROOT / "apps" / "inthub_web" / "static"
OUT_DIR = REPO_ROOT / "pages"


def load_json_dir(directory: Path) -> list[dict]:
    """Load all JSON files from a directory, sorted by filename."""
    if not directory.exists():
        return []
    items = []
    for f in sorted(directory.glob("*.json")):
        items.append(json.loads(f.read_text()))
    return items


def wrap(result: dict | list) -> dict:
    """Wrap result in API response envelope."""
    return {"ok": True, "result": result}


def write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def build_project(project_dir: Path) -> dict:
    """Build all static JSON for one showcase project. Returns project info."""
    name = project_dir.name
    project_id = f"showcase_{name}"
    workspace_id = f"wks_showcase_{name}"

    intents = load_json_dir(project_dir / "intents")
    decisions = load_json_dir(project_dir / "decisions")
    snaps = load_json_dir(project_dir / "snaps")

    # Build lookup maps
    intent_map = {i["id"]: i for i in intents}
    decision_map = {d["id"]: d for d in decisions}
    snap_map = {s["id"]: s for s in snaps}

    # Classify intents
    active_intents = [i for i in intents if i.get("status") == "active"]
    other_intents = [i for i in intents if i.get("status") != "active"]

    # Classify decisions
    active_decisions = [d for d in decisions if d.get("status") == "active"]
    deprecated_decisions = [d for d in decisions if d.get("status") != "active"]

    # Add remote_id to all objects for sidebar rendering
    def with_remote(obj):
        return {**obj, "remote_id": f"{workspace_id}__{obj['id']}"}

    # --- Overview ---
    overview = {
        "project": {
            "id": project_id,
            "name": name,
            "repo": {"owner": "showcase", "name": name},
        },
        "workspaces": [
            {
                "workspace_id": workspace_id,
                "branch": "main",
                "dirty": False,
                "last_synced_at": _latest_date(intents + decisions + snaps),
            }
        ],
        "active_intents": [with_remote(i) for i in active_intents],
        "other_intents": [with_remote(i) for i in other_intents],
        "active_decisions": [with_remote(d) for d in active_decisions],
        "deprecated_decisions": [with_remote(d) for d in deprecated_decisions],
        "recent_snaps": [with_remote(s) for s in reversed(snaps)],
        "total_snaps": len(snaps),
    }
    write_json(
        OUT_DIR / "api" / "v1" / "projects" / project_id / "overview.json",
        wrap(overview),
    )

    # --- Intent details ---
    for intent in intents:
        rid = f"{workspace_id}__{intent['id']}"
        intent_snaps = [
            snap_map[sid]
            for sid in intent.get("snap_ids", [])
            if sid in snap_map
        ]
        write_json(
            OUT_DIR / "api" / "v1" / "intents" / f"{rid}.json",
            wrap({
                "workspace_id": workspace_id,
                "intent": intent,
                "snaps": intent_snaps,
            }),
        )

    # --- Decision details ---
    for decision in decisions:
        rid = f"{workspace_id}__{decision['id']}"
        decision_intents = [
            intent_map[iid]
            for iid in decision.get("intent_ids", [])
            if iid in intent_map
        ]
        write_json(
            OUT_DIR / "api" / "v1" / "decisions" / f"{rid}.json",
            wrap({
                "workspace_id": workspace_id,
                "decision": decision,
                "intents": decision_intents,
            }),
        )

    # --- Snap details ---
    for snap in snaps:
        rid = f"{workspace_id}__{snap['id']}"
        parent_intent = intent_map.get(snap.get("intent_id"))
        write_json(
            OUT_DIR / "api" / "v1" / "snaps" / f"{rid}.json",
            wrap({
                "workspace_id": workspace_id,
                "snap": snap,
                "intent": parent_intent,
            }),
        )

    return {
        "id": project_id,
        "name": name,
        "provider": "github",
        "repo_id": f"showcase/{name}",
        "repo": {"owner": "showcase", "name": name},
        "created_at": _latest_date(intents) or "2026-01-01T00:00:00+00:00",
        "_counts": {
            "intents": len(intents),
            "snaps": len(snaps),
            "decisions": len(decisions),
        },
    }


def _latest_date(objects: list[dict]) -> str | None:
    dates = [o.get("created_at", "") for o in objects if o.get("created_at")]
    return max(dates) if dates else None


def build():
    # Clean generated files (preserve showcase/ source data)
    for name in ("api", "app.js", "config.json", "index.html", "styles.css"):
        p = OUT_DIR / name
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()
    OUT_DIR.mkdir(exist_ok=True)

    # Copy web assets
    shutil.copy2(WEB_STATIC / "styles.css", OUT_DIR / "styles.css")

    # Build each showcase project
    projects = []
    for d in sorted(SHOWCASE_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        info = build_project(d)
        projects.append(info)
        count = info["_counts"]
        print(f"  {d.name}: {count['intents']} intents, {count['snaps']} snaps, {count['decisions']} decisions")

    # --- Projects list ---
    project_list = [{k: v for k, v in p.items() if k != "_counts"} for p in projects]
    write_json(
        OUT_DIR / "api" / "v1" / "projects.json",
        wrap({"projects": project_list}),
    )

    # --- Config ---
    write_json(OUT_DIR / "config.json", {
        "apiBaseUrl": "",
        "static": True,
    })

    # --- Search index (per project) ---
    # Generated alongside overview, consumed client-side
    for d in sorted(SHOWCASE_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        name = d.name
        project_id = f"showcase_{name}"
        workspace_id = f"wks_showcase_{name}"
        intents = load_json_dir(d / "intents")
        decisions = load_json_dir(d / "decisions")
        snaps = load_json_dir(d / "snaps")

        index = []
        for obj in intents:
            index.append({
                "object_type": "intent",
                "id": obj["id"],
                "remote_id": f"{workspace_id}__{obj['id']}",
                "what": obj.get("what", ""),
                "why": obj.get("why", ""),
                "status": obj.get("status", ""),
            })
        for obj in decisions:
            index.append({
                "object_type": "decision",
                "id": obj["id"],
                "remote_id": f"{workspace_id}__{obj['id']}",
                "what": obj.get("what", ""),
                "why": obj.get("why", ""),
                "status": obj.get("status", ""),
            })
        for obj in snaps:
            index.append({
                "object_type": "snap",
                "id": obj["id"],
                "remote_id": f"{workspace_id}__{obj['id']}",
                "what": obj.get("what", ""),
                "why": obj.get("why", ""),
                "status": "",
            })
        write_json(
            OUT_DIR / "api" / "v1" / "projects" / project_id / "search-index.json",
            wrap({"items": index}),
        )

    # Copy index.html (adjust paths for relative loading)
    html = (WEB_STATIC / "index.html").read_text()
    html = html.replace('href="/styles.css"', 'href="styles.css"')
    html = html.replace('src="/app.js"', 'src="app.js"')
    (OUT_DIR / "index.html").write_text(html)

    # Copy and patch app.js for static mode
    _build_static_app_js()

    total = sum(p["_counts"]["intents"] + p["_counts"]["snaps"] + p["_counts"]["decisions"] for p in projects)
    print(f"\nPages built → {OUT_DIR}/ ({len(projects)} projects, {total} objects)")


def _build_static_app_js():
    """Create a static-mode version of app.js."""
    js = (WEB_STATIC / "app.js").read_text()

    # 1. Patch apiUrl to append .json
    js = js.replace(
        'function apiUrl(path) {\n  return `${state.config.apiBaseUrl}${path}`;',
        'function apiUrl(path) {\n  if (state.config?.static) return `${path.replace(/^\\//, "")}.json`;\n  return `${state.config.apiBaseUrl}${path}`;',
    )

    # 2. Patch config loading to use relative path
    js = js.replace(
        'state.config = await fetch("/config.json").then((r) => r.json());',
        'state.config = await fetch("config.json").then((r) => r.json());',
    )

    # 3. Patch search to work client-side in static mode
    search_patch = '''
    // Static mode: client-side search
    if (state.config?.static) {
      e.preventDefault();
      const q = document.getElementById("search-input").value.trim();
      state.searchQuery = q;
      writeRoute();
      if (!q || !state.currentProjectId) return;
      try {
        const idx = await fetchJson(apiUrl(`/api/v1/projects/${state.currentProjectId}/search-index`));
        const lower = q.toLowerCase();
        const matches = idx.items.filter(item =>
          (item.what || "").toLowerCase().includes(lower) ||
          (item.why || "").toLowerCase().includes(lower) ||
          (item.id || "").toLowerCase().includes(lower)
        );
        renderSearchResults({ matches });
      } catch (err) {
        document.getElementById("search-results").innerHTML =
          `<div class="empty-state">${esc(err.message)}</div>`;
      }
      return;
    }'''

    js = js.replace(
        '''    .addEventListener("submit", async (e) => {
      e.preventDefault();
      const q = document.getElementById("search-input").value.trim();''',
        f'''    .addEventListener("submit", async (e) => {{{search_patch}
      e.preventDefault();
      const q = document.getElementById("search-input").value.trim();''',
    )

    # 4. Hide refresh button and API chip in static mode (add to init)
    js = js.replace(
        'el.apiChip.textContent = state.config.apiBaseUrl;',
        '''if (state.config.static) {
      el.refreshBtn.style.display = "none";
      el.apiChip.textContent = "Static Site";
    } else {
      el.apiChip.textContent = state.config.apiBaseUrl;
    }''',
    )

    (OUT_DIR / "app.js").write_text(js)


if __name__ == "__main__":
    build()
