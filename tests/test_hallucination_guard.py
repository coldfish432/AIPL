import json
from pathlib import Path

from services import verifier_service


REPO_ROOT = Path(__file__).resolve().parents[1]


# testhallucinationguardrequiresexecution，解析JSON，创建目录
def test_hallucination_guard_requires_execution(tmp_path, backlog_task, fake_runner):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    checks = [{"type": "command", "cmd": "python -m pytest -q", "timeout": 1}]
    task_id, _ = backlog_task(checks, workspace=workspace)

    fake_runner.queue_result({"executed": False, "timed_out": False, "returncode": 0, "stdout": "", "stderr": ""})
    passed, _ = verifier_service.verify_task(REPO_ROOT, run_dir, task_id, workspace_path=workspace)

    assert passed is False
    result = json.loads((run_dir / "verification_result.json").read_text(encoding="utf-8"))
    assert result["status"] == "failed"
    assert result["executed_commands"] == []
    assert result["checks"][0]["executed"] is False
    assert any(r.get("type") in {"command_not_executed", "no_commands_executed"} for r in result["reasons"])
