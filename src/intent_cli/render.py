from __future__ import annotations

from typing import TYPE_CHECKING

from .constants import OBJECT_LABELS, OBJECT_PLURALS
from .git import summarize_git
from .helpers import object_sort_key

if TYPE_CHECKING:
    from .core import IntentRepository


def render_status_text(repo: "IntentRepository") -> str:
    snapshot = repo.snapshot()
    status = snapshot.state["workspace_status"]
    next_action = repo.next_action(snapshot)
    if status in {"idle", "blocked_no_active_intent"}:
        return "\n".join(
            [
                "Semantic workspace",
                f"Status: {status}",
                "No active intent",
                f"Next: {next_action['command']}" if next_action else "",
            ]
        ).strip()

    lines = ["Semantic workspace"]
    if snapshot.active_intent:
        lines.append(f"Intent: {snapshot.active_intent['id']}  {snapshot.active_intent['title']}")
    if snapshot.active_run:
        lines.append(f"Run: {snapshot.active_run['id']}  {snapshot.active_run['title']}")
    if snapshot.current_checkpoint:
        lines.append(f"Current checkpoint: {snapshot.current_checkpoint['id']}  {snapshot.current_checkpoint['title']}")
    lines.append(f"Status: {status}")
    if snapshot.latest_adoption and status == "adoption_recorded":
        lines.append(f"Latest adoption: {snapshot.latest_adoption['id']}  {snapshot.latest_adoption['title']}")
    if snapshot.latest_decision:
        lines.append(f"Latest decision: {snapshot.latest_decision['id']}  {snapshot.latest_decision['title']}")
    if status == "conflict_multiple_candidates":
        lines.append("Warning: Multiple candidate checkpoints exist and no unique current checkpoint is selected")
    if next_action:
        lines.append(f"Next: {next_action['command']}")
    return "\n".join(lines)


def render_log_text(repo: "IntentRepository") -> str:
    repo.ensure_git()
    repo.ensure_initialized()
    adoptions = sorted(repo.list_objects("adoption"), key=object_sort_key, reverse=True)
    standalone_decisions = repo.standalone_decisions()
    if not adoptions and not standalone_decisions:
        return "Semantic history\nNo semantic records yet\nNext: itt status"

    lines = ["Semantic history", ""]
    for adoption in adoptions:
        created = adoption["created_at"].replace("T", " ").replace("Z", "")
        checkpoint = repo.load_object("checkpoint", adoption.get("checkpoint_id"))
        intent = repo.load_object("intent", adoption.get("intent_id"))
        git_head = (adoption.get("git") or {}).get("head") or "no-commit"
        lines.append(f"{created}  {adoption['id']}  {adoption['title']}")
        if intent:
            lines.append(f"  Intent: {intent['id']}  {intent['title']}")
        if checkpoint:
            lines.append(f"  Checkpoint: {checkpoint['id']}  {checkpoint['title']}")
        if adoption.get("reverts_adoption_id"):
            lines.append(f"  Reverts: {adoption['reverts_adoption_id']}")
        for decision in repo.decisions_for_adoption(adoption["id"]):
            lines.append(f"  Decision: {decision['id']}  {decision['title']}")
            if decision.get("rationale"):
                lines.append(f"  Because: {decision['rationale']}")
        lines.append(f"  Git: {git_head}")
        lines.append("")

    if standalone_decisions:
        lines.append("Standalone decisions")
        lines.append("")
        for decision in standalone_decisions:
            created = decision["created_at"].replace("T", " ").replace("Z", "")
            intent = repo.load_object("intent", decision.get("intent_id"))
            git_head = (decision.get("git") or {}).get("head") or "no-commit"
            lines.append(f"{created}  {decision['id']}  {decision['title']}")
            if intent:
                lines.append(f"  Intent: {intent['id']}  {intent['title']}")
            if decision.get("rationale"):
                lines.append(f"  Because: {decision['rationale']}")
            lines.append(f"  Git: {git_head}")
            lines.append("")
    return "\n".join(lines).rstrip()


def render_config_text(repo: "IntentRepository") -> str:
    config = repo.show_config()
    lines = [
        "Intent config",
        f"Schema version: {config.get('schema_version')}",
        f"Strict adoption: {str(config.get('git', {}).get('strict_adoption', False)).lower()}",
    ]
    return "\n".join(lines)


def render_object_list_text(repo: "IntentRepository", object_name: str) -> str:
    items = repo.list_view(object_name)
    label = OBJECT_PLURALS[object_name]
    if not items:
        return f"{label}\nNo {object_name}s recorded yet"

    lines = [label, ""]
    for item in items:
        details = [f"status={item['status']}"]
        if object_name == "intent":
            if item.get("is_active"):
                details.append("active")
        elif object_name == "checkpoint":
            details.append(f"intent={item['intent_id']}")
            if item.get("run_id"):
                details.append(f"run={item['run_id']}")
            if item.get("selected"):
                details.append("selected")
            if item.get("is_current"):
                details.append("current")
            if item.get("adopted"):
                details.append("adopted")
        elif object_name == "adoption":
            details.append(f"intent={item['intent_id']}")
            details.append(f"checkpoint={item['checkpoint_id']}")
            if item.get("run_id"):
                details.append(f"run={item['run_id']}")
            if item.get("is_latest"):
                details.append("latest")
            if item.get("reverts_adoption_id"):
                details.append(f"reverts={item['reverts_adoption_id']}")
        elif object_name == "run":
            details.append(f"intent={item['intent_id']}")
            if item.get("is_active"):
                details.append("active")
        elif object_name == "decision":
            details.append(f"intent={item['intent_id']}")
            if item.get("adoption_id"):
                details.append(f"adoption={item['adoption_id']}")
            if item.get("checkpoint_id"):
                details.append(f"checkpoint={item['checkpoint_id']}")
        lines.append(f"{item['id']}  {item['title']} [{', '.join(details)}]")
    return "\n".join(lines)


def render_object_show_text(repo: "IntentRepository", object_name: str, object_ref: str) -> str:
    payload = repo.show_view(object_name, object_ref)
    label = OBJECT_LABELS[object_name]
    lines = [
        f"{label} {payload['id']}",
        f"Title: {payload['title']}",
        f"Status: {payload['status']}",
    ]
    if payload.get("summary"):
        lines.append(f"Summary: {payload['summary']}")

    if object_name == "intent":
        lines.append(f"Latest checkpoint: {payload.get('latest_checkpoint_id') or 'none'}")
        lines.append(f"Latest adoption: {payload.get('latest_adoption_id') or 'none'}")
    elif object_name == "checkpoint":
        lines.append(f"Intent: {payload.get('intent_id')}")
        lines.append(f"Run: {payload.get('run_id') or 'none'}")
        lines.append(f"Ordinal: {payload.get('ordinal')}")
        lines.append(f"Selected: {str(payload.get('selected', False)).lower()}")
        lines.append(f"Adopted: {str(payload.get('adopted', False)).lower()}")
        lines.append(f"Adopted by: {payload.get('adopted_by') or 'none'}")
        lines.append(f"Git: {summarize_git(payload.get('git', {}))}")
    elif object_name == "adoption":
        lines.append(f"Intent: {payload.get('intent_id')}")
        lines.append(f"Run: {payload.get('run_id') or 'none'}")
        lines.append(f"Checkpoint: {payload.get('checkpoint_id')}")
        if payload.get("rationale"):
            lines.append(f"Because: {payload['rationale']}")
        lines.append(f"Reverts: {payload.get('reverts_adoption_id') or 'none'}")
        lines.append(f"Git: {summarize_git(payload.get('git', {}))}")
    elif object_name == "run":
        lines.append(f"Intent: {payload.get('intent_id')}")
        lines.append(f"Git: {summarize_git(payload.get('git', {}))}")
    elif object_name == "decision":
        lines.append(f"Intent: {payload.get('intent_id')}")
        lines.append(f"Run: {payload.get('run_id') or 'none'}")
        lines.append(f"Adoption: {payload.get('adoption_id') or 'none'}")
        lines.append(f"Checkpoint: {payload.get('checkpoint_id') or 'none'}")
        if payload.get("rationale"):
            lines.append(f"Because: {payload['rationale']}")
        lines.append(f"Git: {summarize_git(payload.get('git', {}))}")
    return "\n".join(lines)
