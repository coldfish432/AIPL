from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional


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
    except ValueError:
        return default


def _env_list(key: str, default: List[str]) -> List[str]:
    raw = os.getenv(key)
    if raw is None:
        return default
    parts = [p.strip() for p in raw.split(",")]
    return [p for p in parts if p]


@dataclass
class CommandConfig:
    allowed_prefixes: List[str] = field(
        default_factory=lambda: ["python", "pytest", "mvn", "gradle", "npm", "node", "pnpm", "yarn"]
    )
    denied_prefixes: List[str] = field(default_factory=list)
    default_timeout: int = 300
    max_output_bytes: int = 1024 * 1024


@dataclass
class WorkspaceConfig:
    deny_write: List[str] = field(
        default_factory=lambda: [
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
    )
    max_concurrency: int = 2


@dataclass
class PolicyConfig:
    mode: str = "report-only"
    stale_seconds: int = 3600
    stale_auto_reset: bool = False

    @property
    def is_enforced(self) -> bool:
        return self.mode in {"enforce", "strict", "block"}


@dataclass
class VerifierConfig:
    max_json_bytes: int = 1024 * 1024
    http_timeout: int = 30
    command_timeout: int = 300


@dataclass
class StorageConfig:
    db_path: Optional[str] = None
    artifacts_dir: str = "artifacts"
    backlog_dir: str = "backlog"


@dataclass
class Settings:
    command: CommandConfig = field(default_factory=CommandConfig)
    workspace: WorkspaceConfig = field(default_factory=WorkspaceConfig)
    policy: PolicyConfig = field(default_factory=PolicyConfig)
    verifier: VerifierConfig = field(default_factory=VerifierConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            command=CommandConfig(
                allowed_prefixes=_env_list("AIPL_ALLOWED_COMMANDS", CommandConfig().allowed_prefixes),
                denied_prefixes=_env_list("AIPL_DENY_COMMANDS", CommandConfig().denied_prefixes),
                default_timeout=_env_int("AIPL_COMMAND_TIMEOUT", 300),
            ),
            workspace=WorkspaceConfig(
                deny_write=_env_list("AIPL_DENY_WRITE", WorkspaceConfig().deny_write),
                max_concurrency=_env_int("AIPL_MAX_CONCURRENCY", 2),
            ),
            policy=PolicyConfig(
                mode=os.getenv("AIPL_POLICY_MODE", "report-only").strip().lower(),
                stale_seconds=_env_int("AIPL_STALE_SECONDS", 3600),
                stale_auto_reset=_env_bool("AIPL_STALE_AUTO_RESET", False),
            ),
            storage=StorageConfig(
                db_path=os.getenv("AIPL_DB_PATH"),
            ),
        )


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
    return _settings


def reload_settings() -> Settings:
    global _settings
    _settings = Settings.from_env()
    return _settings


__all__ = [
    "CommandConfig",
    "WorkspaceConfig",
    "PolicyConfig",
    "VerifierConfig",
    "StorageConfig",
    "Settings",
    "get_settings",
    "reload_settings",
]
