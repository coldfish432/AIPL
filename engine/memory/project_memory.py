from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .types import ExtraCheck, ImportedPack, Lesson, Rule


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


def _check_from_dict(data: dict) -> ExtraCheck:
    return ExtraCheck(
        id=str(data.get("id", "")),
        check=data.get("check") if isinstance(data.get("check"), dict) else {},
        scope=data.get("scope"),
        created_at=float(data.get("created_at", 0) or 0),
    )


def _lesson_from_dict(data: dict) -> Lesson:
    return Lesson(
        id=str(data.get("id", "")),
        lesson=str(data.get("lesson", "")),
        triggers=[t for t in _safe_list(data.get("triggers")) if isinstance(t, dict)],
        suggested_check=data.get("suggested_check") if isinstance(data.get("suggested_check"), dict) else None,
        confidence=data.get("confidence"),
        created_at=float(data.get("created_at", 0) or 0),
    )


def _imported_pack_from_dict(data: dict) -> ImportedPack:
    return ImportedPack(
        id=str(data.get("id", "")),
        name=str(data.get("name", "")),
        version=str(data.get("version", "1.0.0")),
        description=str(data.get("description", "")),
        author=str(data.get("author", "")),
        tags=[str(t) for t in _safe_list(data.get("tags")) if str(t).strip()],
        rules=[_rule_from_dict(r) for r in _safe_list(data.get("rules")) if isinstance(r, dict)],
        extra_checks=[_check_from_dict(c) for c in _safe_list(data.get("extra_checks")) if isinstance(c, dict)],
        lessons=[_lesson_from_dict(l) for l in _safe_list(data.get("lessons")) if isinstance(l, dict)],
        created_at=float(data.get("created_at", 0) or 0),
        updated_at=float(data.get("updated_at", 0) or 0),
        source=str(data.get("source", "file")),
        imported_at=float(data.get("imported_at", 0) or 0),
        enabled=bool(data.get("enabled", True)),
    )


def _to_dict_list(items: list) -> list:
    return [asdict(item) for item in items]


class ProjectMemory:
    def __init__(self, root: Path, workspace_id: str) -> None:
        self._path = root / "engine" / "data" / "memory" / f"{workspace_id}.json"
        self.custom_rules: dict[str, list] = {"rules": [], "extra_checks": []}
        self.lessons: list[Lesson] = []
        self.patterns: list[dict] = []
        self.imported_packs: list[ImportedPack] = []
        self.updated_at: float = 0

    def load(self) -> None:
        if not self._path.exists():
            return
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return
        if not isinstance(payload, dict):
            return
        custom = payload.get("custom_rules") if isinstance(payload.get("custom_rules"), dict) else {}
        self.custom_rules = {
            "rules": [_rule_from_dict(r) for r in _safe_list(custom.get("rules")) if isinstance(r, dict)],
            "extra_checks": [_check_from_dict(c) for c in _safe_list(custom.get("extra_checks")) if isinstance(c, dict)],
        }
        self.lessons = [_lesson_from_dict(l) for l in _safe_list(payload.get("lessons")) if isinstance(l, dict)]
        self.patterns = [p for p in _safe_list(payload.get("patterns")) if isinstance(p, dict)]
        self.imported_packs = [
            _imported_pack_from_dict(p) for p in _safe_list(payload.get("imported_packs")) if isinstance(p, dict)
        ]
        self.updated_at = float(payload.get("updated_at", 0) or 0)

    def to_dict(self) -> dict:
        return {
            "custom_rules": {
                "rules": _to_dict_list(self.custom_rules.get("rules", [])),
                "extra_checks": _to_dict_list(self.custom_rules.get("extra_checks", [])),
            },
            "lessons": _to_dict_list(self.lessons),
            "patterns": self.patterns,
            "imported_packs": _to_dict_list(self.imported_packs),
            "updated_at": self.updated_at,
        }

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
