from __future__ import annotations

import os

from config import DEFAULT_ALLOWED_COMMANDS


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


NO_CHECKS_BEHAVIOR = os.getenv("AIPL_NO_CHECKS_BEHAVIOR", "fail").lower()
REQUIRE_EXECUTION = _env_bool("AIPL_REQUIRE_EXECUTION", True)
ALLOW_SKIP_TESTS = _env_bool("AIPL_ALLOW_SKIP_TESTS", False)

ALLOW_SHELL_COMMANDS = _env_bool("AIPL_ALLOW_SHELL_COMMANDS", True)
MAX_OUTPUT_BYTES = _env_int("AIPL_MAX_OUTPUT_BYTES", 10 * 1024 * 1024)

COMMAND_TIMEOUT = _env_int("AIPL_COMMAND_TIMEOUT", 300)
BUILD_TIMEOUT = _env_int("AIPL_BUILD_TIMEOUT", 900)
TEST_TIMEOUT = _env_int("AIPL_TEST_TIMEOUT", 600)

HTTP_TIMEOUT = _env_int("AIPL_HTTP_TIMEOUT", 30)
HTTP_RETRIES = _env_int("AIPL_HTTP_RETRIES", 3)
HTTP_SOFT_FAIL = _env_bool("AIPL_HTTP_SOFT_FAIL", False)

ALLOWED_COMMAND_PREFIXES = tuple(DEFAULT_ALLOWED_COMMANDS)

EXECUTION_CHECK_TYPES = {"command", "command_contains", "http_check"}
