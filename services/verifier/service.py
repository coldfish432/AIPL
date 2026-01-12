from __future__ import annotations

import json
import time
from pathlib import Path

from . import checks  # noqa: F401
from .config import ALLOW_SKIP_TESTS, EXECUTION_CHECK_TYPES, NO_CHECKS_BEHAVIOR, REQUIRE_EXECUTION
from .context import load_task_context
from .error_collector import collect_execution_errors, generate_fix_guidance
from .registry import CHECK_REGISTRY
from .types import ReworkRequest, VerifyResult
from .utils import coerce_text, reason


def _load_policy_checks(run_dir: Path) -> list[dict]:
    policy_path = run_dir / "policy.json"
    if not policy_path.exists():
        return []
    try:
        policy_data = json.loads(policy_path.read_text(encoding="utf-8"))
        return policy_data.get("checks", []) or []
    except Exception:
        return []


def _resolve_workspace(workspace_path: Path | None, task_workspace: str | None) -> Path | None:
    workspace = workspace_path or (Path(task_workspace) if task_workspace else None)
    return workspace.resolve() if workspace else None


def _has_execution_check(checks_list: list[dict]) -> bool:
    return any(check.get("type") in EXECUTION_CHECK_TYPES for check in checks_list or [])


def _merge_checks(task_checks: list[dict], policy_checks: list[dict], high_risk: bool = False) -> list[dict]:
    if _has_execution_check(task_checks) and not high_risk:
        return list(task_checks or [])
    merged = list(task_checks or [])
    merged.extend(policy_checks or [])
    return merged


def _is_high_risk(value) -> bool:
    if value is True:
        return True
    if isinstance(value, (int, float)) and value >= 7:
        return True
    if isinstance(value, str) and value.strip().lower() in {"high", "critical"}:
        return True
    return False


def _run_checks(effective_checks: list[dict], run_dir: Path, workspace: Path | None, retry_context: dict | None):
    reasons = []
    passed = True
    log_dir = run_dir / "verification"
    check_results: list[dict] = []
    total_start = time.time()
    for idx, check in enumerate(effective_checks):
        ctype = check.get("type")
        handler = CHECK_REGISTRY.get(ctype)
        info = None
        check_start = time.time()
        if handler:
            outcome = handler(check, run_dir, workspace, log_dir, idx)
            if isinstance(outcome, tuple) and len(outcome) == 3:
                ok, r, info = outcome
            else:
                ok, r = outcome
        else:
            ok, r = False, reason("unknown_check", hint=json.dumps(check, ensure_ascii=False))
        duration_ms = int((time.time() - check_start) * 1000)
        if not ok and r:
            if check.get("soft"):
                r["severity"] = "warning"
            else:
                reasons.append(r)
                passed = False
        record = {"index": idx, "type": ctype, "ok": ok, "duration_ms": duration_ms}
        if isinstance(info, dict):
            record.update(info)
        if r:
            record["reason"] = r
        check_results.append(record)
    if not passed and retry_context:
        reasons.append(retry_context)
    total_duration_ms = int((time.time() - total_start) * 1000)
    return VerifyResult(passed=passed, reasons=reasons, check_results=check_results, total_duration_ms=total_duration_ms)


def verify_execution_requirement(check_results: list[dict], effective_checks: list[dict], passed: bool, reasons: list[dict]):
    if not REQUIRE_EXECUTION:
        return passed, reasons

    execution_checks = [c for c in effective_checks if c.get("type") in EXECUTION_CHECK_TYPES]
    execution_results = [c for c in check_results if c.get("type") in EXECUTION_CHECK_TYPES]
    if not execution_checks:
        if NO_CHECKS_BEHAVIOR == "fail":
            return False, reasons + [reason("no_execution_check_defined")]
        return passed, reasons

    executed_results = [c for c in execution_results if c.get("executed") is True]
    skipped_results = [c for c in execution_results if c.get("status") == "skipped"]
    if not executed_results:
        tests_disabled_count = sum(1 for r in skipped_results if r.get("skip_reason") == "tests_disabled")
        if ALLOW_SKIP_TESTS and skipped_results and tests_disabled_count == len(skipped_results):
            return passed, reasons + [reason("tests_skipped_allowed", severity="info")]
        skipped_commands = [r.get("cmd") for r in execution_results if r.get("status") == "skipped"]
        return False, reasons + [reason("no_commands_executed", skipped_commands=skipped_commands)]
    return passed, reasons


class VerifierService:
    def __init__(self, root: Path) -> None:
        self._root = root

    def verify_task(self, run_dir: Path, task_id: str, workspace_path: Path | None = None):
        checks_list, task_workspace, retry_context, task_risk = load_task_context(self._root, run_dir, task_id)
        policy_checks = _load_policy_checks(run_dir)
        workspace = _resolve_workspace(workspace_path, task_workspace)
        high_risk = _is_high_risk(task_risk)
        effective_checks = _merge_checks(checks_list, policy_checks, high_risk=high_risk)

        if not effective_checks:
            if NO_CHECKS_BEHAVIOR == "fail":
                passed = False
                reasons = [reason("no_checks", hint="未定义任何验证检查")]
            elif NO_CHECKS_BEHAVIOR == "warn":
                passed = True
                reasons = [reason("no_checks_warning", hint="未定义验证检查", severity="warning")]
            else:
                passed = True
                reasons = []
            self._write_verification_result(run_dir, task_id, passed, reasons, [])
            return passed, reasons

        has_http_check = any(c.get("type") == "http_check" for c in effective_checks)
        if not (workspace or has_http_check):
            reasons = [reason("workspace_required", hint="workspace path is required for non-http checks")]
            if retry_context:
                reasons.append(retry_context)
            self._write_verification_result(run_dir, task_id, False, reasons, [])
            return False, reasons

        result = _run_checks(effective_checks, run_dir, workspace, retry_context)
        passed, reasons = verify_execution_requirement(result.check_results, effective_checks, result.passed, result.reasons)
        self._write_verification_result(run_dir, task_id, passed, reasons, result.check_results, result.total_duration_ms)
        return passed, reasons

    def _write_verification_result(
        self,
        run_dir: Path,
        task_id: str,
        passed: bool,
        reasons: list[dict],
        check_results: list[dict],
        total_duration_ms: int = 0,
    ) -> None:
        executed = [c for c in check_results if c.get("executed")]
        payload = {
            "status": "success" if passed else "failed",
            "passed": passed,
            "task_id": task_id,
            "run_dir": str(run_dir),
            "checks": check_results,
            "executed_commands": executed,
            "reasons": reasons,
            "total_duration_ms": total_duration_ms,
            "ts": int(time.time()),
        }
        try:
            (run_dir / "verification_result.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            return

    def collect_errors_for_retry(
        self,
        run_dir: Path,
        round_id: int,
        max_rounds: int,
        reasons: list[dict],
        produced_files: list[str],
        workspace_path: str | Path | None,
        prev_stdout: str,
        suspected_related_files: list[str] | None = None,
    ) -> ReworkRequest:
        log_dir = run_dir / "verification"
        check_results_path = run_dir / "verification_result.json"
        check_results = []
        if check_results_path.exists():
            try:
                data = json.loads(check_results_path.read_text(encoding="utf-8"))
                check_results = data.get("checks", []) or []
            except Exception:
                check_results = []
        errors = collect_execution_errors(check_results, log_dir)
        fix_guidance = generate_fix_guidance(reasons, errors)
        code_modified = bool(produced_files)
        remaining = max(max_rounds - round_id - 1, 0)
        return ReworkRequest(
            round=round_id,
            remaining_attempts=remaining,
            why_failed=reasons,
            execution_errors=errors,
            error_summary=errors.error_summary,
            fix_guidance=fix_guidance,
            prev_stdout=prev_stdout,
            code_modified=code_modified,
            produced_files=produced_files,
            workspace=str(workspace_path or ""),
            suspected_related_files=suspected_related_files or [],
        )
