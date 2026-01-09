from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .types import Rule


def _safe_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _rule_from_dict(data: dict) -> Rule:
    return Rule(
        id=str(data.get("id", "")),
        content=str(data.get("content", "")),
        scope=data.get("scope"),
        category=data.get("category"),
        created_at=float(data.get("created_at", 0) or 0),
    )


class RuleStore:
    def __init__(self, root: Path, workspace_id: str) -> None:
        self._path = root / "engine" / "data" / "config" / "rules" / f"{workspace_id}.json"

    def load(self) -> list[Rule]:
        if not self._path.exists():
            return []
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(payload, list):
            return []
        return [_rule_from_dict(item) for item in payload if isinstance(item, dict)]

    def save(self, rules: list[Rule]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(rule) for rule in rules]
        self._path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
