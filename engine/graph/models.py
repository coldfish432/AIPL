from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional


class EdgeType(Enum):
    IMPORTS = "imports"
    CO_CHANGE = "co_change"
    SEMANTIC = "semantic"
    TEST_FOR = "test_for"


@dataclass
class Edge:
    source: str
    target: str
    edge_type: EdgeType
    weight: float = 1.0
    confidence: float = 1.0
    co_occurrence: int = 0
    last_seen: float = 0.0


@dataclass
class CoChangePattern:
    files: List[str]
    occurrence_count: int
    confidence: float
    avg_change_size: float
    source_runs: List[str] = field(default_factory=list)
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    pattern_type: str = "exact"
    tags: List[str] = field(default_factory=list)


@dataclass
class ChangeSet:
    run_id: str
    task_id: str
    files: List[str]
    timestamp: float
    success: bool
    task_type: str = ""
    change_summary: str = ""
