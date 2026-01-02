from __future__ import annotations

import re
from pathlib import Path

from ..registry import register_check
from ..utils import reason
from .base import check_file_contains, check_file_exists, select_base_path


@register_check("file_exists")
def handle_file_exists(check: dict, run_dir: Path, workspace: Path | None, log_dir: Path, idx: int):
    path = check.get("path", "")
    base = select_base_path(run_dir, workspace, path)
    if not base:
        return False, reason("workspace_required", check_type="file_exists", hint="workspace path is required for this check"), None
    ok, err = check_file_exists(base, path)
    info = {"path": path}
    return ok, err, info


@register_check("file_contains")
def handle_file_contains(check: dict, run_dir: Path, workspace: Path | None, log_dir: Path, idx: int):
    path = check.get("path", "")
    base = select_base_path(run_dir, workspace, path)
    if not base:
        return False, reason("workspace_required", check_type="file_contains", hint="workspace path is required for this check"), None
    ok, err = check_file_contains(base, path, check.get("needle", ""))
    info = {"path": path, "needle": check.get("needle", "")}
    return ok, err, info


@register_check("file_matches")
def handle_file_matches(check: dict, run_dir: Path, workspace: Path | None, log_dir: Path, idx: int):
    path = check.get("path", "")
    pattern = check.get("pattern", "")
    base = select_base_path(run_dir, workspace, path)
    if not base:
        return False, reason("workspace_required", check_type="file_matches", hint="workspace path is required for this check"), None
    ok, err = check_file_exists(base, path)
    if not ok:
        return ok, err, None
    target = (base / path).resolve()
    text = target.read_text(encoding="utf-8", errors="replace")
    flags = 0
    if check.get("ignore_case"):
        flags |= re.IGNORECASE
    if check.get("multiline"):
        flags |= re.MULTILINE
    match = re.search(pattern, text, flags)
    if not match:
        return False, reason("pattern_not_found", pattern=pattern, file=path), {"path": path, "pattern": pattern}
    return True, None, {"path": path, "pattern": pattern, "match": match.group(0)[:200]}
