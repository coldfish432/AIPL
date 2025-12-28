from pathlib import Path

from services.controller_service import format_checks, pick_next_task, write_verification_report


# test选择下一任务respectsdepsandpriority
def test_pick_next_task_respects_deps_and_priority(tmp_path):
    path = tmp_path / "backlog.json"
    tasks = [
        {"id": "t1", "status": "done", "type": "time_for_certainty"},
        {"id": "t2", "status": "todo", "type": "time_for_certainty", "dependencies": ["t1"], "priority": 10},
        {"id": "t3", "status": "todo", "type": "time_for_certainty", "dependencies": ["missing"], "priority": 99},
        {"id": "t4", "status": "todo", "type": "other", "priority": 100},
        {"id": "t5", "status": "todo", "type": "time_for_certainty", "priority": 50},
    ]
    tasks_with_path = [(t, path) for t in tasks]
    task, _ = pick_next_task(tasks_with_path)
    assert task["id"] == "t5"


# test写入验证报告，读取文件内容，创建目录
def test_write_verification_report(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    checks = [
        {"type": "command", "cmd": "python -m pytest -q", "timeout": 60},
        {"type": "file_exists", "path": "outputs/summary.txt"},
    ]
    reasons = [{"type": "command_failed"}]
    write_verification_report(run_dir, "task-1", "plan-1", str(tmp_path), False, reasons, checks)

    report = (run_dir / "verification_report.md").read_text(encoding="utf-8")
    assert "- task_id: task-1" in report
    assert "command: python -m pytest -q" in report
    assert "file_exists: outputs/summary.txt" in report


# test格式化检查项输出lines
def test_format_checks_outputs_lines():
    checks = [{"type": "command_contains", "cmd": "python -m pytest -q", "needle": "ok", "timeout": 30}]
    lines = format_checks(checks)
    assert "command_contains" in lines[0]
