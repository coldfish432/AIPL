from __future__ import annotations

import json
import time
import sqlite3


# 确保档案tables
def ensure_profile_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS workspace_profiles ("
        "workspace_id TEXT PRIMARY KEY,"
        "workspace_path TEXT,"
        "fingerprint TEXT,"
        "user_hard_json TEXT,"
        "system_hard_json TEXT NOT NULL,"
        "updated_at INTEGER"
        ")"
    )


# 加载JSON，解析JSON
def _load_json(text: str | None):
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


# 读取档案
def read_profile(conn: sqlite3.Connection, workspace_id: str) -> dict | None:
    cur = conn.execute(
        "SELECT workspace_id, workspace_path, fingerprint, user_hard_json, system_hard_json, "
        "updated_at "
        "FROM workspace_profiles WHERE workspace_id=?",
        (workspace_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    return {
        "workspace_id": row[0],
        "workspace_path": row[1],
        "fingerprint": row[2],
        "user_hard": _load_json(row[3]),
        "system_hard": _load_json(row[4]) or {},
        "updated_at": int(row[5] or 0),
    }


# upsert档案，序列化JSON
def upsert_profile(conn: sqlite3.Connection, profile: dict) -> None:
    payload = {
        "workspace_id": profile.get("workspace_id"),
        "workspace_path": profile.get("workspace_path"),
        "fingerprint": profile.get("fingerprint"),
        "user_hard_json": json.dumps(profile.get("user_hard"), ensure_ascii=False) if profile.get("user_hard") is not None else None,
        "system_hard_json": json.dumps(profile.get("system_hard") or {}, ensure_ascii=False),
        "updated_at": int(profile.get("updated_at") or time.time()),
    }
    conn.execute(
        "INSERT INTO workspace_profiles("
        "workspace_id, workspace_path, fingerprint, user_hard_json, system_hard_json, "
        "updated_at"
        ") VALUES(?,?,?,?,?,?) "
        "ON CONFLICT(workspace_id) DO UPDATE SET "
        "workspace_path=excluded.workspace_path,"
        "fingerprint=excluded.fingerprint,"
        "user_hard_json=excluded.user_hard_json,"
        "system_hard_json=excluded.system_hard_json,"
        "updated_at=excluded.updated_at",
        (
            payload["workspace_id"],
            payload["workspace_path"],
            payload["fingerprint"],
            payload["user_hard_json"],
            payload["system_hard_json"],
            payload["updated_at"],
        ),
    )
