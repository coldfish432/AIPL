"""Global configuration constants and helpers for the CLI/engine integration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional


# ---------------------------------------------------------------------------
# Command configuration
# ---------------------------------------------------------------------------
DEFAULT_ALLOWED_COMMANDS: List[str] = [
    "python",
    "pytest",
    "mvn",
    "gradle",
    "npm",
    "node",
    "pnpm",
    "yarn",
]

DEFAULT_DENY_COMMANDS: List[str] = []

DEFAULT_COMMAND_TIMEOUT: int = 300


# ---------------------------------------------------------------------------
# Workspace configuration
# ---------------------------------------------------------------------------
DEFAULT_DENY_WRITE: List[str] = [
    ".git",
    "node_modules",
    "target",
    "dist",
    "build",
    ".venv",
    "__pycache__",
    "artifacts",
    "runs",
    "outputs",
]

DEFAULT_MAX_CONCURRENCY: int = 2


# ---------------------------------------------------------------------------
# Stale task configuration
# ---------------------------------------------------------------------------
DEFAULT_STALE_SECONDS: int = 3600
DEFAULT_STALE_AUTO_RESET: bool = False


# ---------------------------------------------------------------------------
# Strategy configuration helpers
# ---------------------------------------------------------------------------
def _env_bool(key: str, default: bool = False) -> bool:
    """Return a boolean flag from the environment."""
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


_POLICY_MODE = os.getenv("AIPL_POLICY_MODE", "report-only").strip().lower()
POLICY_ENFORCED: bool = _POLICY_MODE in {"enforce", "strict", "block"}


# ---------------------------------------------------------------------------
# Database lookup helpers
# ---------------------------------------------------------------------------
def resolve_db_path(root: Path) -> Optional[Path]:
    """
    Resolve the SQLite database path for the CLI process.

    Java injects the path via `--db-path`, which the Python CLI copies into
    the `AIPL_DB_PATH` environment variable. Modules that write to the
    database must call this helper so they can locate the correct file.

    Args:
        root: Engine root directory (reserved for future use).
    """
    del root
    env_path = os.getenv("AIPL_DB_PATH")
    if env_path:
        path = Path(env_path)
        if not path.is_absolute():
            path = path.resolve()
        return path
    return None


__all__ = [
    "DEFAULT_ALLOWED_COMMANDS",
    "DEFAULT_DENY_COMMANDS",
    "DEFAULT_COMMAND_TIMEOUT",
    "DEFAULT_DENY_WRITE",
    "DEFAULT_MAX_CONCURRENCY",
    "DEFAULT_STALE_SECONDS",
    "DEFAULT_STALE_AUTO_RESET",
    "POLICY_ENFORCED",
    "resolve_db_path",
]
