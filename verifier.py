import json
import subprocess
from pathlib import Path


def _reason(mtype: str, **kwargs):
    r = {"type": mtype}
    for k, v in kwargs.items():
        if v is not None:
            r[k] = v
    return r


def _run_command(cmd: str, cwd: Path, timeout: int, log_dir: Path, idx: int):
    log_dir.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            shell=True,
            timeout=timeout,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired as e:
        (log_dir / f"cmd-{idx}.timeout.txt").write_text(str(e), encoding="utf-8")
        return False, _reason("command_timeout", cmd=cmd, expected=f"<= {timeout}s", actual=str(e), hint=f"log: verification/cmd-{idx}.timeout.txt")

    (log_dir / f"cmd-{idx}.stdout.txt").write_text(result.stdout or "", encoding="utf-8")
    (log_dir / f"cmd-{idx}.stderr.txt").write_text(result.stderr or "", encoding="utf-8")
    if result.returncode != 0:
        hint = f"log: verification/cmd-{idx}.stdout.txt / cmd-{idx}.stderr.txt"
        return False, _reason("command_failed", cmd=cmd, expected="exit code 0", actual=f"exit code {result.returncode}", hint=hint)
    return True, None


def _check_file_exists(base: Path, path: str):
    target = (base / path).resolve()
    try:
        target.relative_to(base.resolve())
    except Exception:
        return False, _reason("invalid_path", file=path, hint="escape detected")
    if not target.exists():
        return False, _reason("missing_file", file=path)
    return True, None


def _check_file_contains(base: Path, path: str, needle: str):
    ok, reason = _check_file_exists(base, path)
    if not ok:
        return ok, reason
    target = (base / path).resolve()
    text = target.read_text(encoding="utf-8", errors="replace")
    if needle not in text:
        return False, _reason("content_mismatch", file=path, expected=f"contains {needle!r}", actual=text[:200])
    return True, None


def verify_task(run_dir: Path, task_id: str, workspace_path: Path | None = None):
    """
    优先执行 checks（任务定义 > policy > legacy）。
    返回 (passed, reasons[])
    """
    root = Path(__file__).resolve().parent
    backlog_path = root / "backlog.json"
    acceptance = []
    checks = []
    task_workspace = None
    if backlog_path.exists():
        spec = json.loads(backlog_path.read_text(encoding="utf-8"))
        for t in spec.get("tasks", []):
            if t.get("id") == task_id:
                acceptance = t.get("acceptance_criteria", [])
                checks = t.get("checks", [])
                if isinstance(t.get("workspace"), dict):
                    task_workspace = t["workspace"].get("path")
                break

    # policy 兜底 checks
    policy_checks = []
    policy_path = run_dir / "policy.json"
    if not checks and policy_path.exists():
        try:
            policy_data = json.loads(policy_path.read_text(encoding="utf-8"))
            policy_checks = policy_data.get("checks", []) or []
        except Exception:
            policy_checks = []

    workspace = workspace_path or (Path(task_workspace) if task_workspace else None)
    if workspace:
        workspace = workspace.resolve()

    effective_checks = checks or policy_checks
    if effective_checks and workspace:
        reasons = []
        passed = True
        log_dir = run_dir / "verification"
        for idx, check in enumerate(effective_checks):
            ctype = check.get("type")
            if ctype == "file_exists":
                ok, r = _check_file_exists(workspace, check.get("path", ""))
            elif ctype == "file_contains":
                ok, r = _check_file_contains(workspace, check.get("path", ""), check.get("needle", ""))
            elif ctype == "command":
                timeout = int(check.get("timeout", 300))
                ok, r = _run_command(check.get("cmd", ""), workspace, timeout, log_dir, idx)
            else:
                ok, r = False, _reason("unknown_check", hint=json.dumps(check, ensure_ascii=False))
            if not ok and r:
                reasons.append(r)
                passed = False
        return passed, reasons

    # 兼容旧的 T00x
    legacy = _legacy_tasks(run_dir, task_id)
    if legacy is not None:
        return legacy

    outputs_dir = run_dir / "outputs"
    if outputs_dir.exists():
        return True, []
    return False, [{"type": "unknown", "hint": "no checks provided and no outputs found"}]


def _legacy_tasks(run_dir: Path, task_id: str):
    """兼容旧的 T001/T002/T003，便于回放旧案例"""
    def _run_checks(checks):
        reasons = []
        passed_all = True
        for c in checks:
            if c["type"] == "file_exists":
                ok, r = _check_file_exists(run_dir, c["path"])
            else:
                ok, r = _check_file_contains(run_dir, c["path"], c["contains"])
            if not ok:
                passed_all = False
                reasons.append(r)
        return passed_all, reasons

    if task_id == "T001":
        checks = [
            {"type": "file_exists", "path": "outputs/result.txt"},
            {"type": "file_contains", "path": "outputs/result.txt", "contains": "OK: deliverable generated"},
        ]
        return _run_checks(checks)
    if task_id == "T002":
        checks = [
            {"type": "file_exists", "path": "outputs/summary.md"},
            {"type": "file_contains", "path": "outputs/summary.md", "contains": "Task:"},
            {"type": "file_contains", "path": "outputs/summary.md", "contains": "Run:"},
        ]
        return _run_checks(checks)
    if task_id == "T003":
        checks = [
            {"type": "file_exists", "path": "index.md"},
            {"type": "file_contains", "path": "index.md", "contains": "## Evidence"},
        ]
        return _run_checks(checks)
    return None


__all__ = ["verify_task"]
