from pathlib import Path
import json
try:
    import tomllib
except Exception:  # pragma: no cover - py<3.11
    tomllib = None


DEFAULT_DENY = [".git", "node_modules", "target", "dist", ".venv", "__pycache__", "outputs"]


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_toml(path: Path) -> dict:
    if not tomllib:
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _add_command(commands: list[dict], cmd: str, kind: str, source: str, timeout: int) -> None:
    if not cmd:
        return
    commands.append({"cmd": cmd, "kind": kind, "source": source, "timeout": timeout})


def _select_checks(commands: list[dict]) -> list[dict]:
    checks: list[dict] = []
    test_cmds = [c for c in commands if c.get("kind") == "test"]
    if test_cmds:
        cmd = test_cmds[0]
        checks.append({"type": "command", "cmd": cmd["cmd"], "timeout": cmd["timeout"]})
        return checks
    fallback_kinds = ["build", "lint", "typecheck", "smoke"]
    for kind in fallback_kinds:
        for cmd in commands:
            if cmd.get("kind") == kind:
                checks.append({"type": "command", "cmd": cmd["cmd"], "timeout": cmd["timeout"]})
                break
    return checks


def detect_workspace(workspace: Path) -> dict:
    """
    基于文件特征给出项目类型与推荐写入/测试命令。
    仅返回简单规则，避免误伤。
    """
    workspace = workspace.resolve()
    project_type = "unknown"
    checks = []
    allow_write = []
    deny_write = DEFAULT_DENY.copy()
    commands: list[dict] = []
    detected: list[str] = []

    def exists(name: str):
        return (workspace / name).exists()

    if exists("pom.xml"):
        project_type = "maven"
        detected.append("pom.xml")
        _add_command(commands, "mvn -q test", "test", "pom.xml", 900)
        _add_command(commands, "mvn -q -DskipTests package", "build", "pom.xml", 900)
        allow_write = ["src/main/java", "src/test/java"]
    elif exists("build.gradle") or exists("build.gradle.kts"):
        project_type = "gradle"
        detected.append("build.gradle" if exists("build.gradle") else "build.gradle.kts")
        _add_command(commands, "gradle test", "test", "gradle", 900)
        _add_command(commands, "gradle build", "build", "gradle", 900)
        allow_write = ["src/main/java", "src/test/java"]
    elif exists("package.json"):
        project_type = "node"
        detected.append("package.json")
        pkg = _load_json(workspace / "package.json")
        scripts = pkg.get("scripts") if isinstance(pkg, dict) else {}
        if isinstance(scripts, dict):
            for name in sorted(scripts.keys()):
                cmd = f"npm run {name}"
                if name == "test" or name.startswith("test:"):
                    _add_command(commands, cmd, "test", "package.json", 600)
                elif name == "build" or name.startswith("build:"):
                    _add_command(commands, cmd, "build", "package.json", 600)
                elif name == "lint" or name.startswith("lint:"):
                    _add_command(commands, cmd, "lint", "package.json", 600)
                elif name in {"start", "dev"}:
                    _add_command(commands, f"{cmd} -- --help", "smoke", "package.json", 300)
        if exists("tsconfig.json"):
            detected.append("tsconfig.json")
            _add_command(commands, "npm exec -- tsc --noEmit", "typecheck", "tsconfig.json", 600)
        allow_write = ["src", "tests", "test"]
    elif exists("pyproject.toml") or exists("requirements.txt"):
        project_type = "python"
        if exists("pyproject.toml"):
            detected.append("pyproject.toml")
            data = _load_toml(workspace / "pyproject.toml")
            tool = data.get("tool", {}) if isinstance(data, dict) else {}
            if isinstance(tool, dict) and "pytest" in tool:
                _add_command(commands, "python -m pytest -q", "test", "pyproject.toml", 600)
        if exists("requirements.txt"):
            detected.append("requirements.txt")
        if exists("pytest.ini") or exists("tests"):
            detected.append("pytest.ini" if exists("pytest.ini") else "tests")
            _add_command(commands, "python -m pytest -q", "test", "tests", 600)
        _add_command(commands, "python -m compileall .", "build", "python", 300)
        allow_write = ["src", "tests", ""]
    else:
        allow_write = [""]

    checks = _select_checks(commands)
    return {
        "project_type": project_type,
        "allow_write": allow_write,
        "deny_write": deny_write,
        "checks": checks,
        "capabilities": {
            "project_type": project_type,
            "detected": detected,
            "commands": commands,
        },
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="检测 workspace 特征并输出 JSON")
    parser.add_argument("workspace")
    parser.add_argument("--output", help="输出文件路径，不传则打印")
    args = parser.parse_args()

    cfg = detect_workspace(Path(args.workspace))
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        print(json.dumps(cfg, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
