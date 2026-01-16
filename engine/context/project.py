from __future__ import annotations

from pathlib import Path

from detect_workspace import detect_workspace
from engine.memory.pack_service import ExperiencePackService
from engine.patterns.service import LanguagePackService
from services.profile_service import compute_workspace_id


class ProjectContext:
    def __init__(self, root: Path, workspace: Path | None = None) -> None:
        self.root = root
        self.workspace = workspace.resolve() if workspace else None
        self.workspace_id = compute_workspace_id(self.workspace) if self.workspace else None
        self.workspace_info = detect_workspace(self.workspace) if self.workspace else {}
        self.language_packs = LanguagePackService(root)
        self.experience_packs = ExperiencePackService(root)

    def list_language_packs(self) -> dict:
        project_type = self.workspace_info.get("project_type") if isinstance(self.workspace_info, dict) else None
        return self.language_packs.list_packs(self.workspace, project_type)

    def get_memory(self) -> dict:
        if not self.workspace_id:
            return {}
        return self.experience_packs.get_memory(self.workspace_id)

    def get_default_checks(self) -> list[dict]:
        checks: list[dict] = []
        memory = self.get_memory()
        if isinstance(memory, dict):
            custom = memory.get("custom_rules") if isinstance(memory.get("custom_rules"), dict) else {}
            checks.extend([c.get("check") for c in custom.get("extra_checks", []) if isinstance(c, dict)])
            for pack in memory.get("imported_packs", []) or []:
                if isinstance(pack, dict) and pack.get("enabled", True):
                    checks.extend([c.get("check") for c in pack.get("extra_checks", []) if isinstance(c, dict)])
            for lesson in memory.get("lessons", []) or []:
                if isinstance(lesson, dict) and isinstance(lesson.get("suggested_check"), dict):
                    checks.append(lesson.get("suggested_check"))
        if isinstance(self.workspace_info, dict):
            checks.extend(self.workspace_info.get("checks", []) or [])
        return [c for c in checks if isinstance(c, dict)]

    def analyze_failure(self, command: str, output: str) -> dict:
        project_type = self.workspace_info.get("project_type") if isinstance(self.workspace_info, dict) else None
        packs = self.language_packs.get_active_packs(self.workspace, project_type)
        failure_patterns = self.language_packs.match_command_patterns(command, packs)
        error_signatures = self.language_packs.match_error_signatures(output, packs)
        hints = self.language_packs.get_fix_hints(failure_patterns, error_signatures, packs)
        return {
            "failure_patterns": failure_patterns,
            "error_signatures": error_signatures,
            "hints": hints,
            "packs": [p.id for p in packs],
        }

    def get_hints(self, command: str, output: str) -> list[str]:
        analysis = self.analyze_failure(command, output)
        return analysis.get("hints", [])
