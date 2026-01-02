from __future__ import annotations

import json
from pathlib import Path

from .utils import reason


def _list_backlog_files(root: Path) -> list[Path]:
    backlog_dir = root / "backlog"
    if not backlog_dir.exists():
        return []
    return sorted(backlog_dir.glob("*.json"))


def _find_task_in_backlog(root: Path, task_id: str) -> dict | None:
    for path in _list_backlog_files(root):
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for task in data.get("tasks", []):
            if task.get("id") == task_id:
                return task
    return None


def _infer_plan_id(root: Path, run_dir: Path) -> str | None:
    exec_root = root / "artifacts" / "executions"
    try:
        rel = run_dir.resolve().relative_to(exec_root.resolve())
    except Exception:
        return None
    parts = rel.parts
    return parts[0] if parts else None


def _find_task_in_history(root: Path, plan_id: str, task_id: str) -> dict | None:
    history_path = root / "artifacts" / "executions" / plan_id / "history.jsonl"
    if not history_path.exists():
        return None
    try:
        with history_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if rec.get("id") == task_id:
                    return rec
    except Exception:
        return None
    return None


def _find_task_in_plan_artifacts(root: Path, plan_id: str, task_id: str) -> dict | None:
    exec_root = root / "artifacts" / "executions" / plan_id
    tasks_path = exec_root / "plan.tasks.jsonl"
    if tasks_path.exists():
        try:
            with tasks_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    rec_id = rec.get("step_id") or rec.get("id")
                    if rec_id == task_id:
                        return rec
        except Exception:
            pass
    plan_path = exec_root / "plan.json"
    if plan_path.exists():
        try:
            plan_obj = json.loads(plan_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        tasks = plan_obj.get("raw_plan", {}).get("tasks", []) if isinstance(plan_obj, dict) else []
        for rec in tasks:
            if not isinstance(rec, dict):
                continue
            rec_id = rec.get("step_id") or rec.get("id")
            if rec_id == task_id:
                return rec
    return None


def load_task_context(root: Path, run_dir: Path, task_id: str):
    task = _find_task_in_backlog(root, task_id)
    if not task:
        plan_id = _infer_plan_id(root, run_dir)
        if plan_id:
            task = _find_task_in_history(root, plan_id, task_id)
            if not task:
                task = _find_task_in_plan_artifacts(root, plan_id, task_id)
    if not task:
        return [], None, None, None
    checks = task.get("checks", [])
    task_workspace = None
    if isinstance(task.get("workspace"), dict):
        task_workspace = task["workspace"].get("path")
    task_risk = task.get("risk_level", task.get("risk", task.get("high_risk")))
    retry_context = None
    if task.get("last_run") or task.get("last_reasons"):
        retry_context = reason(
            "retry_context",
            last_run=task.get("last_run"),
            last_reasons=task.get("last_reasons"),
        )
    return checks, task_workspace, retry_context, task_risk
