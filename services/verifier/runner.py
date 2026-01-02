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

    def _run_safe(self, cmd: str, cwd: Path, timeout: int) -> dict[str, Any]:
        try:
            cmd_parts = shlex.split(cmd)
        except ValueError as exc:
            return {"executed": False, "stderr": f"Invalid command: {exc}"}
        try:
            result = subprocess.run(
                cmd_parts,
                cwd=cwd,
                shell=False,
                timeout=timeout,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.TimeoutExpired as exc:
            return {
                "executed": True,
                "timed_out": True,
                "returncode": None,
                "stdout": coerce_text(getattr(exc, "stdout", "")),
                "stderr": coerce_text(getattr(exc, "stderr", "")),
                "timeout_error": coerce_text(exc),
            }
        return {
            "executed": True,
            "timed_out": False,
            "returncode": result.returncode,
            "stdout": result.stdout or "",
            "stderr": result.stderr or "",
        }

    def _run_shell(self, cmd: str, cwd: Path, timeout: int) -> dict[str, Any]:
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
        except subprocess.TimeoutExpired as exc:
            return {
                "executed": True,
                "timed_out": True,
                "returncode": None,
                "stdout": coerce_text(getattr(exc, "stdout", "")),
                "stderr": coerce_text(getattr(exc, "stderr", "")),
                "timeout_error": coerce_text(exc),
            }
        return {
            "executed": True,
            "timed_out": False,
            "returncode": result.returncode,
            "stdout": result.stdout or "",
            "stderr": result.stderr or "",
        }

    def run(self, cmd: str, cwd: Path, timeout: int) -> dict[str, Any]:
        result = self._run_shell(cmd, cwd, timeout) if self.allow_shell else self._run_safe(cmd, cwd, timeout)
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
