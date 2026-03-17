from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from . import __version__
from .constants import EXIT_GENERAL_FAILURE, EXIT_INVALID_INPUT
from .errors import IntentError
from .helpers import cli_action, read_json, utc_now, write_json


MANIFEST_NAME = "manifest.json"
SUPPORTED_AGENTS = ("auto", "codex", "claude", "cursor")


def install_root() -> Path:
    configured = os.environ.get("INTENT_HOME")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".intent"


def launcher_path() -> Path:
    return install_root() / "bin" / "itt"


def repo_checkout_root() -> Path:
    candidates: List[Path] = []

    candidates.append(install_root() / "repo")

    # When developing inside the Intent repository, allow the source checkout
    # itself to act as the setup source instead of requiring a bootstrap copy.
    source_repo = Path(__file__).resolve().parents[2]
    if (source_repo / "setup" / MANIFEST_NAME).exists():
        candidates.append(source_repo)

    for candidate in candidates:
        if (candidate / "setup" / MANIFEST_NAME).exists():
            return candidate

    raise IntentError(
        EXIT_GENERAL_FAILURE,
        "SETUP_ASSETS_MISSING",
        "Intent setup assets are not available from the fixed local checkout.",
        details={"checked_paths": [str(path) for path in candidates]},
        suggested_fix="Run the bootstrap installer again so Intent can restore its local repository checkout.",
    )


def source_setup_root() -> Path:
    return repo_checkout_root() / "setup"


def runtime_context() -> Dict[str, str]:
    return {
        "install_root": str(install_root()),
        "launcher_path": str(launcher_path()),
        "repo_root": str(repo_checkout_root()),
        "setup_root": str(source_setup_root()),
    }


def load_manifest() -> Dict[str, Any]:
    return json.loads((source_setup_root() / MANIFEST_NAME).read_text(encoding="utf-8"))


def normalize_agent_name(agent: Optional[str]) -> str:
    normalized = (agent or "auto").strip().lower()
    if normalized not in SUPPORTED_AGENTS:
        raise IntentError(
            EXIT_INVALID_INPUT,
            "INVALID_INPUT",
            f"Unsupported agent target: {agent}",
            details={"agent": agent, "supported_agents": list(SUPPORTED_AGENTS)},
            suggested_fix=f"Use one of: {', '.join(SUPPORTED_AGENTS)}",
        )
    return normalized


def find_integration(manifest: Dict[str, Any], agent_id: str) -> Dict[str, Any]:
    for integration in manifest["integrations"]:
        if integration["id"] == agent_id:
            return integration
    raise IntentError(
        EXIT_INVALID_INPUT,
        "INVALID_INPUT",
        f"Unsupported agent target: {agent_id}",
        details={"agent": agent_id},
    )


def agent_source_dir(integration: Dict[str, Any]) -> Path:
    return source_setup_root() / integration["source_dir"]


def iter_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file():
            yield path


def asset_file_list(integration: Dict[str, Any]) -> List[str]:
    root = agent_source_dir(integration)
    return [str(path.relative_to(root)) for path in iter_files(root)]


def receipt_path(agent_id: str) -> Path:
    return install_root() / "receipts" / f"{agent_id}.json"


def generated_root(agent_id: str) -> Path:
    return install_root() / "generated" / agent_id


def detect_integration(integration: Dict[str, Any]) -> Dict[str, Any]:
    signals: List[Dict[str, str]] = []
    detection = integration.get("detection", {})

    for env_name in detection.get("env_any", []):
        value = os.environ.get(env_name)
        if value:
            signals.append({"kind": "env", "value": env_name})

    for raw_path in detection.get("paths_any", []):
        resolved = Path(raw_path).expanduser()
        if resolved.exists():
            signals.append({"kind": "path", "value": str(resolved)})

    return {
        "id": integration["id"],
        "detected": bool(signals),
        "signals": signals,
    }


def target_home(integration: Dict[str, Any]) -> Path:
    target = integration.get("target", {})
    env_name = target.get("home_env")
    if env_name and os.environ.get(env_name):
        return Path(os.environ[env_name]).expanduser()
    return Path(target["home_default"]).expanduser()


def target_dir(integration: Dict[str, Any]) -> Optional[Path]:
    if integration["install_mode"] != "skill_dir":
        return None
    return target_home(integration) / integration["target"]["relative_dir"]


def manual_helper_path(integration: Dict[str, Any]) -> Optional[Path]:
    if integration["install_mode"] != "manual_helper":
        return None
    return generated_root(integration["id"]) / integration["helper"]["entrypoint"]


def copy_tree(source: Path, destination: Path) -> List[str]:
    written: List[str] = []
    destination.mkdir(parents=True, exist_ok=True)
    for source_file in iter_files(source):
        relative = source_file.relative_to(source)
        target_file = destination / relative
        target_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, target_file)
        written.append(str(relative))
    return written


def write_receipt(
    integration: Dict[str, Any],
    *,
    status: str,
    target_path: Optional[Path],
    files: List[str],
) -> None:
    path = receipt_path(integration["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()
    write_json(
        path,
        {
            "schema_version": manifest["schema_version"],
            "manifest_version": manifest["manifest_version"],
            "installed_at": utc_now(),
            "agent_id": integration["id"],
            "display_name": integration["display_name"],
            "cli_version": __version__,
            "status": status,
            "install_mode": integration["install_mode"],
            "target_path": str(target_path) if target_path else None,
            "files": files,
        },
    )


def installation_status(integration: Dict[str, Any]) -> Dict[str, Any]:
    receipt = receipt_path(integration["id"])
    receipt_payload = read_json(receipt) if receipt.exists() else None
    expected_files = asset_file_list(integration)

    if integration["install_mode"] == "skill_dir":
        resolved_target = target_dir(integration)
        assert resolved_target is not None
        missing_files = [path for path in expected_files if not (resolved_target / path).exists()]

        if receipt.exists() and not missing_files:
            status = "installed"
        elif resolved_target.exists() and not missing_files:
            status = "installed_external"
        elif resolved_target.exists():
            status = "incomplete"
        else:
            status = "not_installed"

        return {
            "status": status,
            "target_path": str(resolved_target),
            "expected_files": expected_files,
            "missing_files": missing_files,
            "receipt": receipt_payload,
            "installed": status in {"installed", "installed_external"},
        }

    helper = manual_helper_path(integration)
    assert helper is not None
    staged_files = [path for path in expected_files if (generated_root(integration["id"]) / path).exists()]
    if helper.exists():
        status = "manual_helper_ready"
    else:
        status = "manual_setup_pending"

    return {
        "status": status,
        "target_path": str(helper),
        "expected_files": expected_files,
        "missing_files": [path for path in expected_files if path not in staged_files],
        "receipt": receipt_payload,
        "installed": False,
    }


def list_integrations() -> Dict[str, Any]:
    manifest = load_manifest()
    items: List[Dict[str, Any]] = []

    for integration in manifest["integrations"]:
        detected = detect_integration(integration)
        installed = installation_status(integration)
        items.append(
            {
                "id": integration["id"],
                "display_name": integration["display_name"],
                "description": integration["description"],
                "install_mode": integration["install_mode"],
                "auto_install_supported": integration["install_mode"] == "skill_dir",
                "detected": detected["detected"],
                "signals": detected["signals"],
                "status": installed["status"],
                "target_path": installed["target_path"],
            }
        )

    return {
        "schema_version": manifest["schema_version"],
        "manifest_version": manifest["manifest_version"],
        **runtime_context(),
        "integrations": items,
    }


def choose_auto_agent(manifest: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], List[str], List[str], List[str]]:
    warnings: List[str] = []
    auto_detected: List[str] = []
    manual_detected: List[str] = []

    for integration in manifest["integrations"]:
        detected = detect_integration(integration)
        if not detected["detected"]:
            continue
        if integration["install_mode"] == "skill_dir":
            auto_detected.append(integration["id"])
        else:
            manual_detected.append(integration["id"])

    if manual_detected:
        warnings.append(
            "Detected platforms without a file-based auto-install path: "
            + ", ".join(manual_detected)
            + ". Intent will leave them for explicit follow-up."
        )

    if not auto_detected:
        return None, warnings, auto_detected, manual_detected

    if len(auto_detected) > 1:
        warnings.append(f"Multiple auto-installable agents were detected; defaulting to {auto_detected[0]}.")

    return find_integration(manifest, auto_detected[0]), warnings, auto_detected, manual_detected


def manual_instructions(integration: Dict[str, Any], helper_path: Path) -> str:
    if integration["id"] == "cursor":
        return (
            f"Cursor currently uses settings-backed user rules rather than a stable global skill directory. "
            f"A helper rule was staged at {helper_path}. Add it to Cursor user rules or copy it into a project "
            f"at .cursor/rules/intent.mdc."
        )
    return f"Manual follow-up is required for {integration['display_name']}."


def setup_integration(requested_agent: str) -> Tuple[Dict[str, Any], List[str], bool, bool, Optional[str]]:
    manifest = load_manifest()
    normalized_agent = normalize_agent_name(requested_agent)

    selected: Optional[Dict[str, Any]]
    warnings: List[str]
    auto_detected: List[str]
    manual_detected: List[str]

    if normalized_agent == "auto":
        selected, warnings, auto_detected, manual_detected = choose_auto_agent(manifest)
        if selected is None:
            result = {
                "requested_agent": normalized_agent,
                "selected_agent": None,
                **runtime_context(),
                "detected_agents": auto_detected + manual_detected,
                "auto_detected_agents": auto_detected,
                "manual_detected_agents": manual_detected,
                "installed": False,
                "status": "no_auto_installable_agent_detected",
            }
            return result, warnings, False, False, "No auto-installable agent was detected."
    else:
        selected = find_integration(manifest, normalized_agent)
        warnings = []
        auto_detected = []
        manual_detected = []

    assert selected is not None
    current = installation_status(selected)
    current_receipt = current["receipt"] or {}
    up_to_date = (
        current["status"] in {"installed", "manual_helper_ready"}
        and current_receipt.get("cli_version") == __version__
        and current_receipt.get("manifest_version") == manifest["manifest_version"]
    )

    if up_to_date:
        result = {
            "requested_agent": normalized_agent,
            "selected_agent": selected["id"],
            **runtime_context(),
            "install_mode": selected["install_mode"],
            "target_path": current["target_path"],
            "detected_agents": auto_detected + manual_detected,
            "installed": current["status"] == "installed",
            "status": current["status"],
            "files": current["expected_files"],
        }
        return result, warnings, False, True, "Integration assets are already up to date."

    source_dir = agent_source_dir(selected)
    if selected["install_mode"] == "skill_dir":
        destination = target_dir(selected)
        assert destination is not None
        written_files = copy_tree(source_dir, destination)
        write_receipt(selected, status="installed", target_path=destination, files=written_files)
        result = {
            "requested_agent": normalized_agent,
            "selected_agent": selected["id"],
            **runtime_context(),
            "install_mode": selected["install_mode"],
            "target_path": str(destination),
            "detected_agents": auto_detected + manual_detected,
            "installed": True,
            "status": "installed",
            "files": written_files,
        }
        return result, warnings, True, False, None

    helper_destination = generated_root(selected["id"])
    written_files = copy_tree(source_dir, helper_destination)
    helper_file = manual_helper_path(selected)
    assert helper_file is not None
    write_receipt(selected, status="manual_helper_ready", target_path=helper_file, files=written_files)
    result = {
        "requested_agent": normalized_agent,
        "selected_agent": selected["id"],
        **runtime_context(),
        "install_mode": selected["install_mode"],
        "target_path": str(helper_file),
        "detected_agents": auto_detected + manual_detected,
        "installed": False,
        "status": "manual_helper_ready",
        "files": written_files,
    }
    return result, warnings, True, False, manual_instructions(selected, helper_file)


def doctor_report(requested_agent: Optional[str] = None) -> Dict[str, Any]:
    manifest = load_manifest()
    target_agent = normalize_agent_name(requested_agent or "auto")
    if requested_agent:
        integrations = [find_integration(manifest, target_agent)]
    else:
        integrations = manifest["integrations"]

    checks: List[Dict[str, Any]] = []
    warnings: List[str] = []
    healthy = True

    for integration in integrations:
        detected = detect_integration(integration)
        installed = installation_status(integration)
        status = installed["status"]

        if integration["install_mode"] == "skill_dir":
            if requested_agent and status not in {"installed", "installed_external"}:
                healthy = False
            if status == "incomplete":
                healthy = False
            if status == "not_installed" and detected["detected"]:
                warnings.append(
                    f"{integration['id']} was detected locally but its skill is not installed yet."
                )
            if status == "installed_external":
                warnings.append(
                    f"{integration['id']} already has the expected skill files, but they are not managed by Intent yet."
                )
        else:
            if requested_agent:
                healthy = False
            if detected["detected"]:
                warnings.append(
                    f"{integration['id']} is detected, but it still requires manual follow-up after helper generation."
                )

        checks.append(
            {
                "id": integration["id"],
                "display_name": integration["display_name"],
                "description": integration["description"],
                "install_mode": integration["install_mode"],
                "detected": detected["detected"],
                "signals": detected["signals"],
                "status": status,
                "target_path": installed["target_path"],
                "missing_files": installed["missing_files"],
            }
        )

    return {
        "healthy": healthy,
        "schema_version": manifest["schema_version"],
        "manifest_version": manifest["manifest_version"],
        "cli_version": __version__,
        **runtime_context(),
        "checks": checks,
        "warnings": warnings,
    }


def format_integrations_text(payload: Dict[str, Any]) -> str:
    lines = [
        "Supported integrations",
        f"Install root: {payload['install_root']}",
        f"Intent command: {payload['launcher_path']}",
        f"Repo checkout: {payload['repo_root']}",
        f"Setup source: {payload['setup_root']}",
    ]
    for item in payload["integrations"]:
        badges = [item["status"]]
        if item["detected"]:
            badges.append("detected")
        if item["auto_install_supported"]:
            badges.append("auto")
        else:
            badges.append("manual")
        lines.append(f"- {item['id']} ({', '.join(badges)})")
        lines.append(f"  {item['description']}")
    return "\n".join(lines)


def format_setup_text(result: Dict[str, Any], reason: Optional[str]) -> str:
    if result["selected_agent"] is None:
        lines = [
            "No auto-installable agent was detected.",
            f"Repo-backed itt remains available at: {result['launcher_path']}",
            f"Install root: {result['install_root']}",
            f"Repo checkout: {result['repo_root']}",
        ]
        manual_detected = result.get("manual_detected_agents") or []
        if manual_detected:
            lines.append("Detected manual-follow-up targets: " + ", ".join(manual_detected))
        lines.append("Next: itt integrations list")
        return "\n".join(lines)

    if result["install_mode"] == "manual_helper":
        lines = [
            f"Prepared manual setup helper for {result['selected_agent']}",
            f"Helper: {result['target_path']}",
            f"Intent command: {result['launcher_path']}",
        ]
        if reason:
            lines.append(reason)
        return "\n".join(lines)

    lines = [
        f"Installed Intent skill for {result['selected_agent']}",
        f"Target: {result['target_path']}",
        f"Intent command: {result['launcher_path']}",
        f"Install root: {result['install_root']}",
        f"Repo checkout: {result['repo_root']}",
    ]
    if reason:
        lines.append(f"Status: {reason}")
    lines.append(f"Next: {cli_action(['doctor', '--agent', result['selected_agent']], 'Verify the installed skill')['command']}")
    return "\n".join(lines)


def format_doctor_text(payload: Dict[str, Any]) -> str:
    lines = [
        "Intent setup doctor",
        f"CLI: {payload['cli_version']}",
        f"Install root: {payload['install_root']}",
        f"Intent command: {payload['launcher_path']}",
        f"Repo checkout: {payload['repo_root']}",
        f"Setup source: {payload['setup_root']}",
        f"Healthy: {'yes' if payload['healthy'] else 'no'}",
    ]

    for check in payload["checks"]:
        status_bits = [check["status"], check["install_mode"]]
        if check["detected"]:
            status_bits.append("detected")
        lines.append(f"- {check['id']}: {', '.join(status_bits)}")
        if check["target_path"]:
            lines.append(f"  Target: {check['target_path']}")
        if check["missing_files"]:
            lines.append(f"  Missing: {', '.join(check['missing_files'])}")

    if payload["warnings"]:
        lines.append("Warnings:")
        for warning in payload["warnings"]:
            lines.append(f"- {warning}")
    return "\n".join(lines)


def doctor_exit_code(payload: Dict[str, Any]) -> int:
    return 0 if payload["healthy"] else EXIT_GENERAL_FAILURE
