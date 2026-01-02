from __future__ import annotations

import os
from pathlib import Path


def _normalize_path(path: Path) -> str:
    raw = os.path.normpath(str(path.resolve()))
    return raw.lower() if os.name == "nt" else raw


def is_path_under(base: Path, candidate: Path) -> bool:
    base_norm = _normalize_path(base)
    cand_norm = _normalize_path(candidate)
    if cand_norm == base_norm:
        return True
    if not base_norm.endswith(os.sep):
        base_norm = base_norm + os.sep
    return cand_norm.startswith(base_norm)


def is_workspace_unsafe(root: Path, workspace: Path) -> bool:
    return is_path_under(workspace, root)
