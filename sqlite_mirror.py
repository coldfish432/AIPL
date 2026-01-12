"""
sqlite_mirror.py - SQLite mirror operations
"""

import json
import sqlite3
import time
from pathlib import Path

from config import resolve_db_path
from workspace_utils import normalize_workspace_path, compute_workspace_id

__all__ = [
    "ensure_schema",
    "mirror_plan",
    "mirror_run",
    "update_run_status",
    "delete_plan",
    "delete_run",
]


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Ensure the required tables exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS plans (
            plan_id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            workspace_path TEXT,
            tasks_count INTEGER DEFAULT 0,
            input_task TEXT,
            updated_at INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            plan_id TEXT NOT NULL,
            workspace_id TEXT NOT NULL,
            workspace_path TEXT,
            status TEXT DEFAULT 'unknown',
            task TEXT,
            updated_at INTEGER
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_plans_ws ON plans(workspace_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_ws ON runs(workspace_id)")


def mirror_plan(root: Path, plan_id: str, workspace: str, tasks_count: int = 0, input_task: str = "") -> None:
    """Insert/update plan metadata in the database."""
    db_path = resolve_db_path(root)
    if not db_path:
        return

    workspace_id = compute_workspace_id(workspace)
    workspace_path = normalize_workspace_path(workspace)
    now_ms = int(time.time() * 1000)

    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(db_path)) as conn:
            ensure_schema(conn)
            conn.execute(
                """INSERT INTO plans(plan_id, workspace_id, workspace_path, tasks_count, input_task, updated_at)
                   VALUES(?,?,?,?,?,?)
                   ON CONFLICT(plan_id) DO UPDATE SET
                       workspace_id=excluded.workspace_id,
                       workspace_path=excluded.workspace_path,
                       tasks_count=excluded.tasks_count,
                       input_task=excluded.input_task,
                       updated_at=excluded.updated_at""",
                (plan_id, workspace_id, workspace_path, tasks_count, input_task, now_ms),
            )
            conn.commit()
    except Exception as e:
        print(f"[SQLITE] mirror_plan error: {e}")


def mirror_run(root: Path, run_id: str, plan_id: str, workspace: str, status: str = "unknown", task: str = "") -> None:
    """Insert/update run metadata in the database."""
    db_path = resolve_db_path(root)
    if not db_path:
        return

    workspace_id = compute_workspace_id(workspace)
    workspace_path = normalize_workspace_path(workspace)
    now_ms = int(time.time() * 1000)

    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(db_path)) as conn:
            ensure_schema(conn)
            conn.execute(
                """INSERT INTO runs(run_id, plan_id, workspace_id, workspace_path, status, task, updated_at)
                   VALUES(?,?,?,?,?,?,?)
                   ON CONFLICT(run_id) DO UPDATE SET
                       plan_id=excluded.plan_id,
                       workspace_id=excluded.workspace_id,
                       workspace_path=excluded.workspace_path,
                       status=excluded.status,
                       task=excluded.task,
                       updated_at=excluded.updated_at""",
                (run_id, plan_id, workspace_id, workspace_path, status, task, now_ms),
            )
            conn.commit()
    except Exception as e:
        print(f"[SQLITE] mirror_run error: {e}")


def update_run_status(root: Path, run_id: str, status: str) -> None:
    """Update the status only for an existing run."""
    db_path = resolve_db_path(root)
    if not db_path or not db_path.exists():
        return

    try:
        now_ms = int(time.time() * 1000)
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(
                "UPDATE runs SET status=?, updated_at=? WHERE run_id=?",
                (status, now_ms, run_id),
            )
            conn.commit()
    except Exception:
        pass


def delete_plan(root: Path, plan_id: str) -> None:
    """Remove plan and its runs from the database."""
    db_path = resolve_db_path(root)
    if not db_path or not db_path.exists():
        return

    try:
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute("DELETE FROM runs WHERE plan_id=?", (plan_id,))
            conn.execute("DELETE FROM plans WHERE plan_id=?", (plan_id,))
            conn.commit()
    except Exception:
        pass


def delete_run(root: Path, run_id: str) -> None:
    """Remove a single run entry."""
    db_path = resolve_db_path(root)
    if not db_path or not db_path.exists():
        return

    try:
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute("DELETE FROM runs WHERE run_id=?", (run_id,))
            conn.commit()
    except Exception:
        pass
