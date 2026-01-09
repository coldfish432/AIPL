from __future__ import annotations

import hashlib
import os
import time
import json
import sqlite3
from pathlib import Path

import tomllib

from config import (
    DEFAULT_ALLOWED_COMMANDS,
    DEFAULT_COMMAND_TIMEOUT,
    DEFAULT_DENY_WRITE,
    DEFAULT_MAX_CONCURRENCY,
    resolve_db_path,
)
from profile_store import ensure_profile_tables, read_profile, upsert_profile

_MEMORY_CONN: sqlite3.Connection | None = None
_MEMORY_MODE = False


def _connect_memory_db() -> sqlite3.Connection:
    global _MEMORY_CONN, _MEMORY_MODE
    if _MEMORY_CONN is None:
        _MEMORY_CONN = sqlite3.connect(":memory:")
        try:
            _MEMORY_CONN.execute("PRAGMA journal_mode=MEMORY")
            _MEMORY_CONN.execute("PRAGMA temp_store=MEMORY")
        except Exception:
            pass
    _MEMORY_MODE = True
    return _MEMORY_CONN


def _close_conn(conn: sqlite3.Connection | None) -> None:
    if conn is None:
        return
    if _MEMORY_MODE and conn is _MEMORY_CONN:
        return
    try:
        conn.close()
    except Exception:
        pass

FINGERPRINT_FILES = [
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "go.mod",
    "Cargo.toml",
]
FINGERPRINT_GLOBS = ["*.sln"]


# 规范化工作区路径
def normalize_workspace_path(workspace: Path) -> str:
    path = workspace.resolve()
    raw = str(path)
    return raw.lower() if os.name == "nt" else raw


# 计算工作区ID
def compute_workspace_id(workspace: Path) -> str:
    norm = normalize_workspace_path(workspace)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


# 收集fingerprintfiles，检查路径是否存在
def _collect_fingerprint_files(workspace: Path) -> list[Path]:
    files: list[Path] = []
    for name in FINGERPRINT_FILES:
        p = workspace / name
        if p.exists():
            files.append(p)
    for pattern in FINGERPRINT_GLOBS:
        files.extend(sorted(workspace.glob(pattern)))
    uniq = {p.resolve() for p in files if p.is_file()}
    return sorted(uniq, key=lambda p: p.as_posix())


# 计算fingerprint
def compute_fingerprint(workspace: Path) -> str:
    h = hashlib.sha256()
    files = _collect_fingerprint_files(workspace)
    for p in files:
        rel = p.relative_to(workspace).as_posix()
        h.update(rel.encode("utf-8"))
        try:
            h.update(p.read_bytes())
        except Exception:
            h.update(b"<unreadable>")
    if not files:
        h.update(b"no_key_files")
    return h.hexdigest()


# coerce列出
def _coerce_list(value) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value if isinstance(v, str) and v.strip()]
    return None


# 规范化relentries
def _normalize_rel_entries(items: list[str] | None) -> list[str] | None:
    if items is None:
        return None
    normed = []
    for item in items:
        cleaned = item.replace("\\", "/").strip()
        normed.append(cleaned)
    return normed


# 加载userhard策略，检查路径是否存在，解析JSON
def load_user_hard_policy(workspace: Path) -> dict | None:
    json_path = workspace / "aipl.policy.json"
    toml_path = workspace / "aipl.policy.toml"
    if json_path.exists():
        try:
            return json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            return None
    if toml_path.exists():
        try:
            return tomllib.loads(toml_path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def write_user_hard_policy(workspace: Path, user_hard: dict | None) -> tuple[dict | None, list[dict]]:
    cleaned, reasons = sanitize_user_hard(user_hard)
    json_path = workspace / "aipl.policy.json"
    if cleaned is None:
        if json_path.exists():
            try:
                json_path.unlink()
            except Exception:
                pass
        return None, reasons
    json_path.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return cleaned, reasons


# 构建systemhard策略
def build_system_hard_policy(workspace: Path) -> dict:
    return {
        "allow_write": [""],
        "deny_write": DEFAULT_DENY_WRITE.copy(),
        "allowed_commands": DEFAULT_ALLOWED_COMMANDS.copy(),
        "command_timeout": DEFAULT_COMMAND_TIMEOUT,
        "max_concurrency": DEFAULT_MAX_CONCURRENCY,
        "workspace_path": str(workspace.resolve()),
    }


# sanitizeuserhard
def sanitize_user_hard(user_hard: dict | None) -> tuple[dict | None, list[dict]]:
    if not isinstance(user_hard, dict):
        return None, []
    reasons = []
    cleaned: dict = {}
    allow_write = _normalize_rel_entries(_coerce_list(user_hard.get("allow_write")))
    deny_write = _normalize_rel_entries(_coerce_list(user_hard.get("deny_write")))
    allowed_commands = _coerce_list(user_hard.get("allowed_commands"))
    if allow_write is not None:
        cleaned["allow_write"] = allow_write
    if deny_write is not None:
        cleaned["deny_write"] = deny_write
    if allowed_commands is not None:
        cleaned["allowed_commands"] = allowed_commands
    for key in ("command_timeout", "max_concurrency"):
        if key in user_hard:
            try:
                val = int(user_hard[key])
                if val > 0:
                    cleaned[key] = val
                else:
                    reasons.append({"type": "invalid_hard_value", "field": key, "value": user_hard[key]})
            except Exception:
                reasons.append({"type": "invalid_hard_value", "field": key, "value": user_hard[key]})
    return cleaned, reasons


# 合并hard策略
def merge_hard_policy(system_hard: dict, user_hard: dict | None) -> tuple[dict, list[dict]]:
    sanitized_user, reasons = sanitize_user_hard(user_hard)
    effective = dict(system_hard)
    if sanitized_user:
        for key, val in sanitized_user.items():
            effective[key] = val
    return effective, reasons


# 打开档案db，创建目录
def _open_profile_db(root: Path) -> sqlite3.Connection | None:
    global _MEMORY_MODE
    db_path = resolve_db_path(root)
    if not db_path:
        return None
    db_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        conn = sqlite3.connect(str(db_path))
    except sqlite3.OperationalError:
        conn = _connect_memory_db()
    except Exception:
        return None
    try:
        # 使用内存事务日志，避免在受限文件系统上删除/创建 journal 文件失败
        conn.execute("PRAGMA journal_mode=MEMORY")
        conn.execute("PRAGMA temp_store=MEMORY")
    except Exception:
        if conn is not _MEMORY_CONN:
            try:
                conn = _connect_memory_db()
            except Exception:
                return None
    try:
        ensure_profile_tables(conn)
    except sqlite3.OperationalError:
        try:
            conn = _connect_memory_db()
            ensure_profile_tables(conn)
        except Exception:
            return None
    return conn


# 确保档案
def ensure_profile(root: Path, workspace: Path) -> dict:
    workspace = workspace.resolve()
    workspace_id = compute_workspace_id(workspace)
    fingerprint = compute_fingerprint(workspace)
    system_hard = build_system_hard_policy(workspace)
    user_hard_raw = load_user_hard_policy(workspace)
    user_hard_clean, hard_reasons = sanitize_user_hard(user_hard_raw)
    effective_hard, _ = merge_hard_policy(system_hard, user_hard_clean)

    conn = _open_profile_db(root)
    if not conn:
        return {
            "workspace_id": workspace_id,
            "workspace_path": str(workspace),
            "fingerprint": fingerprint,
            "system_hard": system_hard,
            "user_hard": user_hard_clean,
            "hard_validation_reasons": hard_reasons,
            "effective_hard": effective_hard,
            "created": False,
            "fingerprint_changed": False,
        }

    with conn:
        existing = read_profile(conn, workspace_id)
        created = existing is None
        fingerprint_changed = bool(existing and existing.get("fingerprint") != fingerprint)
        profile = existing or {}
        profile.update(
            {
                "workspace_id": workspace_id,
                "workspace_path": str(workspace),
                "fingerprint": fingerprint,
                "user_hard": user_hard_clean,
                "system_hard": system_hard,
                "updated_at": int(time.time()),
            }
        )
        upsert_profile(conn, profile)
    _close_conn(conn)

    return {
        **profile,
        "hard_validation_reasons": hard_reasons,
        "effective_hard": effective_hard,
        "created": created,
        "fingerprint_changed": fingerprint_changed,
    }


# 加载档案
def load_profile(root: Path, workspace: Path) -> dict | None:
    workspace = workspace.resolve()
    workspace_id = compute_workspace_id(workspace)
    conn = _open_profile_db(root)
    if not conn:
        return None
    with conn:
        profile = read_profile(conn, workspace_id)
    _close_conn(conn)
    return profile


class ProfileService:
    # 确保档案
    def ensure_profile(self, root: Path, workspace: Path) -> dict:
        return ensure_profile(root, workspace)

    # 加载档案
    def load_profile(self, root: Path, workspace: Path) -> dict | None:
        return load_profile(root, workspace)

    def update_user_hard(self, root: Path, workspace: Path, user_hard: dict | None) -> dict:
        write_user_hard_policy(workspace, user_hard)
        return ensure_profile(root, workspace)


__all__ = [
    "DEFAULT_ALLOWED_COMMANDS",
    "DEFAULT_COMMAND_TIMEOUT",
    "DEFAULT_DENY_WRITE",
    "DEFAULT_MAX_CONCURRENCY",
    "compute_fingerprint",
    "ensure_profile",
    "load_profile",
    "ProfileService",
    "write_user_hard_policy",
]
