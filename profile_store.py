from __future__ import annotations

import json
import time
import sqlite3


def ensure_profile_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS workspace_profiles ("
        "workspace_id TEXT PRIMARY KEY,"
        "workspace_path TEXT,"
        "fingerprint TEXT,"
        "user_hard_json TEXT,"
        "system_hard_json TEXT NOT NULL,"
        "soft_draft_json TEXT,"
        "soft_approved_json TEXT,"
        "soft_version INTEGER DEFAULT 0,"
        "updated_at INTEGER"
        ")"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS profile_review_log ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "workspace_id TEXT,"
        "action TEXT,"
        "fingerprint TEXT,"
        "payload_json TEXT,"
        "ts INTEGER"
        ")"
    )


def _load_json(text: str | None):
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


def read_profile(conn: sqlite3.Connection, workspace_id: str) -> dict | None:
    cur = conn.execute(
        "SELECT workspace_id, workspace_path, fingerprint, user_hard_json, system_hard_json, "
        "soft_draft_json, soft_approved_json, soft_version, updated_at "
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
        "soft_draft": _load_json(row[5]),
        "soft_approved": _load_json(row[6]),
        "soft_version": int(row[7] or 0),
        "updated_at": int(row[8] or 0),
    }


def upsert_profile(conn: sqlite3.Connection, profile: dict) -> None:
    payload = {
        "workspace_id": profile.get("workspace_id"),
        "workspace_path": profile.get("workspace_path"),
        "fingerprint": profile.get("fingerprint"),
        "user_hard_json": json.dumps(profile.get("user_hard"), ensure_ascii=False) if profile.get("user_hard") is not None else None,
        "system_hard_json": json.dumps(profile.get("system_hard") or {}, ensure_ascii=False),
        "soft_draft_json": json.dumps(profile.get("soft_draft"), ensure_ascii=False) if profile.get("soft_draft") is not None else None,
        "soft_approved_json": json.dumps(profile.get("soft_approved"), ensure_ascii=False) if profile.get("soft_approved") is not None else None,
        "soft_version": int(profile.get("soft_version") or 0),
        "updated_at": int(profile.get("updated_at") or time.time()),
    }
    conn.execute(
        "INSERT INTO workspace_profiles("
        "workspace_id, workspace_path, fingerprint, user_hard_json, system_hard_json, "
        "soft_draft_json, soft_approved_json, soft_version, updated_at"
        ") VALUES(?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(workspace_id) DO UPDATE SET "
        "workspace_path=excluded.workspace_path,"
        "fingerprint=excluded.fingerprint,"
        "user_hard_json=excluded.user_hard_json,"
        "system_hard_json=excluded.system_hard_json,"
        "soft_draft_json=excluded.soft_draft_json,"
        "soft_approved_json=excluded.soft_approved_json,"
        "soft_version=excluded.soft_version,"
        "updated_at=excluded.updated_at",
        (
            payload["workspace_id"],
            payload["workspace_path"],
            payload["fingerprint"],
            payload["user_hard_json"],
            payload["system_hard_json"],
            payload["soft_draft_json"],
            payload["soft_approved_json"],
            payload["soft_version"],
            payload["updated_at"],
        ),
    )


def log_review(conn: sqlite3.Connection, workspace_id: str, action: str, fingerprint: str, payload: dict | None) -> None:
    conn.execute(
        "INSERT INTO profile_review_log(workspace_id, action, fingerprint, payload_json, ts) VALUES(?,?,?,?,?)",
        (
            workspace_id,
            action,
            fingerprint,
            json.dumps(payload, ensure_ascii=False) if payload is not None else None,
            int(time.time()),
        ),
    )
