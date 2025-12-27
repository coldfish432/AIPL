from __future__ import annotations

import os
from pathlib import Path


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except Exception:
        return default


def _env_list(key: str, default: list[str]) -> list[str]:
    raw = os.getenv(key)
    if raw is None:
        return default
    parts = [p.strip() for p in raw.split(",")]
    return [p for p in parts if p]


DEFAULT_STALE_SECONDS = int(os.getenv("AIPL_STALE_SECONDS", "3600"))
DEFAULT_STALE_AUTO_RESET = _env_bool("AIPL_STALE_AUTO_RESET", False)
DEFAULT_ALLOWED_COMMANDS = _env_list(
    "AIPL_ALLOWED_COMMANDS",
    ["python", "pytest", "mvn", "gradle", "npm", "node", "pnpm", "yarn"],
)
DEFAULT_COMMAND_TIMEOUT = _env_int("AIPL_COMMAND_TIMEOUT", 300)
DEFAULT_MAX_CONCURRENCY = _env_int("AIPL_MAX_CONCURRENCY", 2)
DEFAULT_DENY_WRITE = _env_list(
    "AIPL_DENY_WRITE",
    [".git", "node_modules", "target", "dist", "build", ".venv", "__pycache__", "artifacts", "runs", "outputs"],
)


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
