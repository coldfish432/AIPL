from __future__ import annotations

import json
from pathlib import Path
import os

SCAN_DEPTH = 3
MAX_FILE_KB = 64

README_NAMES = {"readme", "readme.md", "readme.txt"}
BUILD_FILES = {
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "go.mod",
    "cargo.toml",
}
TEST_ENTRY_FILES = {
    "pytest.ini",
    "tox.ini",
    "setup.cfg",
    "package.json",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
}


def _limited_read(path: Path, max_kb: int) -> str:
    try:
        data = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    limit = max_kb * 1024
    return data[:limit]


def _walk_limited(root: Path, max_depth: int) -> list[Path]:
    root = root.resolve()
    paths = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel = Path(dirpath).relative_to(root)
        if len(rel.parts) >= max_depth:
            dirnames[:] = []
            continue
        for name in filenames:
            paths.append(Path(dirpath) / name)
    return paths


def _detect_project_type(root: Path) -> str:
    if (root / "pom.xml").exists() or (root / "build.gradle").exists() or (root / "build.gradle.kts").exists():
        return "java"
    if (root / "package.json").exists():
        return "node"
    if (root / "pyproject.toml").exists() or (root / "requirements.txt").exists():
        return "python"
    if (root / "go.mod").exists():
        return "go"
    if (root / "Cargo.toml").exists():
        return "rust"
    return "unknown"


def _suggest_commands(project_type: str, root: Path) -> list[str]:
    if project_type == "java":
        if (root / "pom.xml").exists():
            return ["mvn -q test"]
        return ["gradle test"]
    if project_type == "node":
        return ["npm test"]
    if project_type == "python":
        return ["python -m pytest -q"]
    return []


def _collect_conventions(root: Path) -> list[str]:
    conventions = []
    for name in ("src", "tests", "test", "docs", "scripts", "configs"):
        if (root / name).exists():
            conventions.append(f"dir:{name}")
    for name in ("pyproject.toml", "package.json", "pom.xml", "build.gradle", "build.gradle.kts"):
        if (root / name).exists():
            conventions.append(f"config:{name}")
    return conventions


def _checks_templates(project_type: str, root: Path) -> list[dict]:
    templates = [
        {"type": "file_exists", "path": "outputs/summary.txt"},
        {"type": "file_contains", "path": "outputs/summary.txt", "needle": "ok"},
    ]
    cmd = _suggest_commands(project_type, root)
    if cmd:
        templates.append({"type": "command", "cmd": cmd[0], "timeout": 300})
    return templates


def _path_rules() -> list[str]:
    return [
        "checks.path must be relative to workspace or outputs/",
        "no drive letters, no colon, no .. segments",
        "allowed chars: A-Z a-z 0-9 . _ / -",
        "no braces, quotes, or template tokens",
    ]


def propose_soft_profile(workspace: Path, fingerprint: str | None) -> dict:
    root = workspace.resolve()
    project_type = _detect_project_type(root)
    build_and_test = _suggest_commands(project_type, root)
    conventions = _collect_conventions(root)

    limited_paths = _walk_limited(root, SCAN_DEPTH)
    readme_summary = None
    for p in limited_paths:
        if not p.is_file():
            continue
        if p.name.lower() in README_NAMES:
            readme_summary = _limited_read(p, MAX_FILE_KB).splitlines()[:10]
            break

    test_entries = []
    for p in limited_paths:
        if not p.is_file():
            continue
        if p.name in TEST_ENTRY_FILES:
            test_entries.append(p.relative_to(root).as_posix())

    draft = {
        "project_type": project_type,
        "build_and_test": build_and_test,
        "code_style_hints": [
            "prefer small diffs",
            "keep public APIs stable",
            "avoid large refactors unless asked",
        ],
        "conventions": conventions,
        "checks_templates": _checks_templates(project_type, root),
        "path_rules": _path_rules(),
        "scan_limits": {"max_depth": SCAN_DEPTH, "max_file_kb": MAX_FILE_KB},
        "readme_summary": readme_summary or [],
        "test_entry_files": test_entries,
        "fingerprint": fingerprint,
    }
    return json.loads(json.dumps(draft, ensure_ascii=False))
