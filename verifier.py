from pathlib import Path
import json
import subprocess
import textwrap


def run_codex_verify(prompt: str, root_dir: Path) -> dict:
    cmd = [
        "codex", "exec",
        "--full-auto",
        "--sandbox", "workspace-write",
        "-C", str(root_dir),
        "--skip-git-repo-check",
        "--color", "never",
    ]
    result = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=True,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "codex failed").strip())
    return json.loads(result.stdout.strip())


def snapshot_outputs(outputs_dir: Path, max_chars_per_file: int = 2000) -> dict:
    snap = {}
    if not outputs_dir.exists():
        return snap
    for p in outputs_dir.glob("**/*"):
        if p.is_file():
            rel = p.relative_to(outputs_dir.parent)
            try:
                txt = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                txt = ""
            snap[str(rel)] = txt[:max_chars_per_file]
    return snap


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
    使用 Codex 验收：提供 acceptance_criteria 和 outputs 快照，由 Codex 返回 {passed, reasons[]}。
    reasons 建议包含 type/file/expected/actual/hint。
    """
    root = Path(__file__).resolve().parent
    backlog_path = root / "backlog.json"
    acceptance = []
    if backlog_path.exists():
        try:
            spec = json.loads(backlog_path.read_text(encoding="utf-8"))
            for t in spec.get("tasks", []):
                if t.get("id") == task_id:
                    acceptance = t.get("acceptance_criteria", [])
                    break
        except Exception:
            acceptance = []

    outputs_dir = run_dir / "outputs"
    snap = snapshot_outputs(outputs_dir)

    acceptance_block = "\n".join("- " + c for c in acceptance) if acceptance else "- (none provided)"
    tmpl = (root / "prompts" / "verifier.txt").read_text(encoding="utf-8")
    prompt = tmpl.format(
        task_id=task_id,
        acceptance_block=acceptance_block,
        snap_json=json.dumps(snap, ensure_ascii=False),
    )

    try:
        result = run_codex_verify(prompt, root)
    except Exception as e:
        return False, [{"type": "verifier_error", "hint": str(e)}]

    passed = bool(result.get("passed"))
    reasons = result.get("reasons", [])
    if not isinstance(reasons, list):
        reasons = [{"type": "invalid_output", "hint": str(reasons)}]
    return passed, reasons
