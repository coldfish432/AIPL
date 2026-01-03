from __future__ import annotations

from pathlib import Path

from config.settings import get_settings
from detect_workspace import detect_workspace

__all__ = ["auto_select_workspace"]


def auto_select_workspace(workspace: Path) -> Path:
    workspace = workspace.resolve()
    info = detect_workspace(workspace)
    detected = info.get("detected") or []
    if info.get("project_type") != "unknown" or detected or info.get("checks"):
        return workspace
    candidates: list[tuple[int, Path]] = []
    deny = set(get_settings().workspace.deny_write or [])
    for child in sorted(workspace.iterdir()):
        if not child.is_dir():
            continue
        name = child.name
        if name.startswith(".") or name in deny:
            continue
        sub_info = detect_workspace(child)
        sub_detected = sub_info.get("detected") or []
        if sub_info.get("project_type") == "unknown" and not sub_detected and not sub_info.get("checks"):
            continue
        score = len(sub_detected) + (1 if sub_info.get("checks") else 0)
        candidates.append((score, child))
    if not candidates:
        return workspace
    candidates.sort(key=lambda item: (-item[0], item[1].name.lower()))
    return candidates[0][1]
