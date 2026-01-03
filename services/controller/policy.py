from __future__ import annotations

from pathlib import Path

from config.settings import get_settings
from detect_workspace import detect_workspace
from interfaces.protocols import IProfileService

__all__ = ["load_policy", "merge_checks", "is_high_risk", "has_execution_check"]


def load_policy(
    root: Path,
    workspace_path: str | None,
    profile_service: IProfileService,
) -> tuple[dict, str, dict | None, dict | None]:
    if not workspace_path:
        return {}, "none", None, None

    workspace = Path(workspace_path)
    profile = profile_service.ensure_profile(root, workspace)
    if profile.get("created"):
        profile = profile_service.propose_soft(root, workspace, reason="new_workspace")
    elif profile.get("fingerprint_changed"):
        profile = profile_service.propose_soft(root, workspace, reason="fingerprint_changed")

    effective_hard = profile.get("effective_hard") or {}
    workspace_info = detect_workspace(workspace)
    checks = workspace_info.get("checks", [])
    capabilities = workspace_info.get("capabilities", {})
    settings = get_settings()

    policy = {
        "allow_write": effective_hard.get("allow_write", []),
        "deny_write": effective_hard.get("deny_write", []),
        "allowed_commands": effective_hard.get("allowed_commands", []),
        "command_timeout": effective_hard.get("command_timeout", settings.command.default_timeout),
        "max_concurrency": effective_hard.get("max_concurrency", settings.workspace.max_concurrency),
        "checks": checks,
        "workspace_id": profile.get("workspace_id"),
        "fingerprint": profile.get("fingerprint"),
    }
    return policy, "profile", profile, capabilities


def has_execution_check(checks: list[dict]) -> bool:
    for check in checks or []:
        if check.get("type") in {"command", "command_contains", "http_check"}:
            return True
    return False


def merge_checks(task_checks: list[dict], policy_checks: list[dict], high_risk: bool = False) -> list[dict]:
    if has_execution_check(task_checks) and not high_risk:
        return list(task_checks or [])
    merged = list(task_checks or [])
    merged.extend(policy_checks or [])
    return merged


def is_high_risk(value) -> bool:
    if value is True:
        return True
    if isinstance(value, (int, float)) and value >= 7:
        return True
    if isinstance(value, str) and value.strip().lower() in {"high", "critical"}:
        return True
    return False
