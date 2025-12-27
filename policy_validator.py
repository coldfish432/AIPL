from __future__ import annotations

import re
from pathlib import Path

ALLOWED_PATH_RE = re.compile(r"^[A-Za-z0-9._/\-]+$")


def default_path_rules() -> list[str]:
    return [
        "path must be relative to workspace or outputs/",
        "no drive letters, no colon, no .. segments",
        "allowed chars: A-Z a-z 0-9 . _ / -",
        "no braces, quotes, or template tokens",
    ]


def _norm_rel_path(path: str) -> str:
    return path.replace("\\", "/").strip()


def is_safe_relative_path(path: str) -> bool:
    if not isinstance(path, str):
        return False
    path = _norm_rel_path(path)
    if not path:
        return False
    if path.startswith("/") or path.startswith("\\"):
        return False
    if ":" in path:
        return False
    parts = Path(path).parts
    if any(p == ".." for p in parts):
        return False
    if not ALLOWED_PATH_RE.match(path):
        return False
    return True


def _is_under(path: str, roots: list[str]) -> bool:
    path = _norm_rel_path(path)
    for root in roots:
        root = _norm_rel_path(root)
        if root == "":
            return True
        if path == root or path.startswith(root.rstrip("/") + "/"):
            return True
    return False


def is_write_allowed(rel_path: str, allow_write: list[str], deny_write: list[str]) -> bool:
    if not is_safe_relative_path(rel_path):
        return False
    if deny_write and _is_under(rel_path, deny_write):
        return False
    if not allow_write:
        return True
    return _is_under(rel_path, allow_write)


def validate_checks(checks: list[dict], allowed_commands: list[str], command_whitelist: list[str] | None = None) -> tuple[list[dict], list[dict]]:
    cleaned = []
    reasons: list[dict] = []
    for idx, check in enumerate(checks or []):
        if not isinstance(check, dict):
            reasons.append({"type": "invalid_check", "index": idx, "reason": "not_object"})
            continue
        ctype = check.get("type")
        if not ctype:
            reasons.append({"type": "invalid_check", "index": idx, "reason": "missing_type"})
            continue
        if ctype in {"file_exists", "file_contains", "json_schema"}:
            path = check.get("path", "")
            if not is_safe_relative_path(path):
                reasons.append({"type": "invalid_check_path", "index": idx, "check_type": ctype, "path": path})
                continue
        if ctype in {"command", "command_contains"}:
            cmd = (check.get("cmd") or "").strip()
            if not any(cmd.startswith(p) for p in allowed_commands):
                reasons.append({"type": "command_not_allowed", "index": idx, "cmd": cmd, "expected": allowed_commands})
                continue
            if command_whitelist is not None and cmd not in command_whitelist:
                reasons.append({"type": "command_not_in_whitelist", "index": idx, "cmd": cmd})
                continue
            cwd = check.get("cwd")
            if cwd and not is_safe_relative_path(cwd):
                reasons.append({"type": "invalid_cwd", "index": idx, "cwd": cwd})
                continue
            check = dict(check)
            check["allow_prefixes"] = allowed_commands
            check["cwd"] = "."
        cleaned.append(check)
    return cleaned, reasons


def validate_writes(writes: list[dict], allow_write: list[str], deny_write: list[str]) -> tuple[list[dict], list[dict]]:
    cleaned = []
    reasons = []
    for idx, w in enumerate(writes or []):
        if not isinstance(w, dict):
            reasons.append({"type": "invalid_write", "index": idx, "reason": "not_object"})
            continue
        target = w.get("target", "")
        path = w.get("path", "")
        if target not in {"workspace", "run"}:
            reasons.append({"type": "invalid_write_target", "index": idx, "target": target})
            continue
        if not is_safe_relative_path(path):
            reasons.append({"type": "invalid_write_path", "index": idx, "target": target, "path": path})
            continue
        if target == "workspace":
            if not is_write_allowed(path, allow_write, deny_write):
                reasons.append({"type": "write_not_allowed", "index": idx, "path": path})
                continue
        cleaned.append(w)
    return cleaned, reasons


def validate_commands(commands: list, allowed_commands: list[str], default_timeout: int) -> tuple[list[dict], list[dict]]:
    cleaned = []
    reasons = []
    for idx, item in enumerate(commands or []):
        if isinstance(item, dict):
            cmd = (item.get("cmd") or "").strip()
            try:
                timeout = int(item.get("timeout") or default_timeout)
            except Exception:
                timeout = int(default_timeout)
        else:
            cmd = str(item).strip()
            timeout = int(default_timeout)
        if not cmd:
            continue
        if not any(cmd.startswith(p) for p in allowed_commands):
            reasons.append({"type": "command_not_allowed", "index": idx, "cmd": cmd, "expected": allowed_commands})
            continue
        if timeout <= 0:
            timeout = int(default_timeout)
        cleaned.append({"cmd": cmd, "timeout": timeout})
    return cleaned, reasons
