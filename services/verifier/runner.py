from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import Any

from .config import ALLOW_SHELL_COMMANDS, MAX_OUTPUT_BYTES
from .utils import coerce_text


class CommandRunner:
    def run(self, cmd: str, cwd: Path, timeout: int) -> dict[str, Any]:
        raise NotImplementedError


class SubprocessRunner(CommandRunner):
    def __init__(self, allow_shell: bool | None = None) -> None:
        self.allow_shell = ALLOW_SHELL_COMMANDS if allow_shell is None else allow_shell

    def _truncate(self, text: str) -> str:
        if len(text) <= MAX_OUTPUT_BYTES:
            return text
        half = MAX_OUTPUT_BYTES // 2
        return text[:half] + "\n...[truncated]...\n" + text[-half:]

    def _build_timeout_response(self, exc: subprocess.TimeoutExpired) -> dict[str, Any]:
        return {
            "executed": True,
            "timed_out": True,
            "returncode": None,
            "stdout": coerce_text(getattr(exc, "stdout", "")),
            "stderr": coerce_text(getattr(exc, "stderr", "")),
            "timeout_error": coerce_text(exc),
        }

    def _execute_command(self, cmd: str, cwd: Path, timeout: int, shell: bool) -> dict[str, Any]:
        if shell:
            run_args = cmd
        else:
            try:
                run_args = shlex.split(cmd)
            except ValueError as exc:
                return {"executed": False, "stderr": f"Invalid command: {exc}"}
        try:
            result = subprocess.run(
                run_args,
                cwd=cwd,
                shell=shell,
                timeout=timeout,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.TimeoutExpired as exc:
            return self._build_timeout_response(exc)
        return {
            "executed": True,
            "timed_out": False,
            "returncode": result.returncode,
            "stdout": result.stdout or "",
            "stderr": result.stderr or "",
        }

    def run(self, cmd: str, cwd: Path, timeout: int) -> dict[str, Any]:
        result = self._execute_command(cmd, cwd, timeout, self.allow_shell)
        stdout = coerce_text(result.get("stdout"))
        stderr = coerce_text(result.get("stderr"))
        result["stdout"] = self._truncate(stdout)
        result["stderr"] = self._truncate(stderr)
        return result


_DEFAULT_COMMAND_RUNNER = SubprocessRunner()
_COMMAND_RUNNER: CommandRunner | None = None


def set_command_runner(runner: CommandRunner | None) -> None:
    global _COMMAND_RUNNER
    _COMMAND_RUNNER = runner


def get_command_runner() -> CommandRunner:
    return _COMMAND_RUNNER or _DEFAULT_COMMAND_RUNNER
