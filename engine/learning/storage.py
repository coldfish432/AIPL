from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


class LearningStorage:
    def __init__(self, workspace_path: Path) -> None:
        self.workspace_path = workspace_path
        self.learned_dir = workspace_path / "learned"

    def _load_file(self, filename: str, key: str) -> list[dict]:
        file_path = self.learned_dir / filename
        if not file_path.exists():
            return []
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            items = data.get(key, [])
            if isinstance(items, list):
                return items
        except Exception:
            return []
        return []

    def get_signatures(self, category: Optional[str] = None) -> list[dict]:
        items = self._load_file("signatures.json", "signatures")
        if category:
            return [i for i in items if i.get("category") == category]
        return items

    def get_hints(self, scope: Optional[str] = None) -> list[dict]:
        items = self._load_file("hints.json", "hints")
        if scope:
            return [i for i in items if i.get("scope") == scope]
        return items

    def get_lessons(self, limit: int = 10) -> list[dict]:
        items = self._load_file("lessons.json", "lessons")
        items.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        return items[:limit]

    def get_hints_for_error(self, error_type: str) -> list[str]:
        hints = self.get_hints(scope="fix")
        return [h.get("hint", "") for h in hints if h.get("trigger_signature") == error_type]
