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
from profile_store import ensure_profile_tables, read_profile, upsert_profile, log_review
from soft_proposer import propose_soft_profile

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
    db_path = resolve_db_path(root)
    if not db_path:
        return None
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    ensure_profile_tables(conn)
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
            "soft_draft": None,
            "soft_approved": None,
            "soft_version": 0,
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
        if created:
            profile.setdefault("soft_version", 0)
        upsert_profile(conn, profile)
    conn.close()

    return {
        **profile,
        "hard_validation_reasons": hard_reasons,
        "effective_hard": effective_hard,
        "created": created,
        "fingerprint_changed": fingerprint_changed,
    }


# proposesoft
def propose_soft(root: Path, workspace: Path, reason: str) -> dict:
    workspace = workspace.resolve()
    profile = ensure_profile(root, workspace)
    draft = propose_soft_profile(workspace, profile.get("fingerprint"))
    conn = _open_profile_db(root)
    if not conn:
        return profile
    with conn:
        stored = read_profile(conn, profile["workspace_id"]) or profile
        stored["soft_draft"] = draft
        stored["updated_at"] = int(time.time())
        upsert_profile(conn, stored)
        log_review(conn, profile["workspace_id"], "propose", profile.get("fingerprint") or "", {"reason": reason, "draft": draft})
    conn.close()
    profile["soft_draft"] = draft
    return profile


# approvesoft
def approve_soft(root: Path, workspace: Path) -> dict:
    workspace = workspace.resolve()
    profile = ensure_profile(root, workspace)
    conn = _open_profile_db(root)
    if not conn:
        return profile
    with conn:
        stored = read_profile(conn, profile["workspace_id"]) or profile
        draft = stored.get("soft_draft")
        if draft is not None:
            stored["soft_approved"] = draft
            stored["soft_version"] = int(stored.get("soft_version") or 0) + 1
            stored["updated_at"] = int(time.time())
            upsert_profile(conn, stored)
            log_review(conn, profile["workspace_id"], "approve", profile.get("fingerprint") or "", {"draft": draft, "soft_version": stored["soft_version"]})
        profile = stored
    conn.close()
    return profile


# rejectsoft
def reject_soft(root: Path, workspace: Path) -> dict:
    workspace = workspace.resolve()
    profile = ensure_profile(root, workspace)
    conn = _open_profile_db(root)
    if not conn:
        return profile
    with conn:
        stored = read_profile(conn, profile["workspace_id"]) or profile
        stored["soft_draft"] = None
        stored["updated_at"] = int(time.time())
        upsert_profile(conn, stored)
        log_review(conn, profile["workspace_id"], "reject", profile.get("fingerprint") or "", {"reason": "manual_reject"})
        profile = stored
    conn.close()
    return profile


# 加载档案
def load_profile(root: Path, workspace: Path) -> dict | None:
    workspace = workspace.resolve()
    workspace_id = compute_workspace_id(workspace)
    conn = _open_profile_db(root)
    if not conn:
        return None
    with conn:
        profile = read_profile(conn, workspace_id)
    conn.close()
    return profile


# 判断是否需要proposeonfailure，检查路径是否存在，解析JSON
def should_propose_on_failure(root: Path, workspace: Path, threshold: int = 2, limit: int = 20) -> bool:
    workspace = workspace.resolve()
    reasons_count: dict[str, int] = {}
    run_dirs: list[Path] = []
    exec_root = root / "artifacts" / "executions"
    if exec_root.exists():
        for plan_dir in exec_root.iterdir():
            runs_dir = plan_dir / "runs"
            if runs_dir.exists():
                for run_dir in runs_dir.iterdir():
                    if run_dir.is_dir():
                        run_dirs.append(run_dir)
    legacy_runs = root / "artifacts" / "runs"
    if legacy_runs.exists():
        for run_dir in legacy_runs.iterdir():
            if run_dir.is_dir():
                run_dirs.append(run_dir)
    run_dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    checked = 0
    for run_dir in run_dirs:
        if checked >= limit:
            break
        meta_path = run_dir / "meta.json"
        ver_path = run_dir / "steps" / "step-01"
        if not meta_path.exists() or not ver_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if Path(meta.get("workspace_path", "")).resolve() != workspace:
            continue
        latest_round = None
        rounds = [p for p in ver_path.iterdir() if p.is_dir() and p.name.startswith("round-")]
        if rounds:
            rounds.sort(key=lambda p: p.name)
            latest_round = rounds[-1] / "verification.json"
        if not latest_round or not latest_round.exists():
            continue
        try:
            ver = json.loads(latest_round.read_text(encoding="utf-8"))
        except Exception:
            continue
        if ver.get("passed") is True:
            continue
        for reason in ver.get("reasons", []) or []:
            rtype = reason.get("type")
            if not rtype:
                continue
            reasons_count[rtype] = reasons_count.get(rtype, 0) + 1
        checked += 1
    return any(count >= threshold for count in reasons_count.values())


class ProfileService:
    # 确保档案
    def ensure_profile(self, root: Path, workspace: Path) -> dict:
        return ensure_profile(root, workspace)

    # proposesoft
    def propose_soft(self, root: Path, workspace: Path, reason: str) -> dict:
        return propose_soft(root, workspace, reason)

    # approvesoft
    def approve_soft(self, root: Path, workspace: Path) -> dict:
        return approve_soft(root, workspace)

    # rejectsoft
    def reject_soft(self, root: Path, workspace: Path) -> dict:
        return reject_soft(root, workspace)

    # 加载档案
    def load_profile(self, root: Path, workspace: Path) -> dict | None:
        return load_profile(root, workspace)

    # 判断是否需要proposeonfailure
    def should_propose_on_failure(self, root: Path, workspace: Path, threshold: int = 2, limit: int = 20) -> bool:
        return should_propose_on_failure(root, workspace, threshold=threshold, limit=limit)


__all__ = [
    "DEFAULT_ALLOWED_COMMANDS",
    "DEFAULT_COMMAND_TIMEOUT",
    "DEFAULT_DENY_WRITE",
    "DEFAULT_MAX_CONCURRENCY",
    "compute_fingerprint",
    "ensure_profile",
    "propose_soft",
    "approve_soft",
    "reject_soft",
    "load_profile",
    "should_propose_on_failure",
    "ProfileService",
]
