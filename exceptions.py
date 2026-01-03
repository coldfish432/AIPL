from __future__ import annotations

from typing import Optional


class AIPLError(Exception):
    def __init__(self, message: str, code: str = "UNKNOWN_ERROR", details: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}

    def to_dict(self) -> dict:
        return {"error": self.code, "message": self.message, "details": self.details}


class ConfigError(AIPLError):
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, "CONFIG_ERROR", details)


class WorkspaceError(AIPLError):
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, "WORKSPACE_ERROR", details)


class PolicyError(AIPLError):
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, "POLICY_ERROR", details)


class VerificationError(AIPLError):
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, "VERIFICATION_ERROR", details)


class CommandError(AIPLError):
    def __init__(
        self,
        message: str,
        command: str,
        exit_code: Optional[int] = None,
        stdout: str = "",
        stderr: str = ""
    ):
        super().__init__(
            message,
            "COMMAND_ERROR",
            {"command": command, "exit_code": exit_code, "stdout": stdout, "stderr": stderr},
        )


class CodexError(AIPLError):
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, "CODEX_ERROR", details)


class StorageError(AIPLError):
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, "STORAGE_ERROR", details)
