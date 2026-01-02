import json
from pathlib import Path

import pytest

from services.verifier import VerifierService


REPO_ROOT = Path(__file__).resolve().parents[1]


# testdisallowedcommandsrejected，解析JSON，创建目录
@pytest.mark.parametrize(
    "cmd",
    [
        "rm -rf /",
        "curl http://example.com",
        "powershell Invoke-WebRequest http://example.com",
        "python -m pytest && rm -rf /",
        "python -m pytest ; rm -rf /",
        "python -m pytest | rm -rf /",
    ],
)
# testdisallowedcommandsrejected
def test_disallowed_commands_rejected(tmp_path, backlog_task, fake_runner, cmd):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    checks = [{"type": "command", "cmd": cmd, "timeout": 1}]
    task_id, _ = backlog_task(checks, workspace=workspace)

    passed, _ = VerifierService(REPO_ROOT).verify_task(run_dir, task_id, workspace_path=workspace)

    assert passed is False
    assert fake_runner.calls == []
    result = json.loads((run_dir / "verification_result.json").read_text(encoding="utf-8"))
    assert result["checks"][0]["reason"]["type"] == "command_not_allowed"
    assert result["checks"][0]["executed"] is False


# testcwdtraversalrejected，解析JSON，创建目录
def test_cwd_traversal_rejected(tmp_path, backlog_task, fake_runner):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    checks = [{"type": "command", "cmd": "python -m pytest -q", "cwd": "../..", "timeout": 1}]
    task_id, _ = backlog_task(checks, workspace=workspace)

    passed, _ = VerifierService(REPO_ROOT).verify_task(run_dir, task_id, workspace_path=workspace)

    assert passed is False
    assert fake_runner.calls == []
    result = json.loads((run_dir / "verification_result.json").read_text(encoding="utf-8"))
    assert result["checks"][0]["reason"]["type"] == "invalid_cwd"
    assert result["checks"][0]["executed"] is False
