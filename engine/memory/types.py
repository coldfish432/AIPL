from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Rule:
    id: str
    content: str
    scope: str | None = None
    category: str | None = None
    created_at: float = 0


@dataclass
class ExtraCheck:
    id: str
    check: dict
    scope: str | None = None
    created_at: float = 0


@dataclass
class Lesson:
    id: str
    lesson: str
    triggers: list[dict] = field(default_factory=list)
    suggested_check: dict | None = None
    confidence: float | None = None
    created_at: float = 0


@dataclass
class ExperiencePack:
    id: str
    name: str
    version: str
    description: str
    author: str = ""
    tags: list[str] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)
    extra_checks: list[ExtraCheck] = field(default_factory=list)
    lessons: list[Lesson] = field(default_factory=list)
    created_at: float = 0
    updated_at: float = 0


@dataclass
class ImportedPack(ExperiencePack):
    source: str = "file"
    imported_at: float = 0
    enabled: bool = True
