from __future__ import annotations

import json
from pathlib import Path

from cli.run_utils import load_backlog_map, load_backlog_map_filtered
from cli.utils import (
    count_runs_by_status,
    envelope,
    list_artifacts,
    list_plans_for_workspace,
    resolve_run_dir,
)


def cmd_artifacts(args, root: Path):
    run_dir = resolve_run_dir(root, args.plan_id, args.run_id)
    if not run_dir and not args.plan_id:
        print(json.dumps(envelope(False, error="run not found"), ensure_ascii=False))
        return
    if args.plan_id:
        exec_dir = root / "artifacts" / "executions" / args.plan_id
        data = {
            "plan_id": args.plan_id,
            "artifacts_root": str(exec_dir),
            "runs": [],
        }
        if run_dir:
            data["run_id"] = run_dir.name
            data["items"] = list_artifacts(run_dir)
        print(json.dumps(envelope(True, data=data), ensure_ascii=False))
        return
    data = {
        "run_id": run_dir.name,
        "items": list_artifacts(run_dir),
    }
    print(json.dumps(envelope(True, data=data), ensure_ascii=False))


def cmd_dashboard_stats(args, root: Path):
    workspace = args.workspace
    plans = list_plans_for_workspace(root, workspace)
    plan_items = [
        {
            "plan_id": plan["plan_id"],
            "workspace": plan["workspace"],
            "tasks_count": plan["tasks_count"],
        }
        for plan in plans[:20]
    ]

    run_counts = count_runs_by_status(root, workspace)
    backlog_map = (
        load_backlog_map_filtered(root, workspace)
        if workspace
        else load_backlog_map(root)
    )
    all_tasks = [task for tasks in backlog_map.values() for task in tasks]
    tasks_by_status: dict[str, int] = {}
    for task in all_tasks:
        status = task.get("status") or "unknown"
        tasks_by_status[status] = tasks_by_status.get(status, 0) + 1

    data = {
        "workspace": workspace,
        "plans": {"total": len(plans), "items": plan_items},
        "runs": run_counts,
        "tasks": {"total": len(all_tasks), "by_status": tasks_by_status},
    }
    print(json.dumps(envelope(True, data=data), ensure_ascii=False))
