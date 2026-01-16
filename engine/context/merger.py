from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass
class MergeResult:
    rules: List[str]
    checks: List[dict]
    hints: List[str]
    lessons: List[str]
    rule_sources: Dict[str, str]
    conflicts_discarded: List[dict]


class ContextMerger:
    """
    Merge workspace configuration sources while honoring the alias priority.

    Prioritization:
        1. User configuration under `user/`.
        2. Imported packs under `user/imported_packs/`.
        3. Learned content under `learned/`.
    """

    def __init__(self, workspace_path: Path) -> None:
        self.workspace_path = workspace_path
        self.user_dir = workspace_path / "user"
        self.learned_dir = workspace_path / "learned"

    def merge_for_scope(self, scope: str) -> MergeResult:
        user_rules = self._load_user_rules(scope)
        user_checks = self._load_user_checks(scope)
        pack_rules = self._load_pack_rules(scope)
        pack_checks = self._load_pack_checks(scope)
        learned_hints = self._load_learned_hints(scope)
        learned_lessons = self._load_learned_lessons(scope)

        rules, sources, discarded = self._merge_rules(user_rules, pack_rules, [])
        checks = self._merge_checks(user_checks, pack_checks)

        return MergeResult(
            rules=rules,
            checks=checks,
            hints=learned_hints,
            lessons=learned_lessons,
            rule_sources=sources,
            conflicts_discarded=discarded,
        )

    def _merge_rules(
        self,
        user_rules: List[str],
        pack_rules: List[str],
        learned_rules: List[str],
    ) -> Tuple[List[str], Dict[str, str], List[dict]]:
        result: List[str] = []
        sources: Dict[str, str] = {}
        discarded: List[dict] = []
        seen_normalized: set[str] = set()

        for rule in user_rules:
            normalized = self._normalize_rule(rule)
            if normalized not in seen_normalized:
                seen_normalized.add(normalized)
                result.append(rule)
                sources[rule] = "user"

        for rule in pack_rules:
            normalized = self._normalize_rule(rule)
            if normalized not in seen_normalized:
                seen_normalized.add(normalized)
                result.append(rule)
                sources[rule] = "pack"
            else:
                discarded.append(
                    {"rule": rule, "source": "pack", "reason": "conflict_with_user"}
                )

        for rule in learned_rules:
            normalized = self._normalize_rule(rule)
            if normalized not in seen_normalized:
                seen_normalized.add(normalized)
                result.append(rule)
                sources[rule] = "learned"
            else:
                discarded.append(
                    {"rule": rule, "source": "learned", "reason": "conflict"}
                )

        return result, sources, discarded

    def _normalize_rule(self, rule: str) -> str:
        return rule.lower().strip()

    def _load_user_rules(self, scope: str) -> List[str]:
        rules_file = self.user_dir / "rules.json"
        if not rules_file.exists():
            return []
        try:
            data = json.loads(rules_file.read_text(encoding="utf-8"))
            return [
                r["content"]
                for r in data.get("rules", [])
                if r.get("scope") == scope
            ]
        except Exception:
            return []

    def _load_user_checks(self, scope: str) -> List[dict]:
        checks_file = self.user_dir / "checks.json"
        if not checks_file.exists():
            return []
        try:
            data = json.loads(checks_file.read_text(encoding="utf-8"))
            return [c for c in data.get("checks", []) if c.get("scope") == scope]
        except Exception:
            return []

    def _load_pack_rules(self, scope: str) -> List[str]:
        packs_dir = self.user_dir / "imported_packs"
        if not packs_dir.exists():
            return []
        rules: List[str] = []
        for pack_file in packs_dir.glob("*.json"):
            try:
                data = json.loads(pack_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            for r in data.get("rules", []):
                if r.get("scope") == scope:
                    rules.append(r.get("content", ""))
        return rules

    def _load_pack_checks(self, scope: str) -> List[dict]:
        packs_dir = self.user_dir / "imported_packs"
        if not packs_dir.exists():
            return []
        checks: List[dict] = []
        for pack_file in packs_dir.glob("*.json"):
            try:
                data = json.loads(pack_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            extra = data.get("extra_checks", [])
            for c in extra:
                if c.get("scope") == scope:
                    checks.append(c)
        return checks

    def _load_learned_hints(self, scope: str) -> List[str]:
        hints_file = self.learned_dir / "hints.json"
        if not hints_file.exists():
            return []
        try:
            data = json.loads(hints_file.read_text(encoding="utf-8"))
            return [
                h["content"]
                for h in data.get("hints", [])
                if h.get("scope") == scope
            ]
        except Exception:
            return []

    def _load_learned_lessons(self, scope: str) -> List[str]:
        lessons_file = self.learned_dir / "lessons.json"
        if not lessons_file.exists():
            return []
        try:
            data = json.loads(lessons_file.read_text(encoding="utf-8"))
            return [l["content"] for l in data.get("lessons", []) if l.get("scope") == scope]
        except Exception:
            return []

    def _merge_checks(
        self, user_checks: List[dict], pack_checks: List[dict]
    ) -> List[dict]:
        result = list(user_checks)
        seen_ids = {c.get("id") for c in user_checks if c.get("id")}
        for check in pack_checks:
            check_id = check.get("id")
            if check_id not in seen_ids:
                result.append(check)
                if check_id:
                    seen_ids.add(check_id)
        return result
