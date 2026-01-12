from __future__ import annotations

from pathlib import Path
from typing import Any

from infra.io_utils import read_json


def read_json_dict(path: Path) -> dict[str, Any]:
    data = read_json(path, default={})
    return data if isinstance(data, dict) else {}


def read_backlog_tasks(path: Path) -> list[dict[str, Any]]:
    backlog = read_json(path, default={"tasks": []})
    tasks = backlog.get("tasks", [])
    if isinstance(tasks, list):
        return [task for task in tasks if isinstance(task, dict)]
    return []
