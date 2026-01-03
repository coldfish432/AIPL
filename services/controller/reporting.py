from __future__ import annotations

import json
from pathlib import Path

__all__ = [
    "format_checks",
    "write_verification_report",
    "extract_paths_from_reasons",
    "extract_paths_from_checks",
]


def format_checks(checks: list[dict]) -> list[str]:
    lines = []
    for check in checks:
        ctype = check.get("type")
        if ctype == "command":
            timeout = check.get("timeout", "")
            lines.append(f"- command: {check.get('cmd')} timeout={timeout}")
        elif ctype == "command_contains":
            timeout = check.get("timeout", "")
            lines.append(f"- command_contains: {check.get('cmd')} needle={check.get('needle')} timeout={timeout}")
        elif ctype == "file_exists":
            lines.append(f"- file_exists: {check.get('path')}")
        elif ctype == "file_contains":
            lines.append(f"- file_contains: {check.get('path')} needle={check.get('needle')}")
        elif ctype == "json_schema":
            lines.append(f"- json_schema: {check.get('path')}")
        elif ctype == "http_check":
            lines.append(f"- http_check: {check.get('url')}")
        else:
            lines.append(f"- unknown: {json.dumps(check, ensure_ascii=False)}")
    return lines


def write_verification_report(
    run_dir: Path,
    task_id: str,
    plan_id: str | None,
    workspace_path: str | None,
    passed: bool,
    reasons: list,
    checks: list[dict],
) -> None:
    lines = [
        "# Verification Report",
        f"- task_id: {task_id}",
        f"- plan_id: {plan_id}",
        f"- run_dir: {run_dir}",
        f"- workspace: {workspace_path}",
        f"- passed: {passed}",
        f"- verification_result: {run_dir / 'verification_result.json'}",
        "",
        "## Checks",
    ]
    lines.extend(format_checks(checks) or ["- (none)"])

    lines.append("")
    lines.append("## How To Verify")
    if checks:
        for check in checks:
            ctype = check.get("type")
            if ctype == "command":
                lines.append(f"- run: {check.get('cmd')}")
            elif ctype == "command_contains":
                lines.append(f"- run: {check.get('cmd')} (expect contains {check.get('needle')})")
            elif ctype == "file_exists":
                lines.append(f"- check file exists: {check.get('path')}")
            elif ctype == "file_contains":
                lines.append(f"- check file contains: {check.get('path')} -> {check.get('needle')}")
            elif ctype == "json_schema":
                lines.append(f"- check json schema: {check.get('path')}")
            elif ctype == "http_check":
                lines.append(f"- http check: {check.get('url')}")
            else:
                lines.append(f"- manual check: {json.dumps(check, ensure_ascii=False)}")
    else:
        lines.append("- no checks available")

    lines.append("")
    lines.append("## Failure Reasons")
    if reasons:
        for reason in reasons:
            lines.append(f"- {json.dumps(reason, ensure_ascii=False)}")
    else:
        lines.append("- none")

    (run_dir / "verification_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def extract_paths_from_reasons(reasons: list) -> list[str]:
    paths: list[str] = []
    for reason in reasons or []:
        if not isinstance(reason, dict):
            continue
        for key in ("file", "path"):
            value = reason.get(key)
            if isinstance(value, str) and value.strip():
                paths.append(value.strip())
    return paths


def extract_paths_from_checks(checks: list[dict]) -> list[str]:
    paths: list[str] = []
    for check in checks or []:
        if not isinstance(check, dict):
            continue
        value = check.get("path")
        if isinstance(value, str) and value.strip():
            paths.append(value.strip())
    return paths
