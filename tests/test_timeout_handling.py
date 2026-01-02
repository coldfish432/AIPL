import json
from pathlib import Path

from services.verifier import VerifierService


REPO_ROOT = Path(__file__).resolve().parents[1]


# test超时setsstructuredfields，解析JSON，创建目录
def test_timeout_sets_structured_fields(tmp_path, backlog_task, fake_runner):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    checks = [{"type": "command", "cmd": "python -m pytest -q", "timeout": 1}]
    task_id, _ = backlog_task(checks, workspace=workspace)

    fake_runner.queue_result(
        {
            "executed": True,
            "timed_out": True,
            "returncode": None,
            "stdout": "partial stdout",
            "stderr": "partial stderr",
            "timeout_error": "timeout",
        }
    )
    passed, _ = VerifierService(REPO_ROOT).verify_task(run_dir, task_id, workspace_path=workspace)

    assert passed is False
    result = json.loads((run_dir / "verification_result.json").read_text(encoding="utf-8"))
    check = result["checks"][0]
    assert check["timed_out"] is True
    assert check["exit_code"] is None
    assert check["executed"] is True
    assert check["reason"]["type"] == "command_timeout"
    assert "evidence" in check
    assert "stdout_tail" in check["evidence"]
    assert "stderr_tail" in check["evidence"]
