from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from cli.run_utils import _collect_retry_ids, _load_backlog_tasks, _reset_tasks_to_todo
from sqlite_mirror import mirror_run, update_run_status
from workspace_utils import get_plan_dir, get_backlog_dir
from cli.utils import envelope, find_latest_run, read_status, resolve_run_dir, find_plan_workspace
from infra.io_utils import append_jsonl, read_json, write_json
from state import append_state_events


def cmd_plan(args, root: Path):
    plan_id = args.plan_id or time.strftime("plan-%Y%m%d-%H%M%S")
    cmd = ["python", "plan_and_run.py", "--root", str(root), "--task", args.task, "--plan-id", plan_id, "--no-run"]
    if args.workspace:
        cmd.extend(["--workspace", args.workspace])
    subprocess.check_call(cmd, cwd=root)
    plan_workspace = find_plan_workspace(root, plan_id) or args.workspace or ""
    exec_dir = get_plan_dir(root, plan_workspace, plan_id)
    plan_path = exec_dir / "plan.json"
    tasks_count = 0
    if plan_path.exists():
        plan = read_json(plan_path, default={})
        tasks = plan.get("raw_plan", {}).get("tasks", [])
        tasks_count = len(tasks)
    data = {
        "plan_id": plan_id,
        "workspace": plan_workspace,
        "tasks_count": tasks_count,
        "backlog_written": True,
        "artifacts_root": str(exec_dir),
    }
    res = envelope(True, data=data)
    print(json.dumps(res, ensure_ascii=False))


def cmd_run(args, root: Path):
    plan_id = args.plan_id or time.strftime("plan-%Y%m%d-%H%M%S")
    cmd = ["python", "plan_and_run.py", "--root", str(root), "--task", args.task, "--plan-id", plan_id, "--mode", args.mode]
    if args.workspace:
        cmd.extend(["--workspace", args.workspace])
    subprocess.check_call(cmd, cwd=root)
    plan_workspace = find_plan_workspace(root, plan_id) or args.workspace or ""
    exec_dir = get_plan_dir(root, plan_workspace, plan_id)
    run_dir = find_latest_run(exec_dir)
    status = read_status(run_dir) if run_dir else {"status": "unknown"}
    run_id = run_dir.name if run_dir else None
    workspace_value = plan_workspace or status.get("workspace_main_root") or status.get("workspace") or ""
    if run_id:
        mirror_run(
            root,
            run_id,
            plan_id,
            workspace=workspace_value,
            status=status.get("status", "unknown"),
            task=args.task,
        )
    data = {
        "run_id": run_id,
        "plan_id": plan_id,
        "status": status.get("status"),
        "progress": status.get("progress"),
        "mode": status.get("mode"),
        "patchset_path": status.get("patchset_path"),
        "changed_files_count": status.get("changed_files_count"),
        "workspace_main_root": status.get("workspace_main_root"),
        "workspace_stage_root": status.get("workspace_stage_root"),
        "workspace": workspace_value,
    }
    res = envelope(True, data=data)
    print(json.dumps(res, ensure_ascii=False))


def cmd_run_plan(args, root: Path):
    if not args.plan_id:
        print(json.dumps(envelope(False, error="plan_id is required"), ensure_ascii=False))
        return
    plan_workspace = find_plan_workspace(root, args.plan_id)
    workspace_arg = plan_workspace or args.workspace
    cmd = ["python", "-m", "services.controller_service", "--root", str(root), "--plan-id", args.plan_id, "--mode", args.mode]
    if workspace_arg:
        cmd.extend(["--workspace", workspace_arg])
    subprocess.check_call(cmd, cwd=root)
    exec_dir = get_plan_dir(root, plan_workspace or args.workspace or "", args.plan_id)
    run_dir = find_latest_run(exec_dir)
    status = read_status(run_dir) if run_dir else {"status": "unknown"}
    run_id = run_dir.name if run_dir else None
    workspace_value = plan_workspace or args.workspace or status.get("workspace_main_root") or status.get("workspace") or ""
    if run_id:
        mirror_run(
            root,
            run_id,
            args.plan_id,
            workspace=workspace_value,
            status=status.get("status", "unknown"),
            task="",
        )
    data = {
        "run_id": run_id,
        "plan_id": args.plan_id,
        "status": status.get("status"),
        "progress": status.get("progress"),
        "mode": status.get("mode"),
        "patchset_path": status.get("patchset_path"),
        "changed_files_count": status.get("changed_files_count"),
        "workspace_main_root": status.get("workspace_main_root"),
        "workspace_stage_root": status.get("workspace_stage_root"),
        "workspace": workspace_value,
    }
    res = envelope(True, data=data)
    print(json.dumps(res, ensure_ascii=False))


def cmd_retry(args, root: Path):
    plan_id = args.plan_id
    run_dir = resolve_run_dir(root, plan_id, args.run_id)
    if not run_dir:
        print(json.dumps(envelope(False, error="run not found"), ensure_ascii=False))
        return

    meta = read_json(run_dir / "meta.json", default={})
    task_id = meta.get("task_id")
    if not task_id:
        print(json.dumps(envelope(False, error="task_id missing"), ensure_ascii=False))
        return

    if not plan_id:
        plan_id = meta.get("plan_id")
    plan_workspace = find_plan_workspace(root, plan_id) or ""
    backlog_dir = get_backlog_dir(root, plan_workspace)
    backlog_dir.mkdir(parents=True, exist_ok=True)
    backlog_path = backlog_dir / f"{plan_id or ''}.json"
    backlog, tasks = _load_backlog_tasks(backlog_path)
    if not isinstance(tasks, list):
        tasks = []
    tasks_by_id = {t.get("id"): t for t in tasks if isinstance(t, dict)}
    if args.run_id and not plan_id:
        plan_id = meta.get("plan_id")
    reason = {"type": "retry_reset", "run_id": args.run_id, "retry_deps": bool(args.retry_deps)}
    reset_ids = _collect_retry_ids(tasks_by_id, task_id, args.retry_deps)
    now = time.time()
    events = _reset_tasks_to_todo(tasks, reset_ids, reason, now)
    if events:
        append_state_events(root, events)
    backlog["tasks"] = tasks
    write_json(backlog_path, backlog)

    snapshot_path = get_plan_dir(root, plan_workspace, plan_id) / "snapshot.json" if plan_id else None
    if snapshot_path and snapshot_path.exists():
        snapshot = read_json(snapshot_path, default={})
        snap_tasks = snapshot.get("tasks", []) if isinstance(snapshot, dict) else []
        if isinstance(snap_tasks, list):
            _reset_tasks_to_todo(snap_tasks, reset_ids, reason, now)
            snapshot["tasks"] = snap_tasks
            snapshot["snapshot_ts"] = now
            write_json(snapshot_path, snapshot)

    print(json.dumps(envelope(True, data={"reset": len(reset_ids)}), ensure_ascii=False))


def cmd_status(args, root: Path):
    run_dir = resolve_run_dir(root, args.plan_id, args.run_id)
    if not run_dir:
        print(json.dumps(envelope(False, error="run not found"), ensure_ascii=False))
        return
    status = read_status(run_dir)
    res = envelope(True, data=status)
    update_run_status(root, run_dir.name, status.get("status", "unknown"))
    print(json.dumps(res, ensure_ascii=False))


def cmd_events(args, root: Path):
    run_dir = resolve_run_dir(root, args.plan_id, args.run_id)
    if not run_dir:
        print(json.dumps(envelope(False, error="run not found"), ensure_ascii=False))
        return
    events_path = run_dir / "events.jsonl"
    if not events_path.exists():
        print(json.dumps(envelope(True, data={"events": [], "cursor": args.cursor, "next_cursor": args.cursor}), ensure_ascii=False))
        return
    lines = events_path.read_text(encoding="utf-8").splitlines()
    start = max(args.cursor - 1, 0)
    end = min(start + args.limit, len(lines))
    events = []
    for idx, line in enumerate(lines[start:end], start=start):
        if not line.strip():
            continue
        evt = json.loads(line)
        evt["event_id"] = idx + 1
        events.append(evt)
    data = {
        "run_id": run_dir.name,
        "cursor": start + 1,
        "next_cursor": end + 1,
        "cursor_type": "event_id",
        "total": len(lines),
        "events": events,
    }
    print(json.dumps(envelope(True, data=data), ensure_ascii=False))
