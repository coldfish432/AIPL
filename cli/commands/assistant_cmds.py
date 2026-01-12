from __future__ import annotations

import json
import re
from pathlib import Path

from cli.utils import (
    _build_workspace_context,
    _extract_last_json,
    _format_conversation,
    _resolve_workspace_target,
    envelope,
    run_codex_chat,
)
from infra.io_utils import read_json


def _parse_intent_markers(text: str) -> dict:
    result = {
        "intent": None,
        "task_summary": None,
        "task_files": [],
        "task_operations": [],
        "clean_reply": text,
    }

    intent_match = re.search(r'\[INTENT:(\w+)\]', text)
    if intent_match:
        result["intent"] = intent_match.group(1).lower()

    summary_match = re.search(r'\[TASK_SUMMARY:([^\]]+)\]', text, re.DOTALL)
    if summary_match:
        result["task_summary"] = summary_match.group(1).strip()

    files_match = re.search(r'\[TASK_FILES:([^\]]+)\]', text)
    if files_match:
        result["task_files"] = [
            f.strip()
            for f in files_match.group(1).split(",")
            if f.strip()
        ]

    operations_match = re.search(r'\[TASK_OPERATIONS:([^\]]+)\]', text)
    if operations_match:
        result["task_operations"] = [
            op.strip()
            for op in operations_match.group(1).split(",")
            if op.strip()
        ]

    clean = text
    clean = re.sub(r'\[INTENT:\w+\]', "", clean)
    clean = re.sub(r'\[TASK_SUMMARY:[^\]]*\]', "", clean, flags=re.DOTALL)
    clean = re.sub(r'\[TASK_FILES:[^\]]*\]', "", clean)
    clean = re.sub(r'\[TASK_OPERATIONS:[^\]]*\]', "", clean)
    result["clean_reply"] = clean.strip()

    return result


def cmd_assistant_chat(args, root: Path):
    if not args.messages_file:
        print(json.dumps(envelope(False, error="messages_file is required"), ensure_ascii=False))
        return
    messages_path = Path(args.messages_file)
    if not messages_path.exists():
        print(json.dumps(envelope(False, error="messages_file not found"), ensure_ascii=False))
        return
    payload = read_json(messages_path, default={})
    messages = payload.get("messages", []) if isinstance(payload, dict) else []
    if not isinstance(messages, list):
        messages = []

    workspace_path = None
    if hasattr(args, "workspace") and args.workspace:
        workspace_path = Path(args.workspace)

    resolved_workspace = _resolve_workspace_target(root, workspace_path)
    workspace_context = _build_workspace_context(root, workspace_path, resolved_workspace=resolved_workspace)
    conversation = _format_conversation(messages)
    tmpl_path = root / "prompts" / "chat.txt"
    tmpl = tmpl_path.read_text(encoding="utf-8")
    prompt = tmpl.format(
        workspace_context=workspace_context,
        conversation=conversation,
    )
    raw_reply = run_codex_chat(prompt.strip(), root, resolved_workspace)
    reply = ""
    try:
        reply_obj = json.loads(_extract_last_json(raw_reply))
        reply = reply_obj.get("reply", "")
    except Exception:
        reply = raw_reply.strip()

    parsed = _parse_intent_markers(reply)
    data = {
        "reply": parsed["clean_reply"],
        "intent": parsed["intent"],
        "task_summary": parsed["task_summary"],
        "task_files": parsed["task_files"],
        "task_operations": parsed["task_operations"],
    }

    res = envelope(True, data=data)
    print(json.dumps(res, ensure_ascii=False))
