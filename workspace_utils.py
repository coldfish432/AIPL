"""
workspace_utils.py - workspace helper functions
"""

import hashlib
import os
from pathlib import Path
from infra.fields import get_workspace
from infra.io_utils import read_json
from infra.json_utils import read_json_dict

__all__ = [
    "normalize_workspace_path",
    "compute_workspace_id",
    "get_workspace_dir",
    "get_plan_dir",
    "get_run_dir",
    "get_backlog_dir",
]


def normalize_workspace_path(workspace: str | Path | None) -> str:
    """Normalize workspace paths so we compare consistently."""
    if not workspace:
        return ""
    path_str = str(Path(workspace).resolve())
    if os.name == "nt":
        normalized_prefixes = ("\\\\?\\", "//?/")
        for prefix in normalized_prefixes:
            if path_str.startswith(prefix):
                path_str = path_str[len(prefix) :]
                break
        path_str = path_str.lower()
    return path_str.replace("\\", "/").strip()


def compute_workspace_id(workspace: str | Path | None) -> str:
    """Compute workspace id (SHA256 prefix)."""
    if not workspace:
        return "_default"
    normalized = normalize_workspace_path(workspace)
    if not normalized:
        return "_default"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def get_workspace_dir(root: Path, workspace: str | Path | None) -> Path:
    """Return workspace artifacts root."""
    return root / "artifacts" / "workspaces" / compute_workspace_id(workspace)


def get_plan_dir(root: Path, workspace: str | Path | None, plan_id: str) -> Path:
    """Return execution directory for a plan."""
    return get_workspace_dir(root, workspace) / "executions" / plan_id


def get_run_dir(root: Path, workspace: str | Path | None, plan_id: str, run_id: str) -> Path:
    """Return run directory for a plan/run."""
    return get_plan_dir(root, workspace, plan_id) / "runs" / run_id


def get_backlog_dir(root: Path, workspace: str | Path | None) -> Path:
    """Return backlog directory for a workspace."""
    return get_workspace_dir(root, workspace) / "backlog"


def find_plan_workspace(root: Path, plan_id: str) -> str | None:
    """Find which workspace owns a plan."""
    if not plan_id:
        return None
    ws_root = root / "artifacts" / "workspaces"
    if not ws_root.exists():
        return None
    for ws_dir in ws_root.iterdir():
        if not ws_dir.is_dir():
            continue
        plan_dir = ws_dir / "executions" / plan_id
        if not plan_dir.exists():
            continue

        workspace_value: str | None = None
        cap_path = plan_dir / "capabilities.json"
        if cap_path.exists():
            try:
                workspace_value = get_workspace(read_json_dict(cap_path))
            except Exception:
                pass

        if not workspace_value:
            plan_path = plan_dir / "plan.json"
            if plan_path.exists():
                try:
                    plan_data = read_json(plan_path, default={})
                    workspace_value = plan_data.get("workspace_path") or plan_data.get("workspace_main_root")
                except Exception:
                    pass

        if workspace_value:
            return workspace_value
    return None
