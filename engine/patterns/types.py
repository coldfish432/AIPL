from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PackSource(Enum):
    BUILTIN = "builtin"
    USER = "user"
    LEARNED = "learned"


@dataclass
class CommandPattern:
    """Command -> failure pattern mapping."""

    id: str
    regex: str
    failure_pattern: str
    description: str = ""
    confidence: float = 1.0
    hit_count: int = 0
    last_hit: float = 0


@dataclass
class ErrorSignature:
    """Output -> error signature mapping."""

    id: str
    regex: str
    signature: str
    description: str = ""
    confidence: float = 1.0
    hit_count: int = 0
    last_hit: float = 0


@dataclass
class FixHint:
    """Failure/signature -> fix hints."""

    id: str
    trigger: str
    trigger_type: str
    hints: list[str]
    confidence: float = 1.0
    use_count: int = 0


@dataclass
class LanguagePack:
    """Language pack model."""

    id: str
    name: str
    version: str
    description: str
    source: PackSource
    author: str = ""
    tags: list[str] = field(default_factory=list)
    detect_patterns: list[str] = field(default_factory=list)
    project_types: list[str] = field(default_factory=list)
    command_patterns: list[CommandPattern] = field(default_factory=list)
    error_signatures: list[ErrorSignature] = field(default_factory=list)
    fix_hints: list[FixHint] = field(default_factory=list)
    enabled: bool = True
    priority: int = 0
    created_at: float = 0
    updated_at: float = 0
