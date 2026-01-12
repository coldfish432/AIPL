from __future__ import annotations

from typing import Mapping, Any


def _coerce_text(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    return None


def get_task_id(obj: Mapping[str, Any]) -> str | None:
    for key in ("task_id", "step_id", "id"):
        value = _coerce_text(obj.get(key))
        if value:
            return value
    return None


def get_workspace(obj: Mapping[str, Any]) -> str | None:
    for key in ("workspace", "workspace_main_root", "workspace_path"):
        value = _coerce_text(obj.get(key))
        if value:
            return value
    return None
