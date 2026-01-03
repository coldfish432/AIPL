from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from config import resolve_db_path

__all__ = ["ensure_sqlite_schema", "mirror_run_to_sqlite"]


def ensure_sqlite_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, plan_id TEXT, status TEXT, updated_at INTEGER, raw_json TEXT)"
    )
    conn.execute("CREATE TABLE IF NOT EXISTS plans (plan_id TEXT PRIMARY KEY, updated_at INTEGER, raw_json TEXT)")


def mirror_run_to_sqlite(root: Path, payload: dict) -> None:
    run_id = payload.get("run_id")
    plan_id = payload.get("plan_id")
    if not run_id:
        return
    db_path = resolve_db_path(root)
    if not db_path:
        return
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        now_ms = int(time.time() * 1000)
        raw_json = json.dumps({"ok": True, "ts": int(time.time()), "data": payload}, ensure_ascii=False)
        with sqlite3.connect(str(db_path)) as conn:
            ensure_sqlite_schema(conn)
            conn.execute(
                "INSERT INTO runs(run_id, plan_id, status, updated_at, raw_json) VALUES(?,?,?,?,?) "
                "ON CONFLICT(run_id) DO UPDATE SET plan_id=excluded.plan_id, status=excluded.status, updated_at=excluded.updated_at, raw_json=excluded.raw_json",
                (run_id, plan_id, payload.get("status"), now_ms, raw_json),
            )
            conn.commit()
    except sqlite3.Error:
        return
