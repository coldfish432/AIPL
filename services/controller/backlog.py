from __future__ import annotations

from pathlib import Path
from typing import Optional

from infra.io_utils import read_json
from infra.path_guard import normalize_path

__all__ = ["list_backlog_files", "load_backlog_map", "load_backlog_map_filtered"]


def list_backlog_files(root: Path) -> list[Path]:
    backlog_dir = root / "backlog"
    if not backlog_dir.exists():
        return []
    return sorted(backlog_dir.glob("*.json"))


def load_backlog_map(root: Path) -> dict[Path, list[dict]]:
    backlog_map: dict[Path, list[dict]] = {}
    for path in list_backlog_files(root):
        data = read_json(path, default={"tasks": []})
        backlog_map[path] = (data or {}).get("tasks", [])
    return backlog_map


def load_backlog_map_filtered(root: Path, workspace: Optional[str] = None) -> dict[Path, list[dict]]:
    """Load backlog map, optionally filtering tasks by workspace path."""
    backlog_map: dict[Path, list[dict]] = {}
    workspace_normalized = normalize_path(workspace) if workspace else None

    for path in list_backlog_files(root):
        data = read_json(path, default={"tasks": []})
        tasks = (data or {}).get("tasks", [])

        if workspace_normalized:
            filtered_tasks: list[dict] = []
            for task in tasks:
                task_workspace = task.get("workspace_path")
                if not isinstance(task_workspace, str):
                    workspace_spec = task.get("workspace")
                    if isinstance(workspace_spec, dict):
                        task_workspace = workspace_spec.get("path")
                    else:
                        task_workspace = None
                if not task_workspace:
                    filtered_tasks.append(task)
                    continue
                task_workspace_normalized = normalize_path(task_workspace)
                if task_workspace_normalized == workspace_normalized:
                    filtered_tasks.append(task)
            tasks = filtered_tasks

        if tasks:
            backlog_map[path] = tasks

    return backlog_map
