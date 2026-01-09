from __future__ import annotations

import time
import uuid
from dataclasses import asdict
from pathlib import Path

from .project_memory import ProjectMemory
from .rule_store import RuleStore
from .types import ExtraCheck, ImportedPack, Lesson, Rule


def _now() -> float:
    return time.time()


def _safe_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _ensure_id(value: str | None, prefix: str) -> str:
    return value or f"{prefix}-{uuid.uuid4().hex[:8]}"


def _schema_version(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class ExperiencePackService:
    PACK_TYPE = "experience-pack"
    SCHEMA_VERSION = 1

    def validate_pack(self, pack_data: dict) -> tuple[bool, str]:
        if not isinstance(pack_data, dict):
            return False, "pack must be an object"
        if pack_data.get("pack_type") != self.PACK_TYPE:
            return False, "pack_type mismatch"
        if _schema_version(pack_data.get("schema_version")) != self.SCHEMA_VERSION:
            return False, "schema_version mismatch"
        for key in ("rules", "extra_checks", "lessons", "patterns", "tags"):
            if key in pack_data and not isinstance(pack_data.get(key), list):
                return False, f"{key} must be a list"
        return True, ""
    def __init__(self, root: Path) -> None:
        self._root = root

    def _memory(self, workspace_id: str) -> ProjectMemory:
        memory = ProjectMemory(self._root, workspace_id)
        memory.load()
        self._migrate_legacy_rules(workspace_id, memory)
        return memory

    def _rule_store(self, workspace_id: str) -> RuleStore:
        return RuleStore(self._root, workspace_id)

    def _migrate_legacy_rules(self, workspace_id: str, memory: ProjectMemory) -> None:
        legacy_rules = memory.custom_rules.get("rules", [])
        if not legacy_rules:
            return
        store = self._rule_store(workspace_id)
        existing = store.load()
        existing_ids = {r.id for r in existing}
        merged = list(existing)
        for rule in legacy_rules:
            if rule.id not in existing_ids:
                merged.append(rule)
        store.save(merged)
        memory.custom_rules["rules"] = []
        memory.updated_at = _now()
        memory.save()

    def get_memory(self, workspace_id: str) -> dict:
        memory = self._memory(workspace_id)
        payload = memory.to_dict()
        custom = payload.get("custom_rules") if isinstance(payload.get("custom_rules"), dict) else {}
        custom["rules"] = [asdict(r) for r in self._rule_store(workspace_id).load()]
        payload["custom_rules"] = custom
        return payload

    def list_packs(self, workspace_id: str) -> list[ImportedPack]:
        memory = self._memory(workspace_id)
        return memory.imported_packs

    def get_pack(self, workspace_id: str, pack_id: str) -> ImportedPack | None:
        for pack in self.list_packs(workspace_id):
            if pack.id == pack_id:
                return pack
        return None

    def import_pack(self, workspace_id: str, pack_data: dict, source: str = "file") -> ImportedPack:
        memory = self._memory(workspace_id)
        now = _now()
        ok, reason = self.validate_pack(pack_data)
        if not ok:
            raise ValueError(f"invalid pack format: {reason}")
        def _rule_from(data: dict) -> Rule:
            return Rule(
                id=str(data.get("id", "")) or _ensure_id(None, "rule"),
                content=str(data.get("content", "")),
                scope=data.get("scope"),
                category=data.get("category"),
                created_at=float(data.get("created_at", 0) or 0) or now,
            )

        def _check_from(data: dict) -> ExtraCheck:
            return ExtraCheck(
                id=str(data.get("id", "")) or _ensure_id(None, "check"),
                check=data.get("check") if isinstance(data.get("check"), dict) else {},
                scope=data.get("scope"),
                created_at=float(data.get("created_at", 0) or 0) or now,
            )

        def _lesson_from(data: dict) -> Lesson:
            return Lesson(
                id=str(data.get("id", "")) or _ensure_id(None, "lesson"),
                lesson=str(data.get("lesson", "")),
                triggers=[t for t in _safe_list(data.get("triggers")) if isinstance(t, dict)],
                suggested_check=data.get("suggested_check") if isinstance(data.get("suggested_check"), dict) else None,
                confidence=data.get("confidence"),
                created_at=float(data.get("created_at", 0) or 0) or now,
            )

        pack = ImportedPack(
            id=_ensure_id(pack_data.get("id"), "pack"),
            name=str(pack_data.get("name", "")),
            version=str(pack_data.get("version", "1.0.0")),
            description=str(pack_data.get("description", "")),
            author=str(pack_data.get("author", "")),
            tags=[str(t) for t in _safe_list(pack_data.get("tags")) if str(t).strip()],
            rules=[],
            extra_checks=[_check_from(c) for c in _safe_list(pack_data.get("extra_checks")) if isinstance(c, dict)],
            lessons=[_lesson_from(l) for l in _safe_list(pack_data.get("lessons")) if isinstance(l, dict)],
            created_at=float(pack_data.get("created_at", 0) or 0) or now,
            updated_at=now,
            source=str(pack_data.get("source", source)),
            imported_at=now,
            enabled=bool(pack_data.get("enabled", True)),
        )
        replaced = False
        for idx, existing in enumerate(memory.imported_packs):
            if existing.id == pack.id:
                memory.imported_packs[idx] = pack
                replaced = True
                break
        if not replaced:
            memory.imported_packs.append(pack)
        memory.updated_at = now
        memory.save()
        return pack

    def delete_pack(self, workspace_id: str, pack_id: str) -> bool:
        memory = self._memory(workspace_id)
        before = len(memory.imported_packs)
        memory.imported_packs = [p for p in memory.imported_packs if p.id != pack_id]
        if len(memory.imported_packs) != before:
            memory.updated_at = _now()
            memory.save()
            return True
        return False

    def update_pack(self, workspace_id: str, pack_id: str, enabled: bool | None = None) -> ImportedPack | None:
        memory = self._memory(workspace_id)
        for idx, pack in enumerate(memory.imported_packs):
            if pack.id == pack_id:
                if enabled is not None:
                    pack.enabled = bool(enabled)
                pack.updated_at = _now()
                memory.imported_packs[idx] = pack
                memory.updated_at = _now()
                memory.save()
                return pack
        return None

    def import_workspace(
        self,
        workspace_id: str,
        from_workspace_id: str,
        include_rules: bool = True,
        include_checks: bool = True,
        include_lessons: bool = True,
        include_patterns: bool = True,
    ) -> ImportedPack:
        src = self._memory(from_workspace_id)
        now = _now()
        pack = ImportedPack(
            id=f"workspace-{from_workspace_id[:8]}-{uuid.uuid4().hex[:6]}",
            name=f"Workspace {from_workspace_id[:8]}",
            version="1.0.0",
            description="Imported from workspace",
            rules=[],
            extra_checks=src.custom_rules.get("extra_checks", []) if include_checks else [],
            lessons=src.lessons if include_lessons else [],
            source="workspace",
            imported_at=now,
            created_at=now,
            updated_at=now,
            enabled=True,
        )
        if include_patterns:
            pack.tags = [f"patterns:{len(src.patterns)}"]
        memory = self._memory(workspace_id)
        memory.imported_packs.append(pack)
        memory.updated_at = now
        memory.save()
        return pack

    def export_pack(
        self,
        workspace_id: str,
        name: str,
        description: str,
        include_rules: bool = True,
        include_checks: bool = True,
        include_lessons: bool = True,
        include_patterns: bool = True,
    ) -> dict:
        memory = self._memory(workspace_id)
        payload = {
            "pack_type": self.PACK_TYPE,
            "schema_version": self.SCHEMA_VERSION,
            "id": f"experience-{workspace_id[:8]}-{uuid.uuid4().hex[:6]}",
            "name": name,
            "version": "1.0.0",
            "description": description,
            "extra_checks": [asdict(c) for c in memory.custom_rules.get("extra_checks", [])] if include_checks else [],
            "lessons": [asdict(l) for l in memory.lessons] if include_lessons else [],
            "patterns": memory.patterns if include_patterns else [],
        }
        return payload

    def add_rule(self, workspace_id: str, content: str, scope: str | None, category: str | None) -> Rule:
        memory = self._memory(workspace_id)
        store = self._rule_store(workspace_id)
        rule = Rule(id=_ensure_id(None, "rule"), content=content, scope=scope, category=category, created_at=_now())
        rules = store.load()
        rules.append(rule)
        store.save(rules)
        memory.updated_at = _now()
        memory.save()
        return rule

    def delete_rule(self, workspace_id: str, rule_id: str) -> bool:
        memory = self._memory(workspace_id)
        store = self._rule_store(workspace_id)
        rules = store.load()
        before = len(rules)
        rules = [r for r in rules if r.id != rule_id]
        if len(rules) != before:
            store.save(rules)
            memory.updated_at = _now()
            memory.save()
            return True
        return False

    def add_check(self, workspace_id: str, check: dict, scope: str | None) -> ExtraCheck:
        memory = self._memory(workspace_id)
        extra = ExtraCheck(id=_ensure_id(None, "check"), check=check, scope=scope, created_at=_now())
        memory.custom_rules.setdefault("extra_checks", []).append(extra)
        memory.updated_at = _now()
        memory.save()
        return extra

    def delete_check(self, workspace_id: str, check_id: str) -> bool:
        memory = self._memory(workspace_id)
        before = len(memory.custom_rules.get("extra_checks", []))
        memory.custom_rules["extra_checks"] = [c for c in memory.custom_rules.get("extra_checks", []) if c.id != check_id]
        if len(memory.custom_rules.get("extra_checks", [])) != before:
            memory.updated_at = _now()
            memory.save()
            return True
        return False

    def delete_lesson(self, workspace_id: str, lesson_id: str | None = None) -> int:
        memory = self._memory(workspace_id)
        if lesson_id is None:
            count = len(memory.lessons)
            memory.lessons = []
        else:
            before = len(memory.lessons)
            memory.lessons = [l for l in memory.lessons if l.id != lesson_id]
            count = before - len(memory.lessons)
        if count:
            memory.updated_at = _now()
            memory.save()
        return count
