from __future__ import annotations

import json
import subprocess
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from state import ACTIVE_STATUSES

ALLOWED_COMMAND_PREFIXES = ("python", "pytest", "mvn", "gradle", "npm", "node", "pnpm", "yarn")
MAX_JSON_BYTES = 1024 * 1024
MAX_SCHEMA_DEPTH = 20
MAX_SCHEMA_ITEMS = 100

CHECK_REGISTRY: dict[str, callable] = {}


def register_check(name: str):
    def decorator(fn):
        CHECK_REGISTRY[name] = fn
        return fn
    return decorator


def _reason(mtype: str, **kwargs):
    r = {"type": mtype}
    for k, v in kwargs.items():
        if v is not None:
            r[k] = v
    return r


def _run_command(cmd: str, cwd: Path, timeout: int, log_dir: Path, idx: int, expect_exit_code: int):
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
        return False, _reason("command_timeout", cmd=cmd, expected=f"<= {timeout}s", actual=str(e), hint=f"log: verification/cmd-{idx}.timeout.txt"), "", ""

    (log_dir / f"cmd-{idx}.stdout.txt").write_text(result.stdout or "", encoding="utf-8")
    (log_dir / f"cmd-{idx}.stderr.txt").write_text(result.stderr or "", encoding="utf-8")
    if result.returncode != expect_exit_code:
        hint = f"log: verification/cmd-{idx}.stdout.txt / cmd-{idx}.stderr.txt"
        return False, _reason("command_failed", cmd=cmd, expected=f"exit code {expect_exit_code}", actual=f"exit code {result.returncode}", hint=hint), result.stdout, result.stderr
    return True, None, result.stdout, result.stderr


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


def _select_base_path(run_dir: Path, workspace: Path | None, path: str) -> Path | None:
    norm = path.replace("\\", "/")
    if norm == "outputs" or norm.startswith("outputs/"):
        return run_dir
    return workspace


def _resolve_cwd(base: Path, cwd: str | None):
    if not cwd:
        return base
    target = (base / cwd).resolve()
    try:
        target.relative_to(base.resolve())
    except Exception:
        return None
    return target


def _normalize_prefixes(prefixes) -> tuple[str, ...]:
    if isinstance(prefixes, str):
        return (prefixes,)
    if isinstance(prefixes, (list, tuple)):
        return tuple(p for p in prefixes if isinstance(p, str) and p)
    return ()


def _is_command_allowed(cmd: str, allow_prefixes: tuple[str, ...]):
    cmd = cmd.strip()
    return cmd.startswith(allow_prefixes)


def _json_contains_dict(actual, expected: dict) -> bool:
    if not isinstance(actual, dict):
        return False
    for k, v in expected.items():
        if k not in actual or not _json_contains(actual[k], v):
            return False
    return True


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


def _json_contains(actual, expected) -> bool:
    handler = _JSON_CONTAINS_HANDLERS.get(type(expected))
    if handler:
        return handler(actual, expected)
    return actual == expected


def _schema_depth(schema, depth=0) -> int:
    if depth > MAX_SCHEMA_DEPTH:
        return depth
    if isinstance(schema, dict):
        return max([depth] + [_schema_depth(v, depth + 1) for v in schema.values()])
    if isinstance(schema, list):
        return max([depth] + [_schema_depth(v, depth + 1) for v in schema])
    return depth


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


def _validate_string_schema(data, schema) -> tuple[bool, str | None]:
    return (True, None) if isinstance(data, str) else (False, "expected string")


def _validate_integer_schema(data, schema) -> tuple[bool, str | None]:
    return (True, None) if (isinstance(data, int) and not isinstance(data, bool)) else (False, "expected integer")


def _validate_number_schema(data, schema) -> tuple[bool, str | None]:
    return (True, None) if (isinstance(data, (int, float)) and not isinstance(data, bool)) else (False, "expected number")


def _validate_boolean_schema(data, schema) -> tuple[bool, str | None]:
    return (True, None) if isinstance(data, bool) else (False, "expected boolean")


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


def _validate_schema(data, schema) -> tuple[bool, str | None]:
    stype = schema.get("type")
    validator = _SCHEMA_VALIDATORS.get(stype)
    if validator:
        return validator(data, schema)
    enum = schema.get("enum")
    if enum is not None:
        return (True, None) if data in enum else (False, "expected enum value")
    return True, None


def _ensure_workspace(check_type: str, workspace: Path | None):
    if workspace:
        return True, None
    return False, _reason("workspace_required", check_type=check_type, hint="workspace path is required for this check")


@register_check("file_exists")
def _handle_file_exists(check: dict, run_dir: Path, workspace: Path | None, log_dir: Path, idx: int):
    path = check.get("path", "")
    base = _select_base_path(run_dir, workspace, path)
    if not base:
        return False, _reason("workspace_required", check_type="file_exists", hint="workspace path is required for this check")
    return _check_file_exists(base, path)


@register_check("file_contains")
def _handle_file_contains(check: dict, run_dir: Path, workspace: Path | None, log_dir: Path, idx: int):
    path = check.get("path", "")
    base = _select_base_path(run_dir, workspace, path)
    if not base:
        return False, _reason("workspace_required", check_type="file_contains", hint="workspace path is required for this check")
    return _check_file_contains(base, path, check.get("needle", ""))


@register_check("command")
def _handle_command(check: dict, run_dir: Path, workspace: Path | None, log_dir: Path, idx: int):
    ok, r = _ensure_workspace("command", workspace)
    if not ok:
        return ok, r
    cmd = check.get("cmd", "")
    allow_prefixes = _normalize_prefixes(check.get("allow_prefixes")) or ALLOWED_COMMAND_PREFIXES
    if not _is_command_allowed(cmd, allow_prefixes):
        return False, _reason("command_not_allowed", cmd=cmd, expected=f"prefix in {allow_prefixes}")
    timeout = int(check.get("timeout", 300))
    expect_exit_code = int(check.get("expect_exit_code", 0))
    cwd = _resolve_cwd(workspace, check.get("cwd"))
    if not cwd:
        return False, _reason("invalid_cwd", cwd=check.get("cwd"))
    ok, r, _, _ = _run_command(cmd, cwd, timeout, log_dir, idx, expect_exit_code)
    return ok, r


@register_check("command_contains")
def _handle_command_contains(check: dict, run_dir: Path, workspace: Path | None, log_dir: Path, idx: int):
    ok, r = _ensure_workspace("command_contains", workspace)
    if not ok:
        return ok, r
    cmd = check.get("cmd", "")
    needle = check.get("needle", "")
    allow_prefixes = _normalize_prefixes(check.get("allow_prefixes")) or ALLOWED_COMMAND_PREFIXES
    if not _is_command_allowed(cmd, allow_prefixes):
        return False, _reason("command_not_allowed", cmd=cmd, expected=f"prefix in {allow_prefixes}")
    timeout = int(check.get("timeout", 300))
    expect_exit_code = int(check.get("expect_exit_code", 0))
    cwd = _resolve_cwd(workspace, check.get("cwd"))
    if not cwd:
        return False, _reason("invalid_cwd", cwd=check.get("cwd"))
    ok, r, stdout, stderr = _run_command(cmd, cwd, timeout, log_dir, idx, expect_exit_code)
    if not ok:
        return ok, r
    hay = (stdout or "") + "\n" + (stderr or "")
    if needle not in hay:
        return False, _reason("command_output_missing", cmd=cmd, expected=f"contains {needle!r}", actual=hay[:200])
    return True, None


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


@register_check("json_schema")
def _handle_json_schema(check: dict, run_dir: Path, workspace: Path | None, log_dir: Path, idx: int):
    path = check.get("path", "")
    base = _select_base_path(run_dir, workspace, path)
    if not base:
        return False, _reason("workspace_required", check_type="json_schema", hint="workspace path is required for this check")
    target = (base / path).resolve()
    try:
        target.relative_to(base.resolve())
    except Exception:
        return False, _reason("invalid_path", file=path, hint="escape detected")
    if not target.exists():
        return False, _reason("missing_file", file=path)
    if target.stat().st_size > MAX_JSON_BYTES:
        return False, _reason("file_too_large", file=path, expected=f"<= {MAX_JSON_BYTES} bytes")
    schema, err = _load_schema(base, check.get("schema"), check.get("schema_path"))
    if err:
        return False, err
    if _schema_depth(schema) > MAX_SCHEMA_DEPTH:
        return False, _reason("schema_too_deep", expected=f"<= {MAX_SCHEMA_DEPTH}")
    data = json.loads(target.read_text(encoding="utf-8", errors="replace"))
    ok, err = _validate_schema(data, schema)
    return ok, None if ok else _reason("schema_mismatch", file=path, expected=str(schema), actual=err)


@register_check("http_check")
def _handle_http_check(check: dict, run_dir: Path, workspace: Path | None, log_dir: Path, idx: int):
    url = check.get("url", "")
    parsed = urlparse(url)
    allow_hosts = set(check.get("allow_hosts", []) or [])
    allow_hosts.update({"127.0.0.1", "localhost"})
    if parsed.scheme not in ("http", "https") or parsed.hostname not in allow_hosts:
        return False, _reason("http_not_allowed", url=url, expected=f"host in {sorted(allow_hosts)}")
    expected_status = int(check.get("expected_status", 200))
    timeout = int(check.get("timeout", 10))
    req = Request(url, method=check.get("method", "GET"))
    try:
        with urlopen(req, timeout=timeout) as resp:
            status = resp.getcode()
            body = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return False, _reason("http_error", url=url, actual=str(e))
    if status != expected_status:
        return False, _reason("http_status_mismatch", url=url, expected=expected_status, actual=status)
    contains = check.get("contains")
    if contains and contains not in body:
        return False, _reason("http_body_missing", url=url, expected=f"contains {contains!r}", actual=body[:200])
    json_contains = check.get("json_contains")
    if json_contains is None:
        return True, None
    try:
        data = json.loads(body)
    except Exception as e:
        return False, _reason("http_json_invalid", url=url, actual=str(e))
    ok = _json_contains(data, json_contains)
    return ok, None if ok else _reason("http_json_mismatch", url=url, expected=json_contains, actual=data)


def _list_backlog_files(root: Path) -> list[Path]:
    backlog_dir = root / "backlog"
    if not backlog_dir.exists():
        return []
    return sorted(backlog_dir.glob("*.json"))


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


def _load_task_context(root: Path, run_dir: Path, task_id: str):
    task = _find_task_in_backlog(root, task_id)
    if not task:
        plan_id = _infer_plan_id(root, run_dir)
        if plan_id:
            task = _find_task_in_history(root, plan_id, task_id)
    if not task:
        return [], None, None
    checks = task.get("checks", [])
    task_workspace = None
    if isinstance(task.get("workspace"), dict):
        task_workspace = task["workspace"].get("path")
    retry_context = None
    if task.get("last_run") or task.get("last_reasons"):
        retry_context = _reason(
            "retry_context",
            last_run=task.get("last_run"),
            last_reasons=task.get("last_reasons"),
        )
    return checks, task_workspace, retry_context


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


def _fallback_verify(run_dir: Path, retry_context: dict | None):
    outputs_dir = run_dir / "outputs"
    if outputs_dir.exists():
        return True, []
    reasons = [{"type": "unknown", "hint": "no checks provided and no outputs found"}]
    if retry_context:
        reasons.append(retry_context)
    return False, reasons


def _run_checks(effective_checks: list[dict], run_dir: Path, workspace: Path | None, retry_context: dict | None):
    reasons = []
    passed = True
    log_dir = run_dir / "verification"
    for idx, check in enumerate(effective_checks):
        ctype = check.get("type")
        handler = CHECK_REGISTRY.get(ctype)
        if handler:
            ok, r = handler(check, run_dir, workspace, log_dir, idx)
        else:
            ok, r = False, _reason("unknown_check", hint=json.dumps(check, ensure_ascii=False))
        if not ok and r:
            reasons.append(r)
            passed = False
    if not passed and retry_context:
        reasons.append(retry_context)
    return passed, reasons


def verify_task(run_dir: Path, task_id: str, workspace_path: Path | None = None):
    """
    ä¼˜å…ˆæ‰§è¡Œ checksï¼ˆä»»åŠ¡å®šä¹?> policyï¼‰ã€‚
    è¿”å›ž (passed, reasons[])
    """
    root = Path(__file__).resolve().parent.parent
    checks, task_workspace, retry_context = _load_task_context(root, run_dir, task_id)
    policy_checks = [] if checks else _load_policy_checks(run_dir)
    workspace = _resolve_workspace(workspace_path, task_workspace)
    effective_checks = checks or policy_checks
    if not effective_checks:
        return _fallback_verify(run_dir, retry_context)
    has_http_check = any(c.get("type") == "http_check" for c in effective_checks)
    if not (workspace or has_http_check):
        return _fallback_verify(run_dir, retry_context)
    return _run_checks(effective_checks, run_dir, workspace, retry_context)


class Verifier:
    def verify_task(self, run_dir: Path, task_id: str, workspace_path: Path | None = None):
        return verify_task(run_dir, task_id, workspace_path=workspace_path)


__all__ = ["verify_task", "Verifier"]