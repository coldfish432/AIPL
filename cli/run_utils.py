from __future__ import annotations

from pathlib import Path
from typing import Tuple

from infra.io_utils import read_json
from infra.path_guard import normalize_path
from state import build_transition_event


def _collect_retry_ids(tasks_by_id: dict[str, dict], task_id: str, include_deps: bool) -> set[str]:
    if not include_deps:
        return {task_id}
    seen: set[str] = set()
    stack = [task_id]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        task = tasks_by_id.get(current)
        if not task:
            continue
        deps = task.get("dependencies", [])
        if not isinstance(deps, list):
            continue
        for dep in deps:
            if isinstance(dep, str) and dep and dep not in seen:
                stack.append(dep)
    return seen


def _reset_tasks_to_todo(tasks: list[dict], reset_ids: set[str], reason: dict, now: float) -> list[dict]:
    events: list[dict] = []
    for task in tasks:
        task_id = task.get("id")
        if task_id not in reset_ids:
            continue
        from_status = task.get("status")
        if from_status == "todo":
            continue
        task["status"] = "todo"
        task["status_ts"] = now
        task.pop("heartbeat_ts", None)
        task.pop("stale_ts", None)
        events.append(build_transition_event(task, from_status, "todo", now, source="retry", reason=reason))
    return events


def _load_backlog_tasks(backlog_path: Path) -> Tuple[dict, list[dict]]:
    backlog = read_json(backlog_path, default={"tasks": []})
    tasks = backlog.get("tasks", []) if isinstance(backlog, dict) else []
    if not isinstance(tasks, list):
        tasks = []
    return backlog, tasks


def load_backlog_map(root: Path) -> dict[str, list[dict]]:
    backlog_root = root / "backlog"
    if not backlog_root.exists():
        return {}

    backlog_map: dict[str, list[dict]] = {}
    for backlog_file in backlog_root.iterdir():
        if not backlog_file.is_file():
            continue
        try:
            backlog = read_json(backlog_file, default={})
        except Exception:
            continue
        tasks = backlog.get("tasks", []) if isinstance(backlog, dict) else []
        if not isinstance(tasks, list):
            continue
        for task in tasks:
            if not isinstance(task, dict):
                continue
            workspace = (
                task.get("workspace_path")
                or task.get("workspace")
                or task.get("workspace_main_root")
                or ""
            )
            backlog_map.setdefault(workspace, []).append(task)

    return backlog_map


def load_backlog_map_filtered(root: Path, workspace: str | None) -> dict[str, list[dict]]:
    if not workspace:
        return load_backlog_map(root)
    normalized_target = normalize_path(workspace)
    filtered: dict[str, list[dict]] = {}
    for ws, tasks in load_backlog_map(root).items():
        if not ws:
            continue
        if normalize_path(ws) == normalized_target:
            filtered[ws] = tasks
    return filtered
