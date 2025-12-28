from policy_validator import is_safe_relative_path, validate_checks, validate_writes


# testissaferelative路径
def test_is_safe_relative_path():
    assert is_safe_relative_path("src/app.py") is True
    assert is_safe_relative_path("outputs/summary.txt") is True
    assert is_safe_relative_path("../secrets.txt") is False
    assert is_safe_relative_path("C:\\windows\\system32") is False
    assert is_safe_relative_path("..\\evil") is False
    assert is_safe_relative_path("a:b") is False


# test校验检查项命令whitelistandcwd
def test_validate_checks_command_whitelist_and_cwd():
    allowed = ["python", "pytest"]
    checks = [{"type": "command", "cmd": "python -m pytest -q", "cwd": "../.."}]
    cleaned, reasons = validate_checks(checks, allowed, command_whitelist=["python -m pytest -q"])
    assert cleaned == []
    assert reasons[0]["type"] == "invalid_cwd"


# test校验检查项命令notinwhitelist
def test_validate_checks_command_not_in_whitelist():
    allowed = ["python"]
    checks = [{"type": "command", "cmd": "python -m pytest -q"}]
    cleaned, reasons = validate_checks(checks, allowed, command_whitelist=["python -m compileall ."])
    assert cleaned == []
    assert reasons[0]["type"] == "command_not_in_whitelist"


# test校验检查项invalid路径
def test_validate_checks_invalid_paths():
    allowed = ["python"]
    checks = [
        {"type": "file_exists", "path": "../secret.txt"},
        {"type": "file_contains", "path": "C:\\x\\y", "needle": "x"},
        {"type": "json_schema", "path": "bad:json"},
    ]
    cleaned, reasons = validate_checks(checks, allowed)
    assert cleaned == []
    assert {r["type"] for r in reasons} == {"invalid_check_path"}


# test校验writes路径rules
def test_validate_writes_path_rules():
    allow_write = ["src"]
    deny_write = ["secrets"]
    writes = [
        {"target": "workspace", "path": "src/app.py"},
        {"target": "workspace", "path": "secrets/keys.txt"},
        {"target": "run", "path": "outputs/report.txt"},
    ]
    cleaned, reasons = validate_writes(writes, allow_write, deny_write)
    assert len(cleaned) == 2
    assert any(r["type"] == "write_not_allowed" for r in reasons)
