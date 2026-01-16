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
class LearnedHint:
    id: str
    trigger_signature: str
    hint: str
    scope: str = "fix"
    confidence: float = 0.5
    hit_count: int = 0
    use_count: int = 0
    source_run_id: str = ""
    last_used: float = 0
    created_at: float = 0.0

@dataclass
class LearnedLesson:
    id: str
    content: str
    context: str = ""
    tags: List[str] = field(default_factory=list)
    confidence: float = 0.5
    source_run_id: str = ""
    source_task_id: str = ""
    created_at: float = 0.0

@dataclass
class LearnedSignature:
    id: str
    category: FailureCategory
    error_type: str
    error_pattern: str
    file_pattern: Optional[str] = None
    confidence: float = 0.5
    hit_count: int = 0
    source_run_id: str = ""
    created_at: float = 0.0
