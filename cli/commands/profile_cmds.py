from __future__ import annotations

import json
from pathlib import Path

from cli.utils import _load_payload, envelope
from services.profile_service import ProfileService, ensure_profile


def cmd_profile(args, root: Path):
    profile_service = ProfileService()
    if not args.workspace:
        print(json.dumps(envelope(False, error="workspace is required"), ensure_ascii=False))
        return
    workspace = Path(args.workspace)
    action = args.action
    if action == "get":
        profile = profile_service.ensure_profile(root, workspace)
    elif action == "update":
        payload = _load_payload(args.payload)
        user_hard = payload.get("user_hard") if isinstance(payload, dict) else None
        if isinstance(payload, dict) and "user_hard" not in payload:
            user_hard = payload
        profile = profile_service.update_user_hard(root, workspace, user_hard if isinstance(user_hard, dict) else None)
    else:
        print(json.dumps(envelope(False, error="unknown action"), ensure_ascii=False))
        return

    effective_hard = profile.get("effective_hard")
    if effective_hard is None:
        effective_hard = ensure_profile(root, workspace).get("effective_hard")
    payload = {
        "workspace_id": profile.get("workspace_id"),
        "workspace_path": profile.get("workspace_path"),
        "fingerprint": profile.get("fingerprint"),
        "effective_hard": effective_hard,
        "system_hard": profile.get("system_hard"),
        "user_hard": profile.get("user_hard"),
    }
    res = envelope(True, data=payload)
    print(json.dumps(res, ensure_ascii=False))
