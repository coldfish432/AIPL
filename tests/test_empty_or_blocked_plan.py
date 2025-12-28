import json
from pathlib import Path

from services import verifier_service


REPO_ROOT = Path(__file__).resolve().parents[1]


# testempty计划fails，解析JSON，创建目录
def test_empty_plan_fails(tmp_path, backlog_task):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    task_id, _ = backlog_task([])
    passed, reasons = verifier_service.verify_task(REPO_ROOT, run_dir, task_id)

    assert passed is False
    assert any(r.get("type") == "no_checks" for r in reasons)
    result = json.loads((run_dir / "verification_result.json").read_text(encoding="utf-8"))
    assert result["executed_commands"] == []


# testblocked计划rejected，解析JSON，创建目录
def test_blocked_plan_rejected(tmp_path, backlog_task, fake_runner):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    checks = [{"type": "command", "cmd": "rm -rf /", "timeout": 1}]
    task_id, _ = backlog_task(checks, workspace=workspace)

    passed, _ = verifier_service.verify_task(REPO_ROOT, run_dir, task_id, workspace_path=workspace)

    assert passed is False
    assert fake_runner.calls == []
    result = json.loads((run_dir / "verification_result.json").read_text(encoding="utf-8"))
    assert result["checks"][0]["executed"] is False
    assert result["checks"][0]["reason"]["type"] == "command_not_allowed"
