from __future__ import annotations

import json
import math
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional

from .models import ChangeSet, CoChangePattern, Edge, EdgeType


class CoChangeCollector:
    def __init__(self, workspace_id: str) -> None:
        self.workspace_id = workspace_id
        self._change_sets: list[ChangeSet] = []

    def collect_from_run(
        self,
        run_id: str,
        task_id: str,
        modified_files: list[str],
        success: bool,
        task_type: str = "",
    ) -> Optional[ChangeSet]:
        if not success or len(modified_files) < 2:
            return None

        normalized = [self._normalize_path(f) for f in modified_files]
        normalized = [f for f in normalized if f]
        if len(normalized) < 2:
            return None

        change_set = ChangeSet(
            run_id=run_id,
            task_id=task_id,
            files=sorted(normalized),
            timestamp=time.time(),
            success=success,
            task_type=task_type,
        )

        self._change_sets.append(change_set)
        return change_set

    def get_change_sets(self) -> list[ChangeSet]:
        return list(self._change_sets)

    def clear(self) -> None:
        self._change_sets = []

    def _normalize_path(self, path: str) -> Optional[str]:
        cleaned = path.replace("\\", "/").strip()
        if cleaned.startswith("./"):
            cleaned = cleaned[2:]
        if any(tok in cleaned for tok in ["__pycache__", ".pyc", ".git", "node_modules"]):
            return None
        return cleaned if cleaned else None


class CoChangeLearner:
    MIN_OCCURRENCE = 2
    MIN_CONFIDENCE = 0.3
    MAX_PATTERNS = 500
    DECAY_HALF_LIFE_DAYS = 30

    def __init__(self, storage_path: Path) -> None:
        self.storage_path = storage_path
        self._patterns: list[CoChangePattern] = []
        self._pair_counts: dict[tuple[str, str], int] = defaultdict(int)
        self._file_counts: dict[str, int] = defaultdict(int)

    def load(self) -> None:
        if not self.storage_path.exists():
            return
        try:
            data = json.loads(self.storage_path.read_text(encoding="utf-8"))
            self._patterns = [
                CoChangePattern(**p) for p in data.get("patterns", [])
            ]
            self._pair_counts = defaultdict(int, {
                tuple(k.split("|")): v
                for k, v in data.get("pair_counts", {}).items()
                if isinstance(k, str) and "|" in k
            })
            self._file_counts = defaultdict(int, data.get("file_counts", {}))
        except Exception:
            pass

    def save(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "patterns": [
                {
                    "files": p.files,
                    "occurrence_count": p.occurrence_count,
                    "confidence": p.confidence,
                    "avg_change_size": p.avg_change_size,
                    "source_runs": p.source_runs[-10:],
                    "first_seen": p.first_seen,
                    "last_seen": p.last_seen,
                    "pattern_type": p.pattern_type,
                    "tags": p.tags,
                }
                for p in self._patterns
            ],
            "pair_counts": {
                f"{k[0]}|{k[1]}": v for k, v in self._pair_counts.items()
            },
            "file_counts": dict(self._file_counts),
            "updated_at": time.time(),
        }
        self.storage_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def learn_from_change_sets(self, change_sets: list[ChangeSet]) -> list[CoChangePattern]:
        new_patterns: list[CoChangePattern] = []
        for cs in change_sets:
            if not cs.success or len(cs.files) < 2:
                continue
            for f in cs.files:
                self._file_counts[f] += 1
            for i, f1 in enumerate(cs.files):
                for f2 in cs.files[i + 1:]:
                    pair = tuple(sorted([f1, f2]))
                    self._pair_counts[pair] += 1

        for pair, count in self._pair_counts.items():
            if count < self.MIN_OCCURRENCE:
                continue
            f1, f2 = pair
            max_single = max(self._file_counts.get(f1, 0), self._file_counts.get(f2, 0))
            confidence = count / max_single if max_single > 0 else 0
            if confidence < self.MIN_CONFIDENCE:
                continue
            existing = self._find_pattern([f1, f2])
            if existing:
                existing.occurrence_count = count
                existing.confidence = confidence
                existing.last_seen = time.time()
                if self._pair_counts[pair]:
                    existing.source_runs = list(
                        dict.fromkeys(existing.source_runs + [f"{pair}"])
                    )
            else:
                pattern = CoChangePattern(
                    files=[f1, f2],
                    occurrence_count=count,
                    confidence=confidence,
                    avg_change_size=2,
                    first_seen=time.time(),
                    last_seen=time.time(),
                    pattern_type=self._detect_pattern_type(f1, f2),
                    tags=self._extract_tags(f1, f2),
                )
                self._patterns.append(pattern)
                new_patterns.append(pattern)

        self._gc()
        return new_patterns

    def query_co_changes(self, file_path: str, min_confidence: float = 0.5) -> list[tuple[str, float]]:
        results: list[tuple[str, float]] = []
        normalized = file_path.replace("\\", "/").strip()
        for pattern in self._patterns:
            if normalized not in pattern.files:
                continue
            if pattern.confidence < min_confidence:
                continue
            age_days = (time.time() - pattern.last_seen) / 86400
            decayed_conf = pattern.confidence * math.pow(
                0.5, age_days / self.DECAY_HALF_LIFE_DAYS
            )
            if decayed_conf < min_confidence:
                continue
            for f in pattern.files:
                if f != normalized:
                    results.append((f, decayed_conf))

        seen: dict[str, float] = {}
        for f, conf in results:
            if f not in seen or seen[f] < conf:
                seen[f] = conf
        return sorted(seen.items(), key=lambda x: x[1], reverse=True)

    def get_co_change_edges(self, min_confidence: float = 0.3) -> list[Edge]:
        edges: list[Edge] = []
        for pattern in self._patterns:
            if pattern.confidence < min_confidence or len(pattern.files) != 2:
                continue
            edges.append(Edge(
                source=pattern.files[0],
                target=pattern.files[1],
                edge_type=EdgeType.CO_CHANGE,
                weight=pattern.confidence,
                confidence=pattern.confidence,
                co_occurrence=pattern.occurrence_count,
                last_seen=pattern.last_seen,
            ))
        return edges

    def _find_pattern(self, files: list[str]) -> Optional[CoChangePattern]:
        target = set(files)
        for p in self._patterns:
            if set(p.files) == target:
                return p
        return None

    def _detect_pattern_type(self, f1: str, f2: str) -> str:
        p1, p2 = Path(f1), Path(f2)
        if p1.parent == p2.parent:
            return "same_directory"
        if p1.stem == p2.stem:
            return "same_name"
        combined = f"{f1} {f2}".lower()
        if "test" in combined:
            return "test_related"
        return "exact"

    def _extract_tags(self, f1: str, f2: str) -> list[str]:
        tags: list[str] = []
        for f in [f1, f2]:
            if f.endswith(".py"):
                tags.append("python")
            elif f.endswith(".java"):
                tags.append("java")
            elif f.endswith(".ts") or f.endswith(".tsx"):
                tags.append("typescript")
        for f in [f1, f2]:
            parts = f.split("/")
            if "api" in parts:
                tags.append("api")
            if "models" in parts:
                tags.append("model")
            if "tests" in parts or "test" in parts:
                tags.append("test")
        return list(dict.fromkeys(tags))

    def _gc(self) -> None:
        if len(self._patterns) <= self.MAX_PATTERNS:
            return
        self._patterns.sort(key=lambda p: p.confidence, reverse=True)
        self._patterns = self._patterns[: self.MAX_PATTERNS]
