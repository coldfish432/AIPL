from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from config import DEFAULT_ALLOWED_COMMANDS
from state import ACTIVE_STATUSES

ALLOWED_COMMAND_PREFIXES = tuple(DEFAULT_ALLOWED_COMMANDS)
MAX_JSON_BYTES = 1024 * 1024
MAX_SCHEMA_DEPTH = 20
MAX_SCHEMA_ITEMS = 100

CHECK_REGISTRY: dict[str, callable] = {}


# 注册检查
def register_check(name: str):
    # decorator
    def decorator(fn):
        CHECK_REGISTRY[name] = fn
        return fn
    return decorator


# 原因
def _reason(mtype: str, **kwargs):
    r = {"type": mtype}
    for k, v in kwargs.items():
        if v is not None:
            r[k] = v
    return r


# tail
def _tail(text: str, max_len: int = 500) -> str:
    if not text:
        return ""
    return text[-max_len:]


# coercetext
def _coerce_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


class CommandRunner:
    # 运行
    def run(self, cmd: str, cwd: Path, timeout: int) -> dict:
        raise NotImplementedError


class SubprocessRunner(CommandRunner):
    # 运行，执行外部命令
    def run(self, cmd: str, cwd: Path, timeout: int) -> dict:
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
            return {
                "executed": True,
                "timed_out": True,
                "returncode": None,
                "stdout": _coerce_text(getattr(e, "stdout", "")),
                "stderr": _coerce_text(getattr(e, "stderr", "")),
                "timeout_error": _coerce_text(e),
            }
        return {
            "executed": True,
            "timed_out": False,
            "returncode": result.returncode,
            "stdout": result.stdout or "",
            "stderr": result.stderr or "",
        }


_DEFAULT_COMMAND_RUNNER = SubprocessRunner()
_COMMAND_RUNNER: CommandRunner | None = None


# 设置命令runner
def set_command_runner(runner: CommandRunner | None) -> None:
    global _COMMAND_RUNNER
    _COMMAND_RUNNER = runner


# 获取命令runner
def _get_command_runner() -> CommandRunner:
    return _COMMAND_RUNNER or _DEFAULT_COMMAND_RUNNER


# 运行命令，写入文件内容，创建目录
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
    runner = _get_command_runner()
    result = runner.run(cmd, cwd, timeout)
    executed = bool(result.get("executed", True))
    timed_out = bool(result.get("timed_out", False))
    stdout = _coerce_text(result.get("stdout"))
    stderr = _coerce_text(result.get("stderr"))
    evidence = {"stdout_tail": _tail(stdout), "stderr_tail": _tail(stderr)}
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
        return False, _reason("command_not_executed", cmd=cmd, hint="runner skipped execution"), info
    if timed_out:
        timeout_msg = _coerce_text(result.get("timeout_error")) or f"timeout after {timeout}s"
        timeout_path.write_text(timeout_msg, encoding="utf-8")
        info.update({"status": "timeout", "timeout": timeout, "timeout_log": timeout_rel})
        return False, _reason("command_timeout", cmd=cmd, expected=f"<= {timeout}s", actual=timeout_msg, hint=f"log: {timeout_rel}"), info

    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    returncode = result.get("returncode")
    if returncode != expect_exit_code:
        hint = f"log: {stdout_rel} / {stderr_rel}"
        info["status"] = "failed"
        return False, _reason("command_failed", cmd=cmd, expected=f"exit code {expect_exit_code}", actual=f"exit code {returncode}", hint=hint), info
    info["status"] = "ok"
    return True, None, info


# 检查文件exists，检查路径是否存在
def _check_file_exists(base: Path, path: str):
    target = (base / path).resolve()
    try:
        target.relative_to(base.resolve())
    except Exception:
        return False, _reason("invalid_path", file=path, hint="escape detected")
    if not target.exists():
        return False, _reason("missing_file", file=path)
    return True, None


# 检查文件contains，读取文件内容
def _check_file_contains(base: Path, path: str, needle: str):
    ok, reason = _check_file_exists(base, path)
    if not ok:
        return ok, reason
    target = (base / path).resolve()
    text = target.read_text(encoding="utf-8", errors="replace")
    if needle not in text:
        return False, _reason("content_mismatch", file=path, expected=f"contains {needle!r}", actual=text[:200])
    return True, None


# selectbase路径
def _select_base_path(run_dir: Path, workspace: Path | None, path: str) -> Path | None:
    norm = path.replace("\\", "/")
    if norm == "outputs" or norm.startswith("outputs/"):
        return run_dir
    return workspace


# 解析cwd
def _resolve_cwd(base: Path, cwd: str | None):
    if not cwd:
        return base
    target = (base / cwd).resolve()
    try:
        target.relative_to(base.resolve())
    except Exception:
        return None
    return target


# 规范化prefixes
def _normalize_prefixes(prefixes) -> tuple[str, ...]:
    if isinstance(prefixes, str):
        return (prefixes,)
    if isinstance(prefixes, (list, tuple)):
        return tuple(p for p in prefixes if isinstance(p, str) and p)
    return ()


# 判断是否命令allowed
def _is_command_allowed(cmd: str, allow_prefixes: tuple[str, ...]):
    cmd = cmd.strip()
    if not cmd:
        return False
    if any(token in cmd for token in (";", "&&", "||", "|", "`", "$(", "\n", "\r")):
        return False
    return cmd.startswith(allow_prefixes)


# 判断是否包含execution检查
def _has_execution_check(checks: list[dict]) -> bool:
    for check in checks or []:
        if check.get("type") in {"command", "command_contains", "http_check"}:
            return True
    return False


# 合并检查项
def _merge_checks(task_checks: list[dict], policy_checks: list[dict], high_risk: bool = False) -> list[dict]:
    if _has_execution_check(task_checks) and not high_risk:
        return list(task_checks or [])
    merged = list(task_checks or [])
    merged.extend(policy_checks or [])
    return merged


# 判断是否高风险
def _is_high_risk(value) -> bool:
    if value is True:
        return True
    if isinstance(value, (int, float)) and value >= 7:
        return True
    if isinstance(value, str) and value.strip().lower() in {"high", "critical"}:
        return True
    return False


# JSONcontainsdict
def _json_contains_dict(actual, expected: dict) -> bool:
    if not isinstance(actual, dict):
        return False
    for k, v in expected.items():
        if k not in actual or not _json_contains(actual[k], v):
            return False
    return True


# JSONcontains列出
def _json_contains_list(actual, expected: list) -> bool:
    if not isinstance(actual, list):
        return False
    if len(expected) > len(actual):
        return False
    for i, v in enumerate(expected):
        if not _json_contains(actual[i], v):
            return False
    return True


_JSON_CONTAINS_HANDLERS = {
    dict: _json_contains_dict,
    list: _json_contains_list,
}


# JSONcontains
def _json_contains(actual, expected) -> bool:
    handler = _JSON_CONTAINS_HANDLERS.get(type(expected))
    if handler:
        return handler(actual, expected)
    return actual == expected


# Schemadepth
def _schema_depth(schema, depth=0) -> int:
    if depth > MAX_SCHEMA_DEPTH:
        return depth
    if isinstance(schema, dict):
        return max([depth] + [_schema_depth(v, depth + 1) for v in schema.values()])
    if isinstance(schema, list):
        return max([depth] + [_schema_depth(v, depth + 1) for v in schema])
    return depth


# 校验objectSchema
def _validate_object_schema(data, schema) -> tuple[bool, str | None]:
    if not isinstance(data, dict):
        return False, "expected object"
    required = schema.get("required", [])
    for key in required:
        if key not in data:
            return False, f"missing required key: {key}"
    props = schema.get("properties", {})
    for key, subschema in props.items():
        if key in data and isinstance(subschema, dict):
            ok, err = _validate_schema(data[key], subschema)
            if not ok:
                return False, f"key {key}: {err}"
    return True, None


# 校验arraySchema
def _validate_array_schema(data, schema) -> tuple[bool, str | None]:
    if not isinstance(data, list):
        return False, "expected array"
    items = schema.get("items")
    if isinstance(items, dict):
        for idx, item in enumerate(data[:MAX_SCHEMA_ITEMS]):
            ok, err = _validate_schema(item, items)
            if not ok:
                return False, f"item {idx}: {err}"
    return True, None


# 校验stringSchema
def _validate_string_schema(data, schema) -> tuple[bool, str | None]:
    return (True, None) if isinstance(data, str) else (False, "expected string")


# 校验integerSchema
def _validate_integer_schema(data, schema) -> tuple[bool, str | None]:
    return (True, None) if (isinstance(data, int) and not isinstance(data, bool)) else (False, "expected integer")


# 校验numberSchema
def _validate_number_schema(data, schema) -> tuple[bool, str | None]:
    return (True, None) if (isinstance(data, (int, float)) and not isinstance(data, bool)) else (False, "expected number")


# 校验booleanSchema
def _validate_boolean_schema(data, schema) -> tuple[bool, str | None]:
    return (True, None) if isinstance(data, bool) else (False, "expected boolean")


# 校验nullSchema
def _validate_null_schema(data, schema) -> tuple[bool, str | None]:
    return (True, None) if data is None else (False, "expected null")


_SCHEMA_VALIDATORS = {
    "object": _validate_object_schema,
    "array": _validate_array_schema,
    "string": _validate_string_schema,
    "integer": _validate_integer_schema,
    "number": _validate_number_schema,
    "boolean": _validate_boolean_schema,
    "null": _validate_null_schema,
}


# 校验Schema
def _validate_schema(data, schema) -> tuple[bool, str | None]:
    stype = schema.get("type")
    validator = _SCHEMA_VALIDATORS.get(stype)
    if validator:
        return validator(data, schema)
    enum = schema.get("enum")
    if enum is not None:
        return (True, None) if data in enum else (False, "expected enum value")
    return True, None


# 确保工作区
def _ensure_workspace(check_type: str, workspace: Path | None):
    if workspace:
        return True, None
    return False, _reason("workspace_required", check_type=check_type, hint="workspace path is required for this check")


# handle文件exists
@register_check("file_exists")
def _handle_file_exists(check: dict, run_dir: Path, workspace: Path | None, log_dir: Path, idx: int):
    path = check.get("path", "")
    base = _select_base_path(run_dir, workspace, path)
    if not base:
        return False, _reason("workspace_required", check_type="file_exists", hint="workspace path is required for this check"), None
    ok, reason = _check_file_exists(base, path)
    info = {"path": path}
    return ok, reason, info


# handle文件contains
@register_check("file_contains")
def _handle_file_contains(check: dict, run_dir: Path, workspace: Path | None, log_dir: Path, idx: int):
    path = check.get("path", "")
    base = _select_base_path(run_dir, workspace, path)
    if not base:
        return False, _reason("workspace_required", check_type="file_contains", hint="workspace path is required for this check"), None
    ok, reason = _check_file_contains(base, path, check.get("needle", ""))
    info = {"path": path, "needle": check.get("needle", "")}
    return ok, reason, info


# handle命令
@register_check("command")
def _handle_command(check: dict, run_dir: Path, workspace: Path | None, log_dir: Path, idx: int):
    ok, r = _ensure_workspace("command", workspace)
    if not ok:
        return ok, r, None
    cmd = check.get("cmd", "")
    allow_prefixes = _normalize_prefixes(check.get("allow_prefixes")) or ALLOWED_COMMAND_PREFIXES
    if not _is_command_allowed(cmd, allow_prefixes):
        info = {"cmd": cmd, "status": "skipped", "executed": False, "timed_out": False, "exit_code": None, "evidence": {"stdout_tail": "", "stderr_tail": ""}}
        return False, _reason("command_not_allowed", cmd=cmd, expected=f"prefix in {allow_prefixes}"), info
    timeout = int(check.get("timeout", 300))
    expect_exit_code = int(check.get("expect_exit_code", 0))
    cwd = _resolve_cwd(workspace, check.get("cwd"))
    if not cwd:
        info = {"cmd": cmd, "status": "invalid_cwd", "executed": False, "timed_out": False, "exit_code": None, "evidence": {"stdout_tail": "", "stderr_tail": ""}}
        return False, _reason("invalid_cwd", cwd=check.get("cwd")), info
    ok, r, info = _run_command(cmd, cwd, timeout, log_dir, idx, expect_exit_code)
    return ok, r, info


# handle命令contains，读取文件内容，检查路径是否存在
@register_check("command_contains")
def _handle_command_contains(check: dict, run_dir: Path, workspace: Path | None, log_dir: Path, idx: int):
    ok, r = _ensure_workspace("command_contains", workspace)
    if not ok:
        return ok, r, None
    cmd = check.get("cmd", "")
    needle = check.get("needle", "")
    allow_prefixes = _normalize_prefixes(check.get("allow_prefixes")) or ALLOWED_COMMAND_PREFIXES
    if not _is_command_allowed(cmd, allow_prefixes):
        info = {"cmd": cmd, "status": "skipped", "executed": False, "timed_out": False, "exit_code": None, "evidence": {"stdout_tail": "", "stderr_tail": ""}}
        return False, _reason("command_not_allowed", cmd=cmd, expected=f"prefix in {allow_prefixes}"), info
    timeout = int(check.get("timeout", 300))
    expect_exit_code = int(check.get("expect_exit_code", 0))
    cwd = _resolve_cwd(workspace, check.get("cwd"))
    if not cwd:
        info = {"cmd": cmd, "status": "invalid_cwd", "executed": False, "timed_out": False, "exit_code": None, "evidence": {"stdout_tail": "", "stderr_tail": ""}}
        return False, _reason("invalid_cwd", cwd=check.get("cwd")), info
    ok, r, info = _run_command(cmd, cwd, timeout, log_dir, idx, expect_exit_code)
    if not ok:
        return ok, r, info
    stdout_path = log_dir / f"cmd-{idx}.stdout.txt"
    stderr_path = log_dir / f"cmd-{idx}.stderr.txt"
    stdout = stdout_path.read_text(encoding="utf-8", errors="replace") if stdout_path.exists() else ""
    stderr = stderr_path.read_text(encoding="utf-8", errors="replace") if stderr_path.exists() else ""
    hay = (stdout or "") + "\n" + (stderr or "")
    if needle not in hay:
        if isinstance(info, dict):
            info["status"] = "output_missing"
        return False, _reason("command_output_missing", cmd=cmd, expected=f"contains {needle!r}", actual=hay[:200]), info
    return True, None, info


# 加载Schema，解析JSON，检查路径是否存在
def _load_schema(base: Path, schema, schema_path: str | None):
    if schema is not None:
        return schema, None
    if not schema_path:
        return None, _reason("missing_schema", hint="provide schema or schema_path")
    schema_target = (base / schema_path).resolve()
    try:
        schema_target.relative_to(base.resolve())
    except Exception:
        return None, _reason("missing_schema", hint="provide schema or schema_path")
    if not schema_target.exists():
        return None, _reason("missing_schema", hint="provide schema or schema_path")
    return json.loads(schema_target.read_text(encoding="utf-8", errors="replace")), None


# handleJSONSchema，解析JSON，读取文件内容
@register_check("json_schema")
def _handle_json_schema(check: dict, run_dir: Path, workspace: Path | None, log_dir: Path, idx: int):
    path = check.get("path", "")
    base = _select_base_path(run_dir, workspace, path)
    if not base:
        return False, _reason("workspace_required", check_type="json_schema", hint="workspace path is required for this check"), None
    target = (base / path).resolve()
    try:
        target.relative_to(base.resolve())
    except Exception:
        return False, _reason("invalid_path", file=path, hint="escape detected"), None
    if not target.exists():
        return False, _reason("missing_file", file=path), None
    if target.stat().st_size > MAX_JSON_BYTES:
        return False, _reason("file_too_large", file=path, expected=f"<= {MAX_JSON_BYTES} bytes"), None
    schema, err = _load_schema(base, check.get("schema"), check.get("schema_path"))
    if err:
        return False, err, None
    if _schema_depth(schema) > MAX_SCHEMA_DEPTH:
        return False, _reason("schema_too_deep", expected=f"<= {MAX_SCHEMA_DEPTH}"), None
    data = json.loads(target.read_text(encoding="utf-8", errors="replace"))
    ok, err = _validate_schema(data, schema)
    reason = None if ok else _reason("schema_mismatch", file=path, expected=str(schema), actual=err)
    info = {"path": path, "schema": schema}
    return ok, reason, info


# handleHTTP检查，解析JSON
@register_check("http_check")
def _handle_http_check(check: dict, run_dir: Path, workspace: Path | None, log_dir: Path, idx: int):
    url = check.get("url", "")
    parsed = urlparse(url)
    allow_hosts = set(check.get("allow_hosts", []) or [])
    allow_hosts.update({"127.0.0.1", "localhost"})
    if parsed.scheme not in ("http", "https") or parsed.hostname not in allow_hosts:
        return False, _reason("http_not_allowed", url=url, expected=f"host in {sorted(allow_hosts)}"), {"url": url, "executed": False}
    expected_status = int(check.get("expected_status", 200))
    timeout = int(check.get("timeout", 10))
    req = Request(url, method=check.get("method", "GET"))
    try:
        with urlopen(req, timeout=timeout) as resp:
            status = resp.getcode()
            body = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return False, _reason("http_error", url=url, actual=str(e)), {"url": url, "status": "error", "executed": True}
    if status != expected_status:
        return False, _reason("http_status_mismatch", url=url, expected=expected_status, actual=status), {"url": url, "status": status, "executed": True}
    contains = check.get("contains")
    if contains and contains not in body:
        return False, _reason("http_body_missing", url=url, expected=f"contains {contains!r}", actual=body[:200]), {"url": url, "status": status, "executed": True}
    json_contains = check.get("json_contains")
    if json_contains is None:
        return True, None, {"url": url, "status": status, "executed": True}
    try:
        data = json.loads(body)
    except Exception as e:
        return False, _reason("http_json_invalid", url=url, actual=str(e)), {"url": url, "status": status, "executed": True}
    ok = _json_contains(data, json_contains)
    reason = None if ok else _reason("http_json_mismatch", url=url, expected=json_contains, actual=data)
    info = {"url": url, "status": status, "executed": True}
    return ok, reason, info


# 列出待办files，检查路径是否存在
def _list_backlog_files(root: Path) -> list[Path]:
    backlog_dir = root / "backlog"
    if not backlog_dir.exists():
        return []
    return sorted(backlog_dir.glob("*.json"))


# 查找任务in待办，解析JSON，检查路径是否存在
def _find_task_in_backlog(root: Path, task_id: str) -> dict | None:
    for path in _list_backlog_files(root):
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for t in data.get("tasks", []):
            if t.get("status") not in ACTIVE_STATUSES:
                continue
            if t.get("id") == task_id:
                return t
    return None


# infer计划ID
def _infer_plan_id(root: Path, run_dir: Path) -> str | None:
    exec_root = root / "artifacts" / "executions"
    try:
        rel = run_dir.resolve().relative_to(exec_root.resolve())
    except Exception:
        return None
    parts = rel.parts
    if not parts:
        return None
    return parts[0]


# 查找任务inhistory，检查路径是否存在，读取文件
def _find_task_in_history(root: Path, plan_id: str, task_id: str) -> dict | None:
    history_path = root / "artifacts" / "executions" / plan_id / "history.jsonl"
    if not history_path.exists():
        return None
    found = None
    try:
        with history_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if rec.get("id") == task_id:
                    found = rec
    except Exception:
        return None
    return found


# 加载任务context
def _load_task_context(root: Path, run_dir: Path, task_id: str):
    task = _find_task_in_backlog(root, task_id)
    if not task:
        plan_id = _infer_plan_id(root, run_dir)
        if plan_id:
            task = _find_task_in_history(root, plan_id, task_id)
    if not task:
        return [], None, None, None
    checks = task.get("checks", [])
    task_workspace = None
    if isinstance(task.get("workspace"), dict):
        task_workspace = task["workspace"].get("path")
    task_risk = task.get("risk_level", task.get("risk", task.get("high_risk")))
    retry_context = None
    if task.get("last_run") or task.get("last_reasons"):
        retry_context = _reason(
            "retry_context",
            last_run=task.get("last_run"),
            last_reasons=task.get("last_reasons"),
        )
    return checks, task_workspace, retry_context, task_risk


# 加载策略检查项，解析JSON，检查路径是否存在
def _load_policy_checks(run_dir: Path) -> list[dict]:
    policy_path = run_dir / "policy.json"
    if not policy_path.exists():
        return []
    try:
        policy_data = json.loads(policy_path.read_text(encoding="utf-8"))
        return policy_data.get("checks", []) or []
    except Exception:
        return []


# 解析工作区
def _resolve_workspace(workspace_path: Path | None, task_workspace: str | None) -> Path | None:
    workspace = workspace_path or (Path(task_workspace) if task_workspace else None)
    return workspace.resolve() if workspace else None


# fallback验证
def _fallback_verify(run_dir: Path, retry_context: dict | None):
    reasons = [{"type": "no_checks", "hint": "no verification checks available"}]
    if retry_context:
        reasons.append(retry_context)
    return False, reasons


# 运行检查项，序列化JSON
def _run_checks(effective_checks: list[dict], run_dir: Path, workspace: Path | None, retry_context: dict | None):
    reasons = []
    passed = True
    log_dir = run_dir / "verification"
    check_results: list[dict] = []
    for idx, check in enumerate(effective_checks):
        ctype = check.get("type")
        handler = CHECK_REGISTRY.get(ctype)
        info = None
        if handler:
            outcome = handler(check, run_dir, workspace, log_dir, idx)
            if isinstance(outcome, tuple) and len(outcome) == 3:
                ok, r, info = outcome
            else:
                ok, r = outcome
        else:
            ok, r = False, _reason("unknown_check", hint=json.dumps(check, ensure_ascii=False))
        if not ok and r:
            reasons.append(r)
            passed = False
        record = {"index": idx, "type": ctype, "ok": ok}
        if isinstance(info, dict):
            record.update(info)
        if r:
            record["reason"] = r
        check_results.append(record)
    if not passed and retry_context:
        reasons.append(retry_context)
    return passed, reasons, check_results


# 用途: ä¼˜å…ˆæ‰§è¡Œ checksï¼ˆä»»åŠ¡å®šä¹?> policyï¼‰ã€‚
def verify_task(root: Path, run_dir: Path, task_id: str, workspace_path: Path | None = None):
    """
    ä¼˜å…ˆæ‰§è¡Œ checksï¼ˆä»»åŠ¡å®šä¹?> policyï¼‰ã€‚
    è¿”å›ž (passed, reasons[])
    """
    checks, task_workspace, retry_context, task_risk = _load_task_context(root, run_dir, task_id)
    policy_checks = _load_policy_checks(run_dir)
    workspace = _resolve_workspace(workspace_path, task_workspace)
    high_risk = _is_high_risk(task_risk)
    effective_checks = _merge_checks(checks, policy_checks, high_risk=high_risk)
    passed = False
    reasons: list[dict] = []
    check_results: list[dict] = []
    if not effective_checks:
        passed, reasons = _fallback_verify(run_dir, retry_context)
    elif not _has_execution_check(effective_checks):
        reasons = [{"type": "no_execution_checks", "hint": "no command/http checks available"}]
        if retry_context:
            reasons.append(retry_context)
    else:
        has_http_check = any(c.get("type") == "http_check" for c in effective_checks)
        if not (workspace or has_http_check):
            passed = False
            reasons = [{"type": "workspace_required", "hint": "workspace path is required for non-http checks"}]
            if retry_context:
                reasons.append(retry_context)
        else:
            passed, reasons, check_results = _run_checks(effective_checks, run_dir, workspace, retry_context)

    executed_any = any(c.get("executed") for c in check_results)
    if passed and not executed_any:
        passed = False
        reasons.append(_reason("no_commands_executed", hint="no executed checks available"))
    executed = [c for c in check_results if c.get("executed")]
    result = {
        "status": "success" if passed else "failed",
        "passed": passed,
        "task_id": task_id,
        "run_dir": str(run_dir),
        "checks": check_results,
        "executed_commands": executed,
        "reasons": reasons,
        "ts": time.time(),
    }
    try:
        (run_dir / "verification_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return passed, reasons


class Verifier:
    # 初始化
    def __init__(self, root: Path) -> None:
        self._root = root

    # 验证任务
    def verify_task(self, run_dir: Path, task_id: str, workspace_path: Path | None = None):
        return verify_task(self._root, run_dir, task_id, workspace_path=workspace_path)


__all__ = ["verify_task", "Verifier", "CommandRunner", "set_command_runner"]
