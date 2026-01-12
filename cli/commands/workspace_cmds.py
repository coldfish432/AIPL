from __future__ import annotations

import json
from pathlib import Path

from cli.utils import envelope


IGNORE_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    "target",
    ".idea",
    ".vscode",
    "coverage",
    ".next",
    ".nuxt",
    ".cache",
    "tmp",
    "temp",
}

IGNORE_FILES = {
    ".DS_Store",
    "Thumbs.db",
    ".gitignore",
    ".npmrc",
    ".yarnrc",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
}


def cmd_workspace_tree(args, root: Path):
    workspace = args.workspace
    depth_limit = getattr(args, "depth", 3) or 3

    if not workspace:
        print(json.dumps(envelope(False, error="workspace is required"), ensure_ascii=False))
        return

    workspace_path = Path(workspace).resolve()
    if not workspace_path.exists():
        print(json.dumps(envelope(False, error="workspace not found"), ensure_ascii=False))
        return
    if not workspace_path.is_dir():
        print(json.dumps(envelope(False, error="workspace is not a directory"), ensure_ascii=False))
        return

    def build_tree(path: Path, depth: int = 0):
        if depth > depth_limit:
            return None

        name = path.name
        if name.startswith(".") and name not in {".env.example", ".gitignore"}:
            return None
        if name in IGNORE_DIRS or name in IGNORE_FILES:
            return None

        if path.is_file():
            return {
                "name": name,
                "type": "file",
                "path": str(path.relative_to(workspace_path)),
            }

        if path.is_dir():
            children = []
            try:
                entries = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
                for entry in entries[:50]:
                    child = build_tree(entry, depth + 1)
                    if child:
                        children.append(child)
            except PermissionError:
                pass

            return {
                "name": name,
                "type": "directory",
                "path": str(path.relative_to(workspace_path)) if path != workspace_path else ".",
                "children": children,
            }

        return None

    tree = build_tree(workspace_path)
    data = {"tree": tree, "workspace": str(workspace_path)}
    print(json.dumps(envelope(True, data=data), ensure_ascii=False))


def cmd_workspace_read(args, root: Path):
    workspace = args.workspace
    target = args.path

    if not workspace:
        print(json.dumps(envelope(False, error="workspace is required"), ensure_ascii=False))
        return
    if not target:
        print(json.dumps(envelope(False, error="path is required"), ensure_ascii=False))
        return

    workspace_path = Path(workspace).resolve()
    file_path = workspace_path / target

    try:
        file_path = file_path.resolve()
        if not str(file_path).startswith(str(workspace_path)):
            print(json.dumps(envelope(False, error="path is outside workspace"), ensure_ascii=False))
            return
    except Exception:
        print(json.dumps(envelope(False, error="invalid path"), ensure_ascii=False))
        return

    if not file_path.exists():
        print(json.dumps(envelope(False, error="file not found"), ensure_ascii=False))
        return
    if not file_path.is_file():
        print(json.dumps(envelope(False, error="path is not a file"), ensure_ascii=False))
        return

    if file_path.stat().st_size > 1024 * 1024:
        print(json.dumps(envelope(False, error="file too large (max 1MB)"), ensure_ascii=False))
        return

    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            content = file_path.read_text(encoding="gbk")
        except Exception:
            print(json.dumps(envelope(False, error="cannot decode file content"), ensure_ascii=False))
            return
    except Exception as e:
        print(json.dumps(envelope(False, error=f"read error: {e}"), ensure_ascii=False))
        return

    data = {
        "path": target,
        "content": content,
        "size": len(content),
        "lines": content.count("\n") + 1,
    }
    print(json.dumps(envelope(True, data=data), ensure_ascii=False))
