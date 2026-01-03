from __future__ import annotations

import os
import sys
import tokenize
from pathlib import Path


SKIP_DIRS = {
    ".git",
    ".tmp_custom",
    ".venv",
    ".pytest_cache",
    "__pycache__",
    "artifacts",
    "runs",
    "outputs",
    "node_modules",
    "dist",
    "build",
    "target",
    "ui-electron",
}


def should_skip_directory(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return False
    return any(part in SKIP_DIRS for part in parts)


def iter_python_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        if should_skip_directory(current, root):
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for filename in filenames:
            if filename.endswith(".py"):
                yield current / filename


def compile_paths(paths: list[str]) -> int:
    root = Path.cwd()
    success = True
    for path_str in paths:
        path = (root / path_str).resolve()
        if not path.exists():
            print(f"skip missing path: {path_str}", file=sys.stderr)
            continue
        targets = [path] if path.is_file() else iter_python_files(path)
        for file_path in targets:
            if file_path.is_dir():
                continue
            try:
                with tokenize.open(file_path) as handle:
                    source = handle.read()
                compile(source, str(file_path), "exec")
            except Exception as exc:  # noqa: BLE001
                success = False
                print(f"compile failed: {file_path}: {exc}", file=sys.stderr)
    return 0 if success else 1


def main() -> int:
    args = [arg for arg in sys.argv[1:] if not arg.startswith("-")]
    if not args:
        args = ["."]
    return compile_paths(args)


if __name__ == "__main__":
    raise SystemExit(main())
