from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from cli.utils import _load_payload, _resolve_workspace_id, envelope
from detect_workspace import detect_workspace
from engine.memory.pack_service import ExperiencePackService
from engine.patterns.service import LanguagePackService


def cmd_language_packs(args, root: Path):
    service = LanguagePackService(root)
    action = args.action
    if action == "list":
        ws_path = Path(args.workspace) if args.workspace else None
        project_type = None
        if ws_path:
            try:
                info = detect_workspace(ws_path)
                project_type = info.get("project_type") if isinstance(info, dict) else None
            except Exception:
                project_type = None
        data = service.list_packs(ws_path, project_type)
        print(json.dumps(envelope(True, data=data), ensure_ascii=False))
        return
    if action == "get":
        pack = service.export_pack(args.pack_id)
        if not pack:
            print(json.dumps(envelope(False, error="pack not found"), ensure_ascii=False))
            return
        print(json.dumps(envelope(True, data=pack), ensure_ascii=False))
        return
    if action == "import":
        payload = _load_payload(args.payload)
        if not payload:
            print(json.dumps(envelope(False, error="payload required"), ensure_ascii=False))
            return
        try:
            pack = service.import_pack(payload)
        except ValueError as err:
            print(json.dumps(envelope(False, error=str(err)), ensure_ascii=False))
            return
        payload = service.pack_to_dict(pack)
        print(json.dumps(envelope(True, data=payload), ensure_ascii=False))
        return
    if action == "export":
        pack = service.export_pack(args.pack_id)
        if not pack:
            print(json.dumps(envelope(False, error="pack not found"), ensure_ascii=False))
            return
        print(json.dumps(envelope(True, data=pack), ensure_ascii=False))
        return
    if action == "export-merged":
        pack = service.export_merged(args.pack_id, args.name or "", args.description or "")
        if not pack:
            print(json.dumps(envelope(False, error="pack not found"), ensure_ascii=False))
            return
        print(json.dumps(envelope(True, data=pack), ensure_ascii=False))
        return
    if action == "learned-export":
        pack = service.export_learned(args.name or "", args.description or "")
        if not pack:
            print(json.dumps(envelope(False, error="learned pack not found"), ensure_ascii=False))
            return
        print(json.dumps(envelope(True, data=pack), ensure_ascii=False))
        return
    if action == "delete":
        ok = service.delete_pack(args.pack_id)
        if not ok:
            print(json.dumps(envelope(False, error="pack not found"), ensure_ascii=False))
            return
        print(json.dumps(envelope(True, data={"deleted": True}), ensure_ascii=False))
        return
    if action == "update":
        pack = service.update_pack(args.pack_id, enabled=args.enabled)
        if not pack:
            print(json.dumps(envelope(False, error="pack not found"), ensure_ascii=False))
            return
        payload = service.pack_to_dict(pack)
        print(json.dumps(envelope(True, data=payload), ensure_ascii=False))
        return
    if action == "learned-clear":
        service.clear_learned()
        print(json.dumps(envelope(True, data={"cleared": True}), ensure_ascii=False))
        return
    print(json.dumps(envelope(False, error="unknown action"), ensure_ascii=False))


def cmd_memory(args, root: Path):
    workspace_id = _resolve_workspace_id(args.workspace_id, args.workspace)
    if not workspace_id:
        print(json.dumps(envelope(False, error="workspace_id is required"), ensure_ascii=False))
        return
    service = ExperiencePackService(root)
    data = service.get_memory(workspace_id)
    print(json.dumps(envelope(True, data=data), ensure_ascii=False))


def cmd_experience_packs(args, root: Path):
    workspace_id = _resolve_workspace_id(args.workspace_id, args.workspace)
    if not workspace_id:
        print(json.dumps(envelope(False, error="workspace_id is required"), ensure_ascii=False))
        return
    service = ExperiencePackService(root)
    action = args.action
    if action == "list":
        packs = [asdict(p) for p in service.list_packs(workspace_id)]
        print(json.dumps(envelope(True, data=packs), ensure_ascii=False))
        return
    if action == "get":
        pack = service.get_pack(workspace_id, args.pack_id)
        if not pack:
            print(json.dumps(envelope(False, error="pack not found"), ensure_ascii=False))
            return
        print(json.dumps(envelope(True, data=asdict(pack)), ensure_ascii=False))
        return
    if action == "import":
        payload = _load_payload(args.payload)
        if not payload:
            print(json.dumps(envelope(False, error="payload required"), ensure_ascii=False))
            return
        try:
            pack = service.import_pack(workspace_id, payload, source=payload.get("source", "file"))
        except ValueError as err:
            print(json.dumps(envelope(False, error=str(err)), ensure_ascii=False))
            return
        print(json.dumps(envelope(True, data=asdict(pack)), ensure_ascii=False))
        return
    if action == "import-workspace":
        pack = service.import_workspace(
            workspace_id,
            args.from_workspace_id,
            include_rules=bool(args.include_rules),
            include_checks=bool(args.include_checks),
            include_lessons=bool(args.include_lessons),
            include_patterns=bool(args.include_patterns),
        )
        print(json.dumps(envelope(True, data=asdict(pack)), ensure_ascii=False))
        return
    if action == "export":
        payload = service.export_pack(
            workspace_id,
            args.name or "",
            args.description or "",
            include_rules=bool(args.include_rules),
            include_checks=bool(args.include_checks),
            include_lessons=bool(args.include_lessons),
            include_patterns=bool(args.include_patterns),
        )
        print(json.dumps(envelope(True, data=payload), ensure_ascii=False))
        return
    if action == "delete":
        ok = service.delete_pack(workspace_id, args.pack_id)
        if not ok:
            print(json.dumps(envelope(False, error="pack not found"), ensure_ascii=False))
            return
        print(json.dumps(envelope(True, data={"deleted": True}), ensure_ascii=False))
        return
    if action == "update":
        pack = service.update_pack(workspace_id, args.pack_id, enabled=args.enabled)
        if not pack:
            print(json.dumps(envelope(False, error="pack not found"), ensure_ascii=False))
            return
        print(json.dumps(envelope(True, data=asdict(pack)), ensure_ascii=False))
        return
    print(json.dumps(envelope(False, error="unknown action"), ensure_ascii=False))


def cmd_rules(args, root: Path):
    workspace_id = _resolve_workspace_id(args.workspace_id, args.workspace)
    if not workspace_id:
        print(json.dumps(envelope(False, error="workspace_id is required"), ensure_ascii=False))
        return
    service = ExperiencePackService(root)
    if args.action == "add":
        rule = service.add_rule(workspace_id, args.content or "", args.scope, args.category)
        print(json.dumps(envelope(True, data=asdict(rule)), ensure_ascii=False))
        return
    if args.action == "delete":
        ok = service.delete_rule(workspace_id, args.rule_id)
        if not ok:
            print(json.dumps(envelope(False, error="rule not found"), ensure_ascii=False))
            return
        print(json.dumps(envelope(True, data={"deleted": True}), ensure_ascii=False))
        return
    print(json.dumps(envelope(False, error="unknown action"), ensure_ascii=False))


def cmd_checks(args, root: Path):
    workspace_id = _resolve_workspace_id(args.workspace_id, args.workspace)
    if not workspace_id:
        print(json.dumps(envelope(False, error="workspace_id is required"), ensure_ascii=False))
        return
    service = ExperiencePackService(root)
    if args.action == "add":
        payload = _load_payload(args.payload)
        if not payload:
            print(json.dumps(envelope(False, error="payload required"), ensure_ascii=False))
            return
        scope = payload.get("scope") if isinstance(payload, dict) else None
        if not scope:
            scope = args.scope
        check = service.add_check(workspace_id, payload.get("check", {}), scope)
        print(json.dumps(envelope(True, data=asdict(check)), ensure_ascii=False))
        return
    if args.action == "delete":
        ok = service.delete_check(workspace_id, args.check_id)
        if not ok:
            print(json.dumps(envelope(False, error="check not found"), ensure_ascii=False))
            return
        print(json.dumps(envelope(True, data={"deleted": True}), ensure_ascii=False))
        return
    print(json.dumps(envelope(False, error="unknown action"), ensure_ascii=False))


def cmd_lessons(args, root: Path):
    workspace_id = _resolve_workspace_id(args.workspace_id, args.workspace)
    if not workspace_id:
        print(json.dumps(envelope(False, error="workspace_id is required"), ensure_ascii=False))
        return
    service = ExperiencePackService(root)
    if args.action == "delete":
        count = service.delete_lesson(workspace_id, args.lesson_id)
        print(json.dumps(envelope(True, data={"deleted": count}), ensure_ascii=False))
        return
    if args.action == "clear":
        count = service.delete_lesson(workspace_id, None)
        print(json.dumps(envelope(True, data={"deleted": count}), ensure_ascii=False))
        return
    print(json.dumps(envelope(False, error="unknown action"), ensure_ascii=False))
