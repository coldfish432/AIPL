from __future__ import annotations

from pathlib import Path

from config.settings import get_settings
from engine.context import ContextMerger, ProjectContext
from interfaces.protocols import IProfileService
from workspace_utils import get_workspace_dir

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

    effective_hard = profile.get("effective_hard") or {}
    context = ProjectContext(root, workspace)
    checks = context.get_default_checks()
    workspace_dir = get_workspace_dir(root, workspace_path)
    merger = ContextMerger(workspace_dir)
    merged_context = merger.merge_for_scope("fix")
    combined_checks = list(checks)
    seen_ids = {c.get("id") for c in combined_checks if c.get("id")}
    for check in merged_context.checks:
        check_id = check.get("id")
        if check_id and check_id in seen_ids:
            continue
        if check_id:
            seen_ids.add(check_id)
        combined_checks.append(check)
    capabilities = context.workspace_info.get("capabilities", {}) if isinstance(context.workspace_info, dict) else {}
    if context.workspace_id:
        capabilities = dict(capabilities)
        capabilities["workspace_id"] = context.workspace_id
    settings = get_settings()

    policy = {
        "allow_write": effective_hard.get("allow_write", []),
        "deny_write": effective_hard.get("deny_write", []),
        "allowed_commands": effective_hard.get("allowed_commands", []),
        "command_timeout": effective_hard.get("command_timeout", settings.command.default_timeout),
        "max_concurrency": effective_hard.get("max_concurrency", settings.workspace.max_concurrency),
        "checks": combined_checks,
        "workspace_id": profile.get("workspace_id"),
        "fingerprint": profile.get("fingerprint"),
        "workspace_rules": merged_context.rules,
        "workspace_rule_sources": merged_context.rule_sources,
        "workspace_conflicts": merged_context.conflicts_discarded,
        "workspace_hints": merged_context.hints,
        "workspace_lessons": merged_context.lessons,
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
