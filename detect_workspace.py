from pathlib import Path
import json


DEFAULT_DENY = [".git", "node_modules", "target", "dist", ".venv", "__pycache__", "outputs"]


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

    def exists(name: str):
        return (workspace / name).exists()

    if exists("pom.xml"):
        project_type = "maven"
        checks.append({"type": "command", "cmd": "mvn -q test", "timeout": 900})
        allow_write = ["src/main/java", "src/test/java"]
    elif exists("build.gradle") or exists("build.gradle.kts"):
        project_type = "gradle"
        checks.append({"type": "command", "cmd": "gradle test", "timeout": 900})
        allow_write = ["src/main/java", "src/test/java"]
    elif exists("package.json"):
        project_type = "node"
        checks.append({"type": "command", "cmd": "npm test", "timeout": 600})
        allow_write = ["src", "tests", "test"]
    elif exists("pyproject.toml") or exists("requirements.txt"):
        project_type = "python"
        checks.append({"type": "command", "cmd": "python -m pytest -q", "timeout": 600})
        allow_write = ["src", "tests", ""]
    else:
        allow_write = [""]

    return {
        "project_type": project_type,
        "allow_write": allow_write,
        "deny_write": deny_write,
        "checks": checks,
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
