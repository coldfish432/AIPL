import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


# 写入fakecodex，写入文件内容，创建目录
def _write_fake_codex(bin_dir: Path) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    fake = bin_dir / "codex_fake.py"
    fake.write_text(
        "\n".join(
            [
                "import json",
                "import os",
                "import sys",
                "",
                "schema = ''",
                "for idx, arg in enumerate(sys.argv):",
                "    if arg == '--output-schema' and idx + 1 < len(sys.argv):",
                "        schema = sys.argv[idx + 1]",
                "        break",
                "",
                "url = os.getenv('CODEX_FAKE_HTTP_URL', 'http://127.0.0.1:1/')",
                "if schema.endswith('plan.schema.json'):",
                "    plan = {",
                "        'tasks': [",
                "            {",
                "                'id': 'T1',",
                "                'title': 'integration',",
                "                'type': 'time_for_certainty',",
                "                'priority': 50,",
                "                'estimated_minutes': 1,",
                "                'dependencies': [],",
                "                'acceptance_criteria': ['outputs/summary.txt contains ok'],",
                "                'checks': [",
                "                    {'type': 'http_check', 'url': url, 'expected_status': 200},",
                "                    {'type': 'file_contains', 'path': 'outputs/summary.txt', 'needle': 'ok'},",
                "                ],",
                "            }",
                "        ]",
                "    }",
                "    print(json.dumps(plan))",
                "elif schema.endswith('codex_writes.schema.json'):",
                "    print(json.dumps({'writes': [{'target': 'run', 'path': 'outputs/summary.txt', 'content': 'ok'}], 'commands': []}))",
                "else:",
                "    print('{}')",
            ]
        ),
        encoding="utf-8",
    )
    wrapper = bin_dir / "codex"
    wrapper.write_text(
        "\n".join(
            [
                "#!/usr/bin/env sh",
                f"\"{os.sys.executable}\" \"{fake}\" \"$@\"",
            ]
        ),
        encoding="utf-8",
    )
    try:
        wrapper.chmod(0o755)
    except Exception:
        pass
    wrapper = bin_dir / "codex.cmd"
    wrapper.write_text(f"@echo off\r\n\"{os.sys.executable}\" \"{fake}\" %*\r\n", encoding="utf-8")


# cleanupartifacts，检查路径是否存在
def _cleanup_artifacts(plan_id: str) -> None:
    exec_dir = REPO_ROOT / "artifacts" / "executions" / plan_id
    backlog = REPO_ROOT / "backlog" / f"{plan_id}.json"
    plan_tasks = exec_dir / "plan.tasks.jsonl"
    if exec_dir.exists():
        shutil.rmtree(exec_dir, ignore_errors=True)
    if backlog.exists():
        backlog.unlink()
    if plan_tasks.exists():
        plan_tasks.unlink()


# test计划executionflow，执行外部命令，解析JSON
def test_plan_execution_flow(temp_workspace, mock_http_server, profile_db):
    plan_id = f"itest-{uuid.uuid4().hex}"
    bin_dir = Path(temp_workspace) / ".bin"
    _write_fake_codex(bin_dir)

    env = os.environ.copy()
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    env["AIPL_DB_PATH"] = str(profile_db)
    env["CODEX_FAKE_HTTP_URL"] = mock_http_server.url
    env["CODEX_BIN"] = str(bin_dir / ("codex.cmd" if os.name == "nt" else "codex"))

    try:
        subprocess.check_call(
            ["python", "engine_cli.py", "--root", str(REPO_ROOT), "run", "--task", "integration", "--plan-id", plan_id, "--workspace", str(temp_workspace)],
            cwd=str(REPO_ROOT),
            env=env,
        )
        exec_dir = REPO_ROOT / "artifacts" / "executions" / plan_id
        runs = list((exec_dir / "runs").iterdir())
        assert runs
        run_dir = runs[0]
        result = json.loads((run_dir / "verification_result.json").read_text(encoding="utf-8"))
        assert result["status"] == "success"
        summary = (run_dir / "outputs" / "summary.txt").read_text(encoding="utf-8")
        assert "ok" in summary
    finally:
        _cleanup_artifacts(plan_id)
