from __future__ import annotations

from pathlib import Path
from typing import Optional

from infra.io_utils import read_json
from workspace_utils import normalize_workspace_path

__all__ = ["list_backlog_files", "load_backlog_map", "load_backlog_map_filtered"]


def list_backlog_files(root: Path) -> list[Path]:
    backlog_files: list[Path] = []
    default_dir = root / "backlog"
    if default_dir.exists():
        backlog_files.extend(default_dir.glob("*.json"))

    workspace_root = root / "artifacts" / "workspaces"
    if workspace_root.exists():
        for ws_dir in workspace_root.iterdir():
            if not ws_dir.is_dir():
                continue
            ws_backlog = ws_dir / "backlog"
            if not ws_backlog.exists():
                continue
            backlog_files.extend(ws_backlog.glob("*.json"))

    return sorted(backlog_files)


def load_backlog_map(root: Path) -> dict[Path, list[dict]]:
    backlog_map: dict[Path, list[dict]] = {}
    for path in list_backlog_files(root):
        data = read_json(path, default={"tasks": []})
        backlog_map[path] = (data or {}).get("tasks", [])
    return backlog_map


def load_backlog_map_filtered(root: Path, workspace: Optional[str] = None) -> dict[Path, list[dict]]:
    """Load backlog map, optionally filtering tasks by workspace path."""
    backlog_map: dict[Path, list[dict]] = {}
    workspace_normalized = normalize_workspace_path(workspace) if workspace else None

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
                task_workspace_normalized = normalize_workspace_path(task_workspace)
                if task_workspace_normalized == workspace_normalized:
                    filtered_tasks.append(task)
            tasks = filtered_tasks

        if tasks:
            backlog_map[path] = tasks

    return backlog_map
