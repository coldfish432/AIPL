from __future__ import annotations

from pathlib import Path

from ..config import ALLOWED_COMMAND_PREFIXES
from ..utils import reason


def ensure_workspace(check_type: str, workspace: Path | None):
    if workspace:
        return True, None
    return False, reason("workspace_required", check_type=check_type, hint="workspace path is required for this check")


def select_base_path(run_dir: Path, workspace: Path | None, path: str) -> Path | None:
    norm = path.replace("\\", "/")
    if norm == "outputs" or norm.startswith("outputs/"):
        return run_dir
    return workspace


def check_file_exists(base: Path, path: str):
    target = (base / path).resolve()
    try:
        target.relative_to(base.resolve())
    except Exception:
        return False, reason("invalid_path", file=path, hint="escape detected")
    if not target.exists():
        return False, reason("missing_file", file=path)
    return True, None


def check_file_contains(base: Path, path: str, needle: str):
    ok, err = check_file_exists(base, path)
    if not ok:
        return ok, err
    target = (base / path).resolve()
    text = target.read_text(encoding="utf-8", errors="replace")
    if needle not in text:
        return False, reason("content_mismatch", file=path, expected=f"contains {needle!r}", actual=text[:200])
    return True, None


def resolve_cwd(base: Path, cwd: str | None):
    if not cwd:
        return base
    target = (base / cwd).resolve()
    try:
        target.relative_to(base.resolve())
    except Exception:
        return None
    return target


def normalize_prefixes(prefixes) -> tuple[str, ...]:
    if isinstance(prefixes, str):
        return (prefixes,)
    if isinstance(prefixes, (list, tuple)):
        return tuple(p for p in prefixes if isinstance(p, str) and p)
    return ()


def is_command_allowed(cmd: str, allow_prefixes: tuple[str, ...] | None = None) -> bool:
    cmd = cmd.strip()
    if not cmd:
        return False
    if any(token in cmd for token in (";", "&&", "||", "|", "`", "$(", "\n", "\r")):
        return False
    prefixes = allow_prefixes or ALLOWED_COMMAND_PREFIXES
    return cmd.startswith(prefixes)
