from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class RuleScope(Enum):
    PLAN = "plan"
    FIX = "fix"
    VERIFY = "verify"


class CheckType(Enum):
    COMMAND = "command"
    FILE = "file"
    HTTP = "http"
    SCHEMA = "schema"


@dataclass
class Rule:
    id: str
    content: str
    scope: RuleScope
    category: str = ""
    source: str = "user"
    created_at: float = 0.0


@dataclass
class Check:
    id: str
    type: CheckType
    config: dict
    scope: str = "verify"
    source: str = "user"


@dataclass
class Policy:
    allow: list[str] = field(default_factory=list)
    deny: list[str] = field(default_factory=list)
