from __future__ import annotations

import json
import shutil
import tarfile
import time
from pathlib import Path


_IGNORE_NAMES = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "artifacts",
    "runs",
    "outputs",
    ".pytest_cache",
}


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _should_ignore(path: Path, root: Path) -> bool:
    try:
        rel = path.resolve().relative_to(root.resolve())
    except Exception:
        return True
    return any(part in _IGNORE_NAMES for part in rel.parts)


class ChainWorkspaceManager:
    """管理链式执行工作区（动态缓存继承）。"""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._chains_dir = root / "artifacts" / "chains"

    def _chain_dir(self, batch_id: str) -> Path:
        return self._chains_dir / batch_id

    def _create_snapshot(self, source_dir: Path, snapshot_path: Path) -> None:
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(snapshot_path, "w:gz") as tar:
            for path in source_dir.rglob("*"):
                if _should_ignore(path, source_dir):
                    continue
                arcname = path.relative_to(source_dir)
                tar.add(path, arcname=arcname)

    def _restore_snapshot(self, snapshot_path: Path, dest_dir: Path) -> None:
        if dest_dir.exists():
            shutil.rmtree(dest_dir, ignore_errors=True)
        dest_dir.mkdir(parents=True, exist_ok=True)
        with tarfile.open(snapshot_path, "r:gz") as tar:
            tar.extractall(dest_dir)

    def create_chain(self, batch_id: str, main_root: Path) -> dict:
        chain_dir = self._chain_dir(batch_id)
        workspace_dir = chain_dir / "workspace"
        if workspace_dir.exists():
            shutil.rmtree(workspace_dir, ignore_errors=True)
        shutil.copytree(
            main_root,
            workspace_dir,
            ignore=shutil.ignore_patterns(*sorted(_IGNORE_NAMES)),
        )
        initial_snapshot = chain_dir / "snapshots" / "initial_snapshot.tar.gz"
        self._create_snapshot(workspace_dir, initial_snapshot)
        meta = {
            "batch_id": batch_id,
            "main_root": str(main_root),
            "latest_completed_run": None,
            "latest_snapshot": str(initial_snapshot),
            "updated_at": time.time(),
        }
        _write_json(chain_dir / "meta.json", meta)
        return meta

    def ensure_chain(self, batch_id: str, main_root: Path) -> dict:
        chain_dir = self._chain_dir(batch_id)
        meta_path = chain_dir / "meta.json"
        if meta_path.exists():
            meta = _read_json(meta_path)
            if meta:
                return meta
        return self.create_chain(batch_id, main_root)

    def get_inherit_source(self, batch_id: str) -> dict:
        chain_meta = _read_json(self._chain_dir(batch_id) / "meta.json")
        latest_run = chain_meta.get("latest_completed_run")
        latest_snapshot = chain_meta.get("latest_snapshot")
        return {
            "source": f"run_{latest_run}" if latest_run else "initial",
            "snapshot_path": latest_snapshot,
            "inherited_from_run": latest_run,
        }

    def create_run_stage(self, batch_id: str, run_id: str, stage_root: Path) -> dict:
        inherit_info = self.get_inherit_source(batch_id)
        snapshot_path = Path(inherit_info["snapshot_path"])
        self._restore_snapshot(snapshot_path, stage_root)
        return {
            "stage_root": str(stage_root),
            "mode": "snapshot",
            "base_ref": inherit_info["inherited_from_run"],
            "inherited_from": inherit_info["inherited_from_run"],
        }

    def complete_run(self, batch_id: str, run_id: str, stage_root: Path) -> dict:
        chain_dir = self._chain_dir(batch_id)
        snapshot_path = chain_dir / "snapshots" / f"{run_id}.tar.gz"
        self._create_snapshot(stage_root, snapshot_path)
        meta = _read_json(chain_dir / "meta.json")
        meta.update(
            {
                "latest_completed_run": run_id,
                "latest_snapshot": str(snapshot_path),
                "updated_at": time.time(),
            }
        )
        _write_json(chain_dir / "meta.json", meta)
        return meta

    def fail_run(self, batch_id: str, run_id: str, error: str = "") -> dict:
        chain_dir = self._chain_dir(batch_id)
        meta = _read_json(chain_dir / "meta.json")
        meta.update({"last_failed_run": run_id, "last_error": error, "updated_at": time.time()})
        _write_json(chain_dir / "meta.json", meta)
        return meta
