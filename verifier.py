from pathlib import Path
import json
import subprocess


def _reason(mtype: str, file: str | None = None, expected: str | None = None, actual: str | None = None, hint: str | None = None):
    r = {"type": mtype}
    if file:
        r["file"] = file
    if expected is not None:
        r["expected"] = expected
    if actual is not None:
        r["actual"] = actual
    if hint:
        r["hint"] = hint
    return r


def _check_file_exists(run_dir: Path, check: dict, reasons: list) -> bool:
    path = check.get("path")
    if not path:
        reasons.append(_reason("invalid_check", hint="file_exists missing path"))
        return False
    target = run_dir / path
    if not target.exists():
        reasons.append(_reason("missing_file", file=str(path)))
        return False
    return True


def _check_file_contains(run_dir: Path, check: dict, reasons: list) -> bool:
    path = check.get("path")
    needle = check.get("contains")
    if not path or needle is None:
        reasons.append(_reason("invalid_check", hint="file_contains missing path/contains"))
        return False
    target = run_dir / path
    if not target.exists():
        reasons.append(_reason("missing_file", file=str(path)))
        return False
    text = target.read_text(encoding="utf-8", errors="replace")
    if needle not in text:
        reasons.append(_reason("content_mismatch", file=str(path), expected=f"contains {needle!r}", actual=text[:200]))
        return False
    return True


def _check_command(run_dir: Path, check: dict, reasons: list) -> bool:
    cmd = check.get("cmd")
    timeout = check.get("timeout", 60)
    if not cmd:
        reasons.append(_reason("invalid_check", hint="command missing cmd"))
        return False
    try:
        result = subprocess.run(
            cmd,
            cwd=run_dir,
            shell=True,
            timeout=timeout,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired as e:
        reasons.append(_reason("command_timeout", expected=f"timeout<={timeout}s", actual=str(e), file="cmd"))
        return False
    if result.returncode != 0:
        reasons.append(
            _reason(
                "command_failed",
                expected="exit code 0",
                actual=f"code {result.returncode}",
                hint=f"stdout: {result.stdout[:300]} stderr: {result.stderr[:300]}",
                file="cmd",
            )
        )
        return False
    return True


def _run_checks(run_dir: Path, checks: list[dict]) -> tuple[bool, list]:
    reasons = []
    passed_all = True
    for check in checks:
        ctype = check.get("type")
        if ctype == "file_exists":
            ok = _check_file_exists(run_dir, check, reasons)
        elif ctype == "file_contains":
            ok = _check_file_contains(run_dir, check, reasons)
        elif ctype == "command":
            ok = _check_command(run_dir, check, reasons)
        else:
            reasons.append(_reason("unknown_check", hint=json.dumps(check, ensure_ascii=False)))
            ok = False
        if not ok:
            passed_all = False
    return passed_all, reasons


def _legacy_tasks(run_dir: Path, task_id: str):
    """兼容旧的 T001/T002/T003，便于回放旧案例"""
    if task_id == "T001":
        checks = [
            {"type": "file_exists", "path": "outputs/result.txt"},
            {"type": "file_contains", "path": "outputs/result.txt", "contains": "OK: deliverable generated"},
        ]
        return _run_checks(run_dir, checks)
    if task_id == "T002":
        checks = [
            {"type": "file_exists", "path": "outputs/summary.md"},
            {"type": "file_contains", "path": "outputs/summary.md", "contains": "Task:"},
            {"type": "file_contains", "path": "outputs/summary.md", "contains": "Run:"},
        ]
        return _run_checks(run_dir, checks)
    if task_id == "T003":
        checks = [
            {"type": "file_exists", "path": "index.md"},
            {"type": "file_contains", "path": "index.md", "contains": "## Evidence"},
        ]
        return _run_checks(run_dir, checks)
    return None

def verify_task(run_dir: Path, task_id: str):
    """
    返回 (passed, reasons) 结构化结果。
    优先读取 backlog 中的 checks（若 task_spec 提供），否则走 legacy 兼容或报 unknown_task。
    """
    # 尝试从 backlog 读取 checks
    checks = []
    task_spec_path = run_dir.parent.parent / "backlog.json"
    if task_spec_path.exists():
        try:
            spec = json.loads(task_spec_path.read_text(encoding="utf-8"))
            for t in spec.get("tasks", []):
                if t.get("id") == task_id:
                    checks = t.get("checks", [])
                    break
        except Exception:
            checks = []

    if checks:
        return _run_checks(run_dir, checks)

    legacy = _legacy_tasks(run_dir, task_id)
    if legacy is not None:
        return legacy

    return False, [_reason("unknown_task", hint=f"task_id={task_id} not supported and no checks provided")]
