from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional


class UserConfigStore:
    def __init__(self, workspace_path: Path) -> None:
        self.workspace_path = workspace_path
        self.user_dir = workspace_path / "user"

    def get_rules(self, scope: Optional[str] = None) -> List[dict]:
        rules_file = self.user_dir / "rules.json"
        if not rules_file.exists():
            return []
        try:
            data = json.loads(rules_file.read_text(encoding="utf-8"))
        except Exception:
            return []
        rules = data.get("rules", [])
        if scope:
            return [r for r in rules if r.get("scope") == scope]
        return rules

    def get_checks(self, scope: Optional[str] = None) -> List[dict]:
        checks_file = self.user_dir / "checks.json"
        if not checks_file.exists():
            return []
        try:
            data = json.loads(checks_file.read_text(encoding="utf-8"))
        except Exception:
            return []
        checks = data.get("checks", [])
        if scope:
            return [c for c in checks if c.get("scope") == scope]
        return checks

    def get_imported_packs(self) -> List[dict]:
        packs_dir = self.user_dir / "imported_packs"
        if not packs_dir.exists():
            return []
        packs = []
        for pack_file in packs_dir.glob("*.json"):
            try:
                payload = json.loads(pack_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            payload["_file"] = pack_file.name
            packs.append(payload)
        return packs

    def has_rule(self, rule_content: str, scope: str) -> bool:
        normalized = rule_content.lower().strip()
        return any(
            r.get("content", "").lower().strip() == normalized
            for r in self.get_rules(scope)
        )

    def has_check(self, check_id: str) -> bool:
        return any(c.get("id") == check_id for c in self.get_checks())
