from __future__ import annotations

import json
import time
from pathlib import Path

from config import DEFAULT_STALE_AUTO_RESET, DEFAULT_STALE_SECONDS
STATUS_TODO = "todo"
STATUS_DOING = "doing"
STATUS_STALE = "stale"
STATUS_DONE = "done"
STATUS_FAILED = "failed"
STATUS_CANCELED = "canceled"

ACTIVE_STATUSES = {STATUS_TODO, STATUS_DOING, STATUS_STALE}
TERMINAL_STATUSES = {STATUS_DONE, STATUS_FAILED, STATUS_CANCELED}

TRANSITIONS: dict[str | None, set[str]] = {
    None: {STATUS_TODO},
    STATUS_TODO: {STATUS_DOING, STATUS_CANCELED},
    STATUS_DOING: {STATUS_DONE, STATUS_FAILED, STATUS_CANCELED, STATUS_STALE},
    STATUS_STALE: {STATUS_TODO, STATUS_DOING, STATUS_CANCELED},
    STATUS_DONE: set(),
    STATUS_FAILED: set(),
    STATUS_CANCELED: set(),
}


# 判断是否validtransition
def is_valid_transition(from_status: str | None, to_status: str) -> bool:
    if to_status not in ACTIVE_STATUSES and to_status not in TERMINAL_STATUSES:
        return False
    allowed = TRANSITIONS.get(from_status, set())
    return to_status in allowed


# 构建transition事件
def build_transition_event(
    task: dict,
    from_status: str | None,
    to_status: str,
    now: float,
    source: str | None = None,
    reason: dict | list | str | None = None,
) -> dict:
    event = {
        "type": "status_transition",
        "task_id": task.get("id"),
        "plan_id": task.get("plan_id"),
        "from": from_status,
        "to": to_status,
        "ts": now,
    }
    if source:
        event["source"] = source
    if reason is not None:
        event["reason"] = reason
    return event


# transition任务
def transition_task(
    task: dict,
    to_status: str,
    now: float | None = None,
    source: str | None = None,
    reason: dict | list | str | None = None,
) -> dict | None:
    from_status = task.get("status")
    if from_status == to_status:
        return None
    if not is_valid_transition(from_status, to_status):
        return None
    now = now or time.time()
    task["status"] = to_status
    task["status_ts"] = now
    if to_status == STATUS_DOING:
        task["heartbeat_ts"] = now
    if to_status == STATUS_STALE:
        task["stale_ts"] = now
        task["stale_count"] = int(task.get("stale_count", 0)) + 1
    return build_transition_event(task, from_status, to_status, now, source=source, reason=reason)


# touchheartbeat
def touch_heartbeat(task: dict, now: float | None = None) -> None:
    task["heartbeat_ts"] = now or time.time()


# 状态events路径
def state_events_path(root: Path) -> Path:
    return root / "artifacts" / "state" / "events.jsonl"


# 追加状态events，创建目录，读取文件
def append_state_events(root: Path, events: list[dict]) -> None:
    if not events:
        return
    path = state_events_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")


# stalereferencets
def _stale_reference_ts(task: dict) -> float | None:
    for key in ("heartbeat_ts", "status_ts", "created_ts"):
        ts = task.get(key)
        if isinstance(ts, (int, float)) and ts > 0:
            return float(ts)
    return None


# scan待办forstale
def scan_backlog_for_stale(
    backlog_map: dict[Path, list[dict]],
    stale_after_seconds: int,
    auto_reset: bool,
    root: Path,
    source: str,
) -> bool:
    if stale_after_seconds <= 0:
        return False
    now = time.time()
    events: list[dict] = []
    changed = False
    for tasks in backlog_map.values():
        for task in tasks:
            if task.get("status") != STATUS_DOING:
                continue
            ref_ts = _stale_reference_ts(task)
            if not ref_ts:
                continue
            age = now - ref_ts
            if age < stale_after_seconds:
                continue
            reason = {"type": "stale", "age_seconds": int(age)}
            event = transition_task(task, STATUS_STALE, now=now, source=source, reason=reason)
            if event:
                events.append(event)
                changed = True
            if auto_reset:
                event = transition_task(task, STATUS_TODO, now=now, source=source, reason=reason)
                if event:
                    events.append(event)
                    changed = True
    append_state_events(root, events)
    return changed
