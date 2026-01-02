from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path


class StageWorkspaceManager:
    def __init__(self, root: Path, stage_root: Path | None = None) -> None:
        self._root = root
        self._stage_root = stage_root or (root / "artifacts" / "executions" / "_stages")

    def create_stage(self, run_id: str, main_root: Path) -> dict:
        main_root = main_root.resolve()
        stage_dir = (self._stage_root / run_id).resolve()
        if stage_dir.exists():
            shutil.rmtree(stage_dir, ignore_errors=True)
        stage_dir.parent.mkdir(parents=True, exist_ok=True)

        mode = "copy"
        base_ref = None
        if (main_root / ".git").exists():
            try:
                base_ref = subprocess.check_output(
                    ["git", "-C", str(main_root), "rev-parse", "HEAD"],
                    text=True,
                    stderr=subprocess.DEVNULL,
                ).strip()
            except Exception:
                base_ref = None
            try:
                ref = base_ref or "HEAD"
                subprocess.check_call(
                    ["git", "-C", str(main_root), "worktree", "add", str(stage_dir), ref],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                mode = "worktree"
            except Exception:
                mode = "copy"

        if mode == "copy":
            if stage_dir.exists():
                shutil.rmtree(stage_dir, ignore_errors=True)
            shutil.copytree(
                main_root,
                stage_dir,
                ignore=shutil.ignore_patterns(
                    ".git",
                    "node_modules",
                    "__pycache__",
                    ".venv",
                    "artifacts",
                    "runs",
                    "outputs",
                    ".pytest_cache",
                ),
            )

        return {
            "stage_root": str(stage_dir),
            "mode": mode,
            "base_ref": base_ref,
            "created_ts": time.time(),
        }

    def remove_stage(self, stage_root: Path, main_root: Path | None = None) -> None:
        stage_root = stage_root.resolve()
        if not stage_root.exists():
            return
        if (stage_root / ".git").exists() and main_root:
            try:
                subprocess.check_call(
                    ["git", "-C", str(main_root), "worktree", "remove", "--force", str(stage_root)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return
            except Exception:
                pass
        shutil.rmtree(stage_root, ignore_errors=True)
