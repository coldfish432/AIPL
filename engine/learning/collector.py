from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from engine.diagnosis.models import DiagnosisReport


@dataclass
class LearnedItem:
    type: str
    content: dict
    source_run_id: str
    source_task_id: str
    timestamp: float
    confidence: float


class LearningCollector:
    def __init__(self, workspace_path: Path) -> None:
        self.workspace_path = workspace_path
        self.learned_dir = workspace_path / "learned"
        self._candidates: List[LearnedItem] = []

    def collect_from_diagnosis(
        self,
        diagnosis: DiagnosisReport,
        run_id: str,
        task_id: str,
    ) -> List[LearnedItem]:
        if not diagnosis.learnable:
            return []
        items: List[LearnedItem] = []
        sig = diagnosis.error_signature
        if sig:
            items.append(
                LearnedItem(
                    type="signature",
                    content={
                        "category": sig.category.value,
                        "error_type": sig.error_type,
                        "error_pattern": self._extract_pattern(sig.error_message),
                        "file_pattern": self._extract_file_pattern(sig.file_path),
                    },
                    source_run_id=run_id,
                    source_task_id=task_id,
                    timestamp=time.time(),
                    confidence=diagnosis.confidence,
                )
            )
        if diagnosis.successful_fix:
            items.append(
                LearnedItem(
                    type="hint",
                    content={
                        "trigger_signature": sig.error_type if sig else "unknown",
                        "hint": diagnosis.successful_fix,
                        "scope": "fix",
                    },
                    source_run_id=run_id,
                    source_task_id=task_id,
                    timestamp=time.time(),
                    confidence=diagnosis.confidence,
                )
            )
        if diagnosis.suggested_prevention:
            items.append(
                LearnedItem(
                    type="lesson",
                    content={
                        "content": diagnosis.suggested_prevention,
                        "context": diagnosis.root_cause_analysis[:100],
                        "tags": diagnosis.tags,
                    },
                    source_run_id=run_id,
                    source_task_id=task_id,
                    timestamp=time.time(),
                    confidence=diagnosis.confidence,
                )
            )
        self._candidates.extend(items)
        return items

    def get_candidates(self) -> List[LearnedItem]:
        return list(self._candidates)

    def clear_candidates(self) -> None:
        self._candidates = []

    def store_all(self, min_confidence: float = 0.5) -> int:
        self.learned_dir.mkdir(parents=True, exist_ok=True)
        stored = 0
        by_type: dict[str, List[LearnedItem]] = {}
        for item in self._candidates:
            if item.confidence < min_confidence:
                continue
            by_type.setdefault(item.type, []).append(item)
        for item_type, items in by_type.items():
            stored += self._store_items(item_type, items)
        self._candidates = []
        return stored

    def _store_items(self, item_type: str, items: List[LearnedItem]) -> int:
        mapping = {
            "signature": ("signatures.json", "signatures"),
            "hint": ("hints.json", "hints"),
            "lesson": ("lessons.json", "lessons"),
        }
        filename, key = mapping.get(item_type, (None, None))
        if not filename or not key:
            return 0
        file_path = self.learned_dir / filename
        existing: list[dict] = []
        if file_path.exists():
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                existing = data.get(key, [])
            except Exception:
                existing = []
        seen = {json.dumps(e.get("content", e), sort_keys=True) for e in existing}
        for item in items:
            marker = json.dumps(item.content, sort_keys=True)
            if marker in seen:
                continue
            seen.add(marker)
            existing.append(
                {
                    **item.content,
                    "source_run_id": item.source_run_id,
                    "source_task_id": item.source_task_id,
                    "timestamp": item.timestamp,
                    "confidence": item.confidence,
                }
            )
        file_path.write_text(
            json.dumps({key: existing}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return len(items)

    def _extract_pattern(self, message: str) -> str:
        pattern = re.sub(r"/[^\\s:]+/", "/", message or "")
        pattern = re.sub(r"line \\d+", "line N", pattern)
        pattern = re.sub(r"\\b\\d+\\b", "N", pattern)
        return pattern[:200]

    def _extract_file_pattern(self, path: Optional[str]) -> Optional[str]:
        if not path:
            return None
        return f"*/{Path(path).name}"
