from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from difflib import unified_diff
from pathlib import Path


IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "artifacts", "runs", "outputs", ".pytest_cache"}


@dataclass
class PatchsetResult:
    patchset_path: Path
    changed_files_path: Path
    changed_files: list[dict]


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _iter_files(root: Path) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for base, dirs, filenames in os.walk(root):
        rel = Path(base).relative_to(root)
        if any(part in IGNORE_DIRS for part in rel.parts):
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for name in filenames:
            full = Path(base) / name
            rel_path = full.relative_to(root).as_posix()
            files[rel_path] = full
    return files


def _read_text(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    return text.splitlines(keepends=True)


def build_patchset(stage_root: Path, main_root: Path, run_dir: Path) -> PatchsetResult:
    stage_root = stage_root.resolve()
    main_root = main_root.resolve()
    patch_dir = run_dir / "patchset"
    patch_dir.mkdir(parents=True, exist_ok=True)
    patch_path = patch_dir / "patchset.diff"
    changed_files_path = patch_dir / "changed_files.json"

    stage_files = _iter_files(stage_root)
    main_files = _iter_files(main_root)

    changed: list[dict] = []
    diffs: list[str] = []

    all_paths = set(stage_files.keys()) | set(main_files.keys())
    for rel_path in sorted(all_paths):
        stage_path = stage_files.get(rel_path)
        main_path = main_files.get(rel_path)
        if stage_path and not main_path:
            changed.append({"path": rel_path, "status": "added"})
            diff = unified_diff([], _read_text(stage_path), fromfile=f"a/{rel_path}", tofile=f"b/{rel_path}")
            diffs.extend(list(diff))
        elif main_path and not stage_path:
            changed.append({"path": rel_path, "status": "deleted"})
            diff = unified_diff(_read_text(main_path), [], fromfile=f"a/{rel_path}", tofile=f"b/{rel_path}")
            diffs.extend(list(diff))
        else:
            if not stage_path or not main_path:
                continue
            if _hash_file(stage_path) != _hash_file(main_path):
                changed.append({"path": rel_path, "status": "modified"})
                diff = unified_diff(
                    _read_text(main_path),
                    _read_text(stage_path),
                    fromfile=f"a/{rel_path}",
                    tofile=f"b/{rel_path}",
                )
                diffs.extend(list(diff))

    patch_path.write_text("".join(diffs), encoding="utf-8")
    payload = {
        "generated_at": int(time.time()),
        "changed_files": changed,
    }
    changed_files_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return PatchsetResult(
        patchset_path=patch_path,
        changed_files_path=changed_files_path,
        changed_files=changed,
    )


def apply_patchset(stage_root: Path, main_root: Path, changed_files: list[dict]) -> list[dict]:
    stage_root = stage_root.resolve()
    main_root = main_root.resolve()
    results: list[dict] = []
    for item in changed_files:
        rel = item.get("path")
        status = item.get("status")
        if not rel or not isinstance(rel, str):
            results.append({"path": rel, "status": status, "result": "skipped", "reason": "invalid_path"})
            continue
        if rel.startswith("/") or rel.startswith("\\") or ".." in Path(rel).parts:
            results.append({"path": rel, "status": status, "result": "skipped", "reason": "unsafe_path"})
            continue
        src = stage_root / rel
        dest = main_root / rel
        if status == "deleted":
            if dest.exists():
                try:
                    dest.unlink()
                    results.append({"path": rel, "status": status, "result": "deleted"})
                except Exception as exc:
                    results.append({"path": rel, "status": status, "result": "failed", "reason": str(exc)})
            else:
                results.append({"path": rel, "status": status, "result": "missing"})
            continue
        if not src.exists():
            results.append({"path": rel, "status": status, "result": "missing_source"})
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            dest.write_bytes(src.read_bytes())
            results.append({"path": rel, "status": status, "result": "copied"})
        except Exception as exc:
            results.append({"path": rel, "status": status, "result": "failed", "reason": str(exc)})
    return results
