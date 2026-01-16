from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class FailureCategory(Enum):
    SYNTAX_ERROR = "syntax_error"
    RUNTIME_ERROR = "runtime_error"
    DEPENDENCY_ERROR = "dependency_error"
    LOGIC_ERROR = "logic_error"
    ENVIRONMENT_ERROR = "environment_error"
    TIMEOUT_ERROR = "timeout_error"
    PERMISSION_ERROR = "permission_error"
    UNKNOWN = "unknown"


@dataclass
class ErrorSignature:
    category: FailureCategory
    error_type: str
    error_message: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    stack_trace_summary: str = ""


@dataclass
class FixAttempt:
    round_id: int
    action_type: str
    action_detail: str
    success: bool
    side_effects: List[str] = field(default_factory=list)


@dataclass
class DiagnosisReport:
    task_id: str
    run_id: str
    round_id: int
    timestamp: float
    error_signature: ErrorSignature
    root_cause_analysis: str
    contributing_factors: List[str]
    fix_attempts: List[FixAttempt]
    successful_fix: Optional[str] = None
    suggested_prevention: str = ""
    learnable: bool = True
    confidence: float = 0.5
    generalizability: str = "low"
    affected_files: List[str] = field(default_factory=list)
    related_commands: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
