from __future__ import annotations

import os
from pathlib import Path

from .settings import Settings, get_settings, reload_settings


def resolve_db_path(root: Path, env_key: str = "AIPL_DB_PATH") -> Path | None:
    env_path = os.getenv(env_key)
    if env_path:
        return Path(env_path).expanduser()
    config_path = root / "server" / "src" / "main" / "resources" / "application.yml"
    db_path = None
    if config_path.exists():
        try:
            for line in config_path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped.startswith("dbPath:"):
                    db_path = stripped.split(":", 1)[1].strip().strip("\"'") or None
                    break
        except Exception:
            db_path = None
    if not db_path:
        return root / "server" / "data" / "aipl.db"
    path = Path(db_path)
    if path.is_absolute():
        return path
    server_root = root / "server"
    candidate = server_root / path
    if candidate.exists() or candidate.parent.exists():
        return candidate
    return root / path


def _settings_snapshot() -> Settings:
    return get_settings()


DEFAULT_STALE_SECONDS = _settings_snapshot().policy.stale_seconds
DEFAULT_STALE_AUTO_RESET = _settings_snapshot().policy.stale_auto_reset
DEFAULT_ALLOWED_COMMANDS = _settings_snapshot().command.allowed_prefixes
DEFAULT_DENY_COMMANDS = _settings_snapshot().command.denied_prefixes
DEFAULT_COMMAND_TIMEOUT = _settings_snapshot().command.default_timeout
DEFAULT_MAX_CONCURRENCY = _settings_snapshot().workspace.max_concurrency
DEFAULT_DENY_WRITE = _settings_snapshot().workspace.deny_write
DEFAULT_POLICY_MODE = _settings_snapshot().policy.mode
POLICY_ENFORCED = _settings_snapshot().policy.is_enforced


__all__ = [
    "Settings",
    "get_settings",
    "reload_settings",
    "resolve_db_path",
    "DEFAULT_STALE_SECONDS",
    "DEFAULT_STALE_AUTO_RESET",
    "DEFAULT_ALLOWED_COMMANDS",
    "DEFAULT_DENY_COMMANDS",
    "DEFAULT_COMMAND_TIMEOUT",
    "DEFAULT_MAX_CONCURRENCY",
    "DEFAULT_DENY_WRITE",
    "DEFAULT_POLICY_MODE",
    "POLICY_ENFORCED",
]
