from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


JsonDict = dict[str, Any]


@dataclass
class ExecutionError:
    cmd: str | None = None
    exit_code: int | None = None
    status: str | None = None
    stdout: str | None = None
    stderr: str | None = None
    key_errors: str | None = None


@dataclass
class ExecutionErrors:
    has_errors: bool = False
    failed_commands: list[ExecutionError] = field(default_factory=list)
    error_summary: str = ""


@dataclass
class CheckResult:
    index: int
    type: str
    ok: bool
    info: JsonDict = field(default_factory=dict)


@dataclass
class VerifyResult:
    passed: bool
    reasons: list[JsonDict]
    check_results: list[JsonDict]
    total_duration_ms: int


@dataclass
class ReworkRequest:
    round: int
    remaining_attempts: int
    why_failed: list[JsonDict]
    execution_errors: ExecutionErrors
    error_summary: str
    fix_guidance: str
    prev_stdout: str
    code_modified: bool
    produced_files: list[str]
    workspace: str
    suspected_related_files: list[str]

    def to_dict(self) -> JsonDict:
        return {
            "round": self.round,
            "remaining_attempts": self.remaining_attempts,
            "why_failed": self.why_failed,
            "execution_errors": {
                "has_errors": self.execution_errors.has_errors,
                "failed_commands": [
                    {
                        "cmd": err.cmd,
                        "exit_code": err.exit_code,
                        "status": err.status,
                        "stdout": err.stdout,
                        "stderr": err.stderr,
                        "key_errors": err.key_errors,
                    }
                    for err in self.execution_errors.failed_commands
                ],
                "error_summary": self.execution_errors.error_summary,
            },
            "error_summary": self.error_summary,
            "fix_guidance": self.fix_guidance,
            "prev_stdout": self.prev_stdout,
            "code_modified": self.code_modified,
            "produced_files": self.produced_files,
            "workspace": self.workspace,
            "suspected_related_files": self.suspected_related_files,
            "next_round_should_do": "根据错误信息修复代码，确保能够正常运行。",
        }
