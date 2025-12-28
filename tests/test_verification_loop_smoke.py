import json
from pathlib import Path

from services import verifier_service


REPO_ROOT = Path(__file__).resolve().parents[1]


# test验证循环smoke，解析JSON，创建目录
def test_verification_loop_smoke(tmp_path, backlog_task, fake_runner):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    checks = [{"type": "command", "cmd": "python -m pytest -q", "timeout": 1}]
    task_id, _ = backlog_task(checks, workspace=workspace)

    fake_runner.queue_result({"executed": True, "timed_out": False, "returncode": 1, "stdout": "", "stderr": "fail"})
    passed, _ = verifier_service.verify_task(REPO_ROOT, run_dir, task_id, workspace_path=workspace)
    assert passed is False

    fake_runner.queue_result({"executed": True, "timed_out": False, "returncode": 0, "stdout": "ok", "stderr": ""})
    passed, _ = verifier_service.verify_task(REPO_ROOT, run_dir, task_id, workspace_path=workspace)
    assert passed is True

    result = json.loads((run_dir / "verification_result.json").read_text(encoding="utf-8"))
    assert result["status"] == "success"
    assert len(result["executed_commands"]) == 1
