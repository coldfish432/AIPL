from __future__ import annotations

import json
import math
import time
from pathlib import Path


class LearningGC:
    DECAY_HALF_LIFE_DAYS = 30
    MAX_ITEMS_PER_TYPE = 500
    MIN_CONFIDENCE = 0.1

    def __init__(self, workspace_path: Path) -> None:
        self.workspace_path = workspace_path
        self.learned_dir = workspace_path / "learned"

    def run(self) -> dict[str, int]:
        stats = {"removed": 0, "decayed": 0}
        for filename in ["signatures.json", "hints.json", "lessons.json"]:
            file_path = self.learned_dir / filename
            if not file_path.exists():
                continue
            result = self._gc_file(file_path)
            stats["removed"] += result.get("removed", 0)
            stats["decayed"] += result.get("decayed", 0)
        return stats

    def _gc_file(self, file_path: Path) -> dict[str, int]:
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            return {"removed": 0, "decayed": 0}
        removed = 0
        decayed = 0
        for key, items in list(data.items()):
            if not isinstance(items, list):
                continue
            new_items = []
            for item in items:
                timestamp = item.get("timestamp", 0)
                age_days = (time.time() - timestamp) / 86400
                confidence = item.get("confidence", 0.5)
                decayed_conf = confidence * math.pow(0.5, age_days / self.DECAY_HALF_LIFE_DAYS)
                if decayed_conf < confidence:
                    decayed += 1
                if decayed_conf < self.MIN_CONFIDENCE:
                    removed += 1
                    continue
                item["confidence"] = decayed_conf
                new_items.append(item)
            if len(new_items) > self.MAX_ITEMS_PER_TYPE:
                new_items.sort(key=lambda x: x.get("confidence", 0), reverse=True)
                overflow = len(new_items) - self.MAX_ITEMS_PER_TYPE
                removed += overflow
                new_items = new_items[: self.MAX_ITEMS_PER_TYPE]
            data[key] = new_items
        file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"removed": removed, "decayed": decayed}
