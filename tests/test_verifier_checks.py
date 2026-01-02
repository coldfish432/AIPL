import json
from pathlib import Path

from services.verifier import VerifierService
from services.verifier.checks import http as http_checks


REPO_ROOT = Path(__file__).resolve().parents[1]


class _FakeResponse:
    # 初始化
    def __init__(self, body: str, status: int = 200) -> None:
        self._body = body
        self._status = status

    # getcode
    def getcode(self):
        return self._status

    # 读取
    def read(self):
        return self._body.encode("utf-8")

    # 进入上下文
    def __enter__(self):
        return self

    # 退出上下文
    def __exit__(self, exc_type, exc, tb):
        return False


# testverifierhandles文件andJSON检查项，写入文件内容，解析JSON
def test_verifier_handles_file_and_json_checks(tmp_path, backlog_task, monkeypatch):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    data_path = workspace / "data.json"
    data_path.write_text(json.dumps({"ok": True}), encoding="utf-8")
    text_path = workspace / "note.txt"
    text_path.write_text("hello world\n", encoding="utf-8")

    # fakeurlopen
    def _fake_urlopen(req, timeout=10):
        return _FakeResponse('{"ok": true}', status=200)

    monkeypatch.setattr(http_checks, "urlopen", _fake_urlopen)

    checks = [
        {"type": "http_check", "url": "http://localhost/health", "expected_status": 200},
        {"type": "file_exists", "path": "note.txt"},
        {"type": "file_contains", "path": "note.txt", "needle": "hello"},
        {"type": "json_schema", "path": "data.json", "schema": {"type": "object", "required": ["ok"], "properties": {"ok": {"type": "boolean"}}}},
    ]
    task_id, _ = backlog_task(checks, workspace=workspace)

    passed, _ = VerifierService(REPO_ROOT).verify_task(run_dir, task_id, workspace_path=workspace)

    assert passed is True
    result = json.loads((run_dir / "verification_result.json").read_text(encoding="utf-8"))
    assert any(c.get("type") == "http_check" and c.get("executed") is True for c in result["checks"])
    assert all(c.get("ok") is True for c in result["checks"])


# test文件existsmissingandescape，解析JSON，创建目录
def test_file_exists_missing_and_escape(tmp_path, backlog_task, monkeypatch):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr(http_checks, "urlopen", lambda req, timeout=10: _FakeResponse("ok", status=200))
    checks = [
        {"type": "http_check", "url": "http://localhost/health", "expected_status": 200},
        {"type": "file_exists", "path": "missing.txt"},
        {"type": "file_exists", "path": "../escape.txt"},
    ]
    task_id, _ = backlog_task(checks, workspace=workspace)

    passed, _ = VerifierService(REPO_ROOT).verify_task(run_dir, task_id, workspace_path=workspace)

    assert passed is False
    result = json.loads((run_dir / "verification_result.json").read_text(encoding="utf-8"))
    reasons = [c.get("reason", {}).get("type") for c in result["checks"]]
    assert "missing_file" in reasons
    assert "invalid_path" in reasons


# test文件containsmismatch，写入文件内容，解析JSON
def test_file_contains_mismatch(tmp_path, backlog_task, monkeypatch):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "note.txt"
    target.write_text("hello\n", encoding="utf-8")
    monkeypatch.setattr(http_checks, "urlopen", lambda req, timeout=10: _FakeResponse("ok", status=200))
    checks = [
        {"type": "http_check", "url": "http://localhost/health", "expected_status": 200},
        {"type": "file_contains", "path": "note.txt", "needle": "world"},
    ]
    task_id, _ = backlog_task(checks, workspace=workspace)

    passed, _ = VerifierService(REPO_ROOT).verify_task(run_dir, task_id, workspace_path=workspace)

    assert passed is False
    result = json.loads((run_dir / "verification_result.json").read_text(encoding="utf-8"))
    reasons = {c.get("type"): c.get("reason", {}).get("type") for c in result["checks"]}
    assert reasons.get("file_contains") == "content_mismatch"


# deepSchema
def _deep_schema(depth: int) -> dict:
    schema = {"type": "object", "properties": {}}
    current = schema
    for idx in range(depth):
        nested = {"type": "object", "properties": {}}
        current["properties"][f"k{idx}"] = nested
        current = nested
    return schema


# testJSONSchemamismatchanddepthlimit，写入文件内容，解析JSON
def test_json_schema_mismatch_and_depth_limit(tmp_path, backlog_task, monkeypatch):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    data_path = workspace / "data.json"
    data_path.write_text(json.dumps({"ok": "no"}), encoding="utf-8")
    monkeypatch.setattr(http_checks, "urlopen", lambda req, timeout=10: _FakeResponse("ok", status=200))
    checks = [
        {"type": "http_check", "url": "http://localhost/health", "expected_status": 200},
        {"type": "json_schema", "path": "data.json", "schema": {"type": "object", "required": ["ok"], "properties": {"ok": {"type": "boolean"}}}},
        {"type": "json_schema", "path": "data.json", "schema": _deep_schema(25)},
    ]
    task_id, _ = backlog_task(checks, workspace=workspace)

    passed, _ = VerifierService(REPO_ROOT).verify_task(run_dir, task_id, workspace_path=workspace)

    assert passed is False
    result = json.loads((run_dir / "verification_result.json").read_text(encoding="utf-8"))
    reasons = [c.get("reason", {}).get("type") for c in result["checks"]]
    assert "schema_mismatch" in reasons
    assert "schema_too_deep" in reasons


# testJSONSchema文件toolarge，解析JSON，创建目录
def test_json_schema_file_too_large(tmp_path, backlog_task, monkeypatch):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    data_path = workspace / "big.json"
    data_path.write_bytes(b"a" * (1024 * 1024 + 5))
    monkeypatch.setattr(http_checks, "urlopen", lambda req, timeout=10: _FakeResponse("ok", status=200))
    checks = [
        {"type": "http_check", "url": "http://localhost/health", "expected_status": 200},
        {"type": "json_schema", "path": "big.json", "schema": {"type": "string"}},
    ]
    task_id, _ = backlog_task(checks, workspace=workspace)

    passed, _ = VerifierService(REPO_ROOT).verify_task(run_dir, task_id, workspace_path=workspace)

    assert passed is False
    result = json.loads((run_dir / "verification_result.json").read_text(encoding="utf-8"))
    reasons = {c.get("type"): c.get("reason", {}).get("type") for c in result["checks"]}
    assert reasons.get("json_schema") == "file_too_large"


# testHTTP检查notallowedhost，解析JSON，创建目录
def test_http_check_not_allowed_host(tmp_path, backlog_task):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    checks = [{"type": "http_check", "url": "http://example.com/health", "expected_status": 200}]
    task_id, _ = backlog_task(checks)

    passed, _ = VerifierService(REPO_ROOT).verify_task(run_dir, task_id, workspace_path=None)

    assert passed is False
    result = json.loads((run_dir / "verification_result.json").read_text(encoding="utf-8"))
    assert result["checks"][0]["reason"]["type"] == "http_not_allowed"


# testHTTP检查error，解析JSON，创建目录
def test_http_check_error(tmp_path, backlog_task, monkeypatch):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    checks = [{"type": "http_check", "url": "http://localhost/health", "expected_status": 200}]
    task_id, _ = backlog_task(checks)

    # boom
    def _boom(req, timeout=10):
        raise TimeoutError("timeout")

    monkeypatch.setattr(http_checks, "urlopen", _boom)
    passed, _ = VerifierService(REPO_ROOT).verify_task(run_dir, task_id, workspace_path=None)

    assert passed is False
    result = json.loads((run_dir / "verification_result.json").read_text(encoding="utf-8"))
    assert result["checks"][0]["reason"]["type"] == "http_error"


# test命令containsmatchandmismatch，解析JSON，创建目录
def test_command_contains_match_and_mismatch(tmp_path, backlog_task, fake_runner):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    checks = [{"type": "command_contains", "cmd": "python -m pytest -q", "needle": "OK", "timeout": 1}]
    task_id, _ = backlog_task(checks, workspace=workspace)

    fake_runner.queue_result({"executed": True, "timed_out": False, "returncode": 0, "stdout": "OK\n", "stderr": ""})
    passed, _ = VerifierService(REPO_ROOT).verify_task(run_dir, task_id, workspace_path=workspace)
    assert passed is True

    fake_runner.queue_result({"executed": True, "timed_out": False, "returncode": 0, "stdout": "nope\n", "stderr": ""})
    passed, _ = VerifierService(REPO_ROOT).verify_task(run_dir, task_id, workspace_path=workspace)
    assert passed is False
    result = json.loads((run_dir / "verification_result.json").read_text(encoding="utf-8"))
    assert result["checks"][0]["reason"]["type"] == "command_output_missing"
