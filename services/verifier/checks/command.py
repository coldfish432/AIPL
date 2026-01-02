from __future__ import annotations

import json
import os
from pathlib import Path

from ..config import ALLOWED_COMMAND_PREFIXES, COMMAND_TIMEOUT
from ..registry import register_check
from ..runner import get_command_runner
from ..utils import coerce_text, reason, tail
from .base import ensure_workspace, is_command_allowed, normalize_prefixes, resolve_cwd


TEST_COMMAND_PREFIXES = (
    "pytest",
    "python -m pytest",
    "python -m unittest",
    "tox",
    "nosetests",
    "go test",
    "mvn test",
    "mvn -q test",
    "gradle test",
    "./gradlew test",
    "npm test",
    "npm run test",
    "pnpm test",
    "pnpm run test",
    "yarn test",
    "yarn run test",
    "bun test",
    "cargo test",
    "jest",
    "vitest",
)


def _normalize_cmd(cmd: str) -> str:
    return " ".join(cmd.strip().lower().split())


def _is_test_command(cmd: str) -> bool:
    normalized = _normalize_cmd(cmd)
    return normalized.startswith(TEST_COMMAND_PREFIXES)


def _tests_disabled(run_dir: Path) -> bool:
    if os.getenv("AIPL_ALLOW_TESTS", "").lower() in {"1", "true", "yes"}:
        return False
    if os.getenv("AIPL_DISABLE_TESTS", "").lower() in {"1", "true", "yes"}:
        return True
    meta_path = run_dir / "meta.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
        if meta.get("disable_tests") is True:
            return True
    return False


def _run_command(cmd: str, cwd: Path, timeout: int, log_dir: Path, idx: int, expect_exit_code: int):
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / f"cmd-{idx}.stdout.txt"
    stderr_path = log_dir / f"cmd-{idx}.stderr.txt"
    timeout_path = log_dir / f"cmd-{idx}.timeout.txt"
    try:
        stdout_rel = stdout_path.relative_to(log_dir.parent).as_posix()
        stderr_rel = stderr_path.relative_to(log_dir.parent).as_posix()
        timeout_rel = timeout_path.relative_to(log_dir.parent).as_posix()
    except Exception:
        stdout_rel = stdout_path.as_posix()
        stderr_rel = stderr_path.as_posix()
        timeout_rel = timeout_path.as_posix()
    info = {
        "cmd": cmd,
        "expected_exit_code": expect_exit_code,
        "stdout_log": stdout_rel,
        "stderr_log": stderr_rel,
    }
    runner = get_command_runner()
    result = runner.run(cmd, cwd, timeout)
    executed = bool(result.get("executed", True))
    timed_out = bool(result.get("timed_out", False))
    stdout = coerce_text(result.get("stdout"))
    stderr = coerce_text(result.get("stderr"))
    evidence = {"stdout_tail": tail(stdout), "stderr_tail": tail(stderr)}
    info.update(
        {
            "executed": executed,
            "timed_out": timed_out,
            "exit_code": result.get("returncode"),
            "evidence": evidence,
        }
    )
    if not executed:
        info.update({"status": "skipped"})
        return False, reason("command_not_executed", cmd=cmd, hint="runner skipped execution"), info
    if timed_out:
        timeout_msg = coerce_text(result.get("timeout_error")) or f"timeout after {timeout}s"
        timeout_path.write_text(timeout_msg, encoding="utf-8")
        info.update({"status": "timeout", "timeout": timeout, "timeout_log": timeout_rel})
        return False, reason("command_timeout", cmd=cmd, expected=f"<= {timeout}s", actual=timeout_msg, hint=f"log: {timeout_rel}"), info

    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    returncode = result.get("returncode")
    if returncode != expect_exit_code:
        hint = f"log: {stdout_rel} / {stderr_rel}"
        info["status"] = "failed"
        return (
            False,
            reason("command_failed", cmd=cmd, expected=f"exit code {expect_exit_code}", actual=f"exit code {returncode}", hint=hint),
            info,
        )
    info["status"] = "ok"
    return True, None, info


@register_check("command")
def handle_command(check: dict, run_dir: Path, workspace: Path | None, log_dir: Path, idx: int):
    ok, err = ensure_workspace("command", workspace)
    if not ok:
        return ok, err, None
    cmd = check.get("cmd", "")
    policy_enforced = check.get("policy_enforced", True)
    allow_prefixes = normalize_prefixes(check.get("allow_prefixes")) or ALLOWED_COMMAND_PREFIXES
    if not cmd.strip():
        info = {"cmd": cmd, "status": "skipped", "executed": False, "timed_out": False, "exit_code": None, "evidence": {"stdout_tail": "", "stderr_tail": ""}}
        return False, reason("empty_command", cmd=cmd), info
    if _tests_disabled(run_dir) and _is_test_command(cmd) and workspace is None:
        info = {"cmd": cmd, "status": "skipped", "executed": False, "timed_out": False, "exit_code": None, "skip_reason": "tests_disabled", "evidence": {"stdout_tail": "", "stderr_tail": ""}}
        return True, None, info
    if policy_enforced and not is_command_allowed(cmd, allow_prefixes):
        info = {"cmd": cmd, "status": "skipped", "executed": False, "timed_out": False, "exit_code": None, "evidence": {"stdout_tail": "", "stderr_tail": ""}}
        return False, reason("command_not_allowed", cmd=cmd, expected=f"prefix in {allow_prefixes}"), info
    timeout = int(check.get("timeout", COMMAND_TIMEOUT))
    expect_exit_code = int(check.get("expect_exit_code", 0))
    cwd = resolve_cwd(workspace, check.get("cwd"))
    if not cwd:
        info = {"cmd": cmd, "status": "invalid_cwd", "executed": False, "timed_out": False, "exit_code": None, "evidence": {"stdout_tail": "", "stderr_tail": ""}}
        return False, reason("invalid_cwd", cwd=check.get("cwd")), info
    ok, err, info = _run_command(cmd, cwd, timeout, log_dir, idx, expect_exit_code)
    return ok, err, info


@register_check("command_contains")
def handle_command_contains(check: dict, run_dir: Path, workspace: Path | None, log_dir: Path, idx: int):
    ok, err = ensure_workspace("command_contains", workspace)
    if not ok:
        return ok, err, None
    cmd = check.get("cmd", "")
    needle = check.get("needle", "")
    policy_enforced = check.get("policy_enforced", True)
    allow_prefixes = normalize_prefixes(check.get("allow_prefixes")) or ALLOWED_COMMAND_PREFIXES
    if not cmd.strip():
        info = {"cmd": cmd, "status": "skipped", "executed": False, "timed_out": False, "exit_code": None, "evidence": {"stdout_tail": "", "stderr_tail": ""}}
        return False, reason("empty_command", cmd=cmd), info
    if _tests_disabled(run_dir) and _is_test_command(cmd) and workspace is None:
        info = {"cmd": cmd, "status": "skipped", "executed": False, "timed_out": False, "exit_code": None, "skip_reason": "tests_disabled", "evidence": {"stdout_tail": "", "stderr_tail": ""}}
        return True, None, info
    if policy_enforced and not is_command_allowed(cmd, allow_prefixes):
        info = {"cmd": cmd, "status": "skipped", "executed": False, "timed_out": False, "exit_code": None, "evidence": {"stdout_tail": "", "stderr_tail": ""}}
        return False, reason("command_not_allowed", cmd=cmd, expected=f"prefix in {allow_prefixes}"), info
    timeout = int(check.get("timeout", COMMAND_TIMEOUT))
    expect_exit_code = int(check.get("expect_exit_code", 0))
    cwd = resolve_cwd(workspace, check.get("cwd"))
    if not cwd:
        info = {"cmd": cmd, "status": "invalid_cwd", "executed": False, "timed_out": False, "exit_code": None, "evidence": {"stdout_tail": "", "stderr_tail": ""}}
        return False, reason("invalid_cwd", cwd=check.get("cwd")), info
    ok, err, info = _run_command(cmd, cwd, timeout, log_dir, idx, expect_exit_code)
    if not ok:
        return ok, err, info
    stdout_path = log_dir / f"cmd-{idx}.stdout.txt"
    stderr_path = log_dir / f"cmd-{idx}.stderr.txt"
    stdout = stdout_path.read_text(encoding="utf-8", errors="replace") if stdout_path.exists() else ""
    stderr = stderr_path.read_text(encoding="utf-8", errors="replace") if stderr_path.exists() else ""
    hay = (stdout or "") + "\n" + (stderr or "")
    if needle not in hay:
        if isinstance(info, dict):
            info["status"] = "output_missing"
        return False, reason("command_output_missing", cmd=cmd, expected=f"contains {needle!r}", actual=hay[:200]), info
    return True, None, info
