from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

from infra.path_guard import normalize_path

__all__ = ["pick_next_task"]


def pick_next_task(
    tasks_with_path: list[tuple[dict, Path]],
    plan_filter: str | None = None,
    workspace: str | None = None,
) -> Tuple[Optional[dict], Optional[Path]]:
    tasks = [t for t, _ in tasks_with_path]
    if plan_filter:
        done = {t["id"] for t in tasks if t.get("status") == "done" and t.get("plan_id") == plan_filter}
    else:
        done = {t["id"] for t in tasks if t.get("status") == "done"}

    workspace_filter = normalize_path(workspace) if workspace else None

    candidates = []
    for task, path in tasks_with_path:
        if plan_filter and task.get("plan_id") != plan_filter:
            continue
        if workspace_filter:
            task_workspace = normalize_path(task.get("workspace_path"))
            if not task_workspace or task_workspace != workspace_filter:
                continue
        if task.get("status") != "todo":
            continue
        deps = task.get("dependencies", [])
        if any(dep not in done for dep in deps):
            continue
        if task.get("type") != "time_for_certainty":
            continue
        candidates.append((task, path))

    if not candidates:
        return None, None

    candidates.sort(key=lambda item: item[0].get("priority", 0), reverse=True)
    return candidates[0]
