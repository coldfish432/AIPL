from __future__ import annotations

import json
import re
import time
from dataclasses import asdict
from pathlib import Path

from .builtin import BUILTIN_PACKS
from .types import CommandPattern, ErrorSignature, FixHint, LanguagePack, PackSource


def _now() -> float:
    return time.time()


def _safe_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _schema_version(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _pack_source(value: str | PackSource, fallback: PackSource) -> PackSource:
    if isinstance(value, PackSource):
        return value
    if isinstance(value, str):
        try:
            return PackSource(value)
        except Exception:
            return fallback
    return fallback


def _pattern_from_dict(data: dict) -> CommandPattern:
    return CommandPattern(
        id=str(data.get("id", "")),
        regex=str(data.get("regex", "")),
        failure_pattern=str(data.get("failure_pattern", "")),
        description=str(data.get("description", "")),
        confidence=float(data.get("confidence", 1.0) or 1.0),
        hit_count=int(data.get("hit_count", 0) or 0),
        last_hit=float(data.get("last_hit", 0) or 0),
    )


def _signature_from_dict(data: dict) -> ErrorSignature:
    return ErrorSignature(
        id=str(data.get("id", "")),
        regex=str(data.get("regex", "")),
        signature=str(data.get("signature", "")),
        description=str(data.get("description", "")),
        confidence=float(data.get("confidence", 1.0) or 1.0),
        hit_count=int(data.get("hit_count", 0) or 0),
        last_hit=float(data.get("last_hit", 0) or 0),
    )


def _fix_hint_from_dict(data: dict) -> FixHint:
    return FixHint(
        id=str(data.get("id", "")),
        trigger=str(data.get("trigger", "")),
        trigger_type=str(data.get("trigger_type", "")),
        hints=[str(h) for h in _safe_list(data.get("hints")) if str(h).strip()],
        confidence=float(data.get("confidence", 1.0) or 1.0),
        use_count=int(data.get("use_count", 0) or 0),
    )


def _pack_from_dict(data: dict, source_override: PackSource | None = None) -> LanguagePack:
    source = _pack_source(data.get("source", ""), source_override or PackSource.USER)
    pack = LanguagePack(
        id=str(data.get("id", "")),
        name=str(data.get("name", "")),
        version=str(data.get("version", "1.0.0")),
        description=str(data.get("description", "")),
        source=source,
        author=str(data.get("author", "")),
        tags=[str(t) for t in _safe_list(data.get("tags")) if str(t).strip()],
        detect_patterns=[str(p) for p in _safe_list(data.get("detect_patterns")) if str(p).strip()],
        project_types=[str(p) for p in _safe_list(data.get("project_types")) if str(p).strip()],
        command_patterns=[_pattern_from_dict(p) for p in _safe_list(data.get("command_patterns")) if isinstance(p, dict)],
        error_signatures=[_signature_from_dict(s) for s in _safe_list(data.get("error_signatures")) if isinstance(s, dict)],
        fix_hints=[_fix_hint_from_dict(h) for h in _safe_list(data.get("fix_hints")) if isinstance(h, dict)],
        enabled=bool(data.get("enabled", True)),
        priority=int(data.get("priority", 0) or 0),
        created_at=float(data.get("created_at", 0) or 0),
        updated_at=float(data.get("updated_at", 0) or 0),
    )
    return pack


def _pack_to_dict(pack: LanguagePack) -> dict:
    payload = asdict(pack)
    payload["source"] = pack.source.value
    payload["pack_type"] = PACK_TYPE
    payload["schema_version"] = SCHEMA_VERSION
    return payload


class LanguagePackService:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._data_dir = root / "engine" / "data" / "patterns"
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._user_path = self._data_dir / "user_packs.json"
        self._learned_path = self._data_dir / "learned.json"

    def _read_json(self, path: Path, default):
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def _write_json(self, path: Path, payload) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _load_user_packs(self) -> list[LanguagePack]:
        raw = self._read_json(self._user_path, [])
        if not isinstance(raw, list):
            raw = []
        return [_pack_from_dict(item, source_override=PackSource.USER) for item in raw if isinstance(item, dict)]

    def _save_user_packs(self, packs: list[LanguagePack]) -> None:
        payload = [_pack_to_dict(p) for p in packs]
        self._write_json(self._user_path, payload)

    def _load_learned_pack(self) -> LanguagePack | None:
        raw = self._read_json(self._learned_path, None)
        if not isinstance(raw, dict):
            return None
        return _pack_from_dict(raw, source_override=PackSource.LEARNED)

    def _save_learned_pack(self, pack: LanguagePack | None) -> None:
        if pack is None:
            if self._learned_path.exists():
                self._learned_path.unlink()
            return
        payload = _pack_to_dict(pack)
        self._write_json(self._learned_path, payload)

    def list_packs(self, workspace: Path | None = None, project_type: str | None = None) -> dict:
        builtin = list(BUILTIN_PACKS)
        user = self._load_user_packs()
        learned = self._load_learned_pack()
        all_packs = user + ([learned] if learned else []) + builtin
        active = []
        for pack in all_packs:
            if not pack or not pack.enabled:
                continue
            if self._matches(pack, workspace=workspace, project_type=project_type):
                active.append(pack.id)
        return {
            "builtin": [_pack_to_dict(p) for p in builtin],
            "user": [_pack_to_dict(p) for p in user],
            "learned": _pack_to_dict(learned) if learned else None,
            "active": active,
        }

    def get_active_packs(self, workspace: Path | None = None, project_type: str | None = None) -> list[LanguagePack]:
        packs = []
        for pack in self._load_user_packs():
            if pack.enabled and self._matches(pack, workspace, project_type):
                packs.append(pack)
        learned = self._load_learned_pack()
        if learned and learned.enabled and self._matches(learned, workspace, project_type):
            packs.append(learned)
        for pack in BUILTIN_PACKS:
            if pack.enabled and self._matches(pack, workspace, project_type):
                packs.append(pack)
        return packs

    def get_pack(self, pack_id: str) -> LanguagePack | None:
        for pack in self._load_user_packs():
            if pack.id == pack_id:
                return pack
        learned = self._load_learned_pack()
        if learned and learned.id == pack_id:
            return learned
        for pack in BUILTIN_PACKS:
            if pack.id == pack_id:
                return pack
        return None

    def import_pack(self, pack_data: dict) -> LanguagePack:
        ok, reason = self._validate_pack(pack_data)
        if not ok:
            raise ValueError(f"invalid pack format: {reason}")
        pack = _pack_from_dict(pack_data, source_override=PackSource.USER)
        pack.source = PackSource.USER
        now = _now()
        if not pack.created_at:
            pack.created_at = now
        pack.updated_at = now
        user = self._load_user_packs()
        replaced = False
        for idx, existing in enumerate(user):
            if existing.id == pack.id:
                user[idx] = pack
                replaced = True
                break
        if not replaced:
            user.append(pack)
        self._save_user_packs(user)
        return pack

    def _validate_pack(self, pack_data: dict) -> tuple[bool, str]:
        if not isinstance(pack_data, dict):
            return False, "pack must be an object"
        pack_type = pack_data.get("pack_type")
        if pack_type and pack_type != PACK_TYPE:
            return False, "pack_type mismatch"
        schema_value = pack_data.get("schema_version")
        if schema_value is not None and _schema_version(schema_value) != SCHEMA_VERSION:
            return False, "schema_version mismatch"
        for key in ("command_patterns", "error_signatures", "fix_hints", "detect_patterns", "project_types", "tags"):
            if key in pack_data and not isinstance(pack_data.get(key), list):
                return False, f"{key} must be a list"
        return True, ""

    def update_pack(self, pack_id: str, enabled: bool | None = None) -> LanguagePack | None:
        user = self._load_user_packs()
        for idx, pack in enumerate(user):
            if pack.id == pack_id:
                if enabled is not None:
                    pack.enabled = bool(enabled)
                pack.updated_at = _now()
                user[idx] = pack
                self._save_user_packs(user)
                return pack
        learned = self._load_learned_pack()
        if learned and learned.id == pack_id:
            if enabled is not None:
                learned.enabled = bool(enabled)
            learned.updated_at = _now()
            self._save_learned_pack(learned)
            return learned
        return None

    def delete_pack(self, pack_id: str) -> bool:
        user = self._load_user_packs()
        remaining = [p for p in user if p.id != pack_id]
        if len(remaining) != len(user):
            self._save_user_packs(remaining)
            return True
        return False

    def pack_to_dict(self, pack: LanguagePack | None) -> dict | None:
        return _pack_to_dict(pack) if pack else None

    def export_pack(self, pack_id: str) -> dict | None:
        pack = self.get_pack(pack_id)
        return _pack_to_dict(pack) if pack else None

    def export_learned(self, name: str, description: str) -> dict | None:
        learned = self._load_learned_pack()
        if not learned:
            return None
        merged = _pack_to_dict(learned)
        merged["id"] = f"learned-{int(_now())}"
        merged["name"] = name or merged.get("name", "Learned Pack")
        merged["description"] = description or merged.get("description", "")
        merged["source"] = PackSource.USER.value
        return merged

    def export_merged(self, pack_id: str, name: str, description: str) -> dict | None:
        base = self.get_pack(pack_id)
        learned = self._load_learned_pack()
        if not base:
            return None
        base_dict = _pack_to_dict(base)
        if learned:
            base_dict["command_patterns"] = _safe_list(base_dict.get("command_patterns")) + [
                asdict(p) for p in learned.command_patterns
            ]
            base_dict["error_signatures"] = _safe_list(base_dict.get("error_signatures")) + [
                asdict(s) for s in learned.error_signatures
            ]
            base_dict["fix_hints"] = _safe_list(base_dict.get("fix_hints")) + [asdict(h) for h in learned.fix_hints]
        base_dict["id"] = f"{pack_id}-merged-{int(_now())}"
        base_dict["name"] = name or base_dict.get("name", "")
        base_dict["description"] = description or base_dict.get("description", "")
        base_dict["source"] = PackSource.USER.value
        return base_dict

    def clear_learned(self) -> None:
        self._save_learned_pack(None)

    def match_command_patterns(self, command: str, packs: list[LanguagePack]) -> list[str]:
        patterns: list[str] = []
        for pack in packs:
            for cmd in pack.command_patterns:
                if not cmd.regex:
                    continue
                try:
                    if re.search(cmd.regex, command):
                        patterns.append(cmd.failure_pattern)
                        cmd.hit_count += 1
                        cmd.last_hit = _now()
                except re.error:
                    continue
        return patterns

    def match_error_signatures(self, output: str, packs: list[LanguagePack]) -> list[str]:
        signatures: list[str] = []
        for pack in packs:
            for sig in pack.error_signatures:
                if not sig.regex:
                    continue
                try:
                    if re.search(sig.regex, output):
                        signatures.append(sig.signature)
                        sig.hit_count += 1
                        sig.last_hit = _now()
                except re.error:
                    continue
        return signatures

    def get_fix_hints(self, failure_patterns: list[str], error_signatures: list[str], packs: list[LanguagePack]) -> list[str]:
        hints: list[str] = []
        pattern_set = set(failure_patterns or [])
        signature_set = set(error_signatures or [])
        for pack in packs:
            for hint in pack.fix_hints:
                if hint.trigger_type == "failure_pattern" and hint.trigger in pattern_set:
                    hints.extend(hint.hints)
                    hint.use_count += 1
                elif hint.trigger_type == "error_signature" and hint.trigger in signature_set:
                    hints.extend(hint.hints)
                    hint.use_count += 1
        return hints

    def learn_command_pattern(self, command: str, failure_pattern: str, description: str = "") -> CommandPattern:
        learned = self._ensure_learned_pack()
        now = _now()
        pat = CommandPattern(
            id=f"learned-cmd-{int(now)}",
            regex=re.escape(command),
            failure_pattern=failure_pattern,
            description=description,
            confidence=0.6,
            hit_count=1,
            last_hit=now,
        )
        learned.command_patterns.append(pat)
        learned.updated_at = now
        self._save_learned_pack(learned)
        return pat

    def learn_error_signature(self, signature: str, regex: str, description: str = "") -> ErrorSignature:
        learned = self._ensure_learned_pack()
        now = _now()
        sig = ErrorSignature(
            id=f"learned-err-{int(now)}",
            regex=regex,
            signature=signature,
            description=description,
            confidence=0.6,
            hit_count=1,
            last_hit=now,
        )
        learned.error_signatures.append(sig)
        learned.updated_at = now
        self._save_learned_pack(learned)
        return sig

    def learn_fix_hint(self, trigger: str, trigger_type: str, hints: list[str]) -> FixHint:
        learned = self._ensure_learned_pack()
        now = _now()
        hint = FixHint(
            id=f"learned-hint-{int(now)}",
            trigger=trigger,
            trigger_type=trigger_type,
            hints=[h for h in hints if h],
            confidence=0.6,
            use_count=0,
        )
        learned.fix_hints.append(hint)
        learned.updated_at = now
        self._save_learned_pack(learned)
        return hint

    def gc_learned(self, max_patterns: int = 200, max_signatures: int = 200, max_hints: int = 200) -> None:
        learned = self._load_learned_pack()
        if not learned:
            return
        learned.command_patterns = self._prune_items(learned.command_patterns, max_patterns)
        learned.error_signatures = self._prune_items(learned.error_signatures, max_signatures)
        learned.fix_hints = self._prune_items(learned.fix_hints, max_hints)
        learned.updated_at = _now()
        self._save_learned_pack(learned)

    def _matches(self, pack: LanguagePack, workspace: Path | None, project_type: str | None) -> bool:
        if project_type and project_type in pack.project_types:
            return True
        if not workspace or not pack.detect_patterns:
            return False
        for pattern in pack.detect_patterns:
            if self._has_match(workspace, pattern):
                return True
        return False

    def _has_match(self, workspace: Path, pattern: str) -> bool:
        try:
            for _ in workspace.rglob(pattern):
                return True
        except Exception:
            return False
        return False

    def _ensure_learned_pack(self) -> LanguagePack:
        learned = self._load_learned_pack()
        if learned:
            return learned
        now = _now()
        learned = LanguagePack(
            id="learned",
            name="Learned",
            version="1.0.0",
            description="Learned language patterns",
            source=PackSource.LEARNED,
            created_at=now,
            updated_at=now,
        )
        self._save_learned_pack(learned)
        return learned

    def _prune_items(self, items: list, max_count: int) -> list:
        if len(items) <= max_count:
            return items
        def score(item) -> tuple:
            confidence = getattr(item, "confidence", 0)
            last_hit = getattr(item, "last_hit", 0)
            use_count = getattr(item, "use_count", 0)
            hit_count = getattr(item, "hit_count", 0)
            return (confidence, use_count, hit_count, last_hit)
        items = sorted(items, key=score, reverse=True)
        return items[:max_count]
PACK_TYPE = "language-pack"
SCHEMA_VERSION = 1
