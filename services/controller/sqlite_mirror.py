from __future__ import annotations

import sqlite3
from pathlib import Path

from sqlite_mirror import ensure_schema as base_ensure_schema, mirror_run

__all__ = ["ensure_sqlite_schema", "mirror_run_to_sqlite"]


def ensure_sqlite_schema(conn: sqlite3.Connection) -> None:
    base_ensure_schema(conn)


def mirror_run_to_sqlite(root: Path, payload: dict) -> None:
    run_id = payload.get("run_id")
    if not run_id:
        return
    plan_id = payload.get("plan_id", "")
    status = payload.get("status") or "unknown"
    workspace = payload.get("workspace_main_root") or payload.get("workspace") or ""
    task = payload.get("task") or ""
    mirror_run(root, run_id, plan_id, workspace=workspace, status=status, task=task)
