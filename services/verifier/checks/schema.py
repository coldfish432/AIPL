from __future__ import annotations

import json
from pathlib import Path

from ..registry import register_check
from ..schema import validate_schema
from ..utils import reason
from .base import select_base_path


MAX_JSON_BYTES = 1024 * 1024
MAX_SCHEMA_DEPTH = 20
MAX_SCHEMA_ITEMS = 100


def _schema_depth(schema, depth: int = 0) -> int:
    if depth > MAX_SCHEMA_DEPTH:
        return depth
    if isinstance(schema, dict):
        return max([depth] + [_schema_depth(v, depth + 1) for v in schema.values()])
    if isinstance(schema, list):
        return max([depth] + [_schema_depth(v, depth + 1) for v in schema])
    return depth


def _load_schema(base: Path, schema, schema_path: str | None):
    if schema is not None:
        return schema, None
    if not schema_path:
        return None, reason("missing_schema", hint="provide schema or schema_path")
    schema_target = (base / schema_path).resolve()
    try:
        schema_target.relative_to(base.resolve())
    except Exception:
        return None, reason("missing_schema", hint="provide schema or schema_path")
    if not schema_target.exists():
        return None, reason("missing_schema", hint="provide schema or schema_path")
    return json.loads(schema_target.read_text(encoding="utf-8", errors="replace")), None


@register_check("json_schema")
def handle_json_schema(check: dict, run_dir: Path, workspace: Path | None, log_dir: Path, idx: int):
    path = check.get("path", "")
    base = select_base_path(run_dir, workspace, path)
    if not base:
        return False, reason("workspace_required", check_type="json_schema", hint="workspace path is required for this check"), None
    target = (base / path).resolve()
    try:
        target.relative_to(base.resolve())
    except Exception:
        return False, reason("invalid_path", file=path, hint="escape detected"), None
    if not target.exists():
        return False, reason("missing_file", file=path), None
    if target.stat().st_size > MAX_JSON_BYTES:
        return False, reason("file_too_large", file=path, expected=f"<= {MAX_JSON_BYTES} bytes"), None
    schema, err = _load_schema(base, check.get("schema"), check.get("schema_path"))
    if err:
        return False, err, None
    if _schema_depth(schema) > MAX_SCHEMA_DEPTH:
        return False, reason("schema_too_deep", expected=f"<= {MAX_SCHEMA_DEPTH}"), None
    data = json.loads(target.read_text(encoding="utf-8", errors="replace"))
    if isinstance(data, list) and len(data) > MAX_SCHEMA_ITEMS:
        data = data[:MAX_SCHEMA_ITEMS]
    ok, err = validate_schema(data, schema)
    reason_obj = None if ok else reason("schema_mismatch", file=path, expected=str(schema), actual=err)
    info = {"path": path, "schema": schema}
    return ok, reason_obj, info
