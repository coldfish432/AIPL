import argparse
import json
import subprocess
import time
from pathlib import Path
import re

from state import (
    DEFAULT_STALE_AUTO_RESET,
    DEFAULT_STALE_SECONDS,
    scan_backlog_for_stale,
)
from profile import ensure_profile, propose_soft, DEFAULT_ALLOWED_COMMANDS
from policy_validator import validate_checks, default_path_rules


def read_json(path: Path) -> dict:
    if not path.exists():
        return {"tasks": []}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _merge_tasks(tasks: list[dict]) -> list[dict]:
    by_id: dict[str, dict] = {}
    for t in tasks:
        tid = t.get("id")
        if not tid:
            continue
        prev = by_id.get(tid)
        if not prev:
            by_id[tid] = t
            continue
        if prev.get("status") != "doing" and t.get("status") == "doing":
            by_id[tid] = t
    return list(by_id.values())


def _list_backlog_files(root: Path) -> list[Path]:
    backlog_dir = root / "backlog"
    if not backlog_dir.exists():
        return []
    return sorted(backlog_dir.glob("*.json"))


def _load_backlog_map(root: Path) -> dict[Path, list[dict]]:
    backlog_map: dict[Path, list[dict]] = {}
    for path in _list_backlog_files(root):
        if not path.exists():
            backlog_map[path] = []
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {"tasks": []}
        backlog_map[path] = data.get("tasks", [])
    return backlog_map


def _write_backlog_map(backlog_map: dict[Path, list[dict]]) -> None:
    for path, tasks in backlog_map.items():
        write_json(path, {"tasks": tasks})


def _load_active_backlog(root: Path) -> dict:
    backlog_map = _load_backlog_map(root)
    merged = _merge_tasks([t for tasks in backlog_map.values() for t in tasks])
    return {"tasks": merged}


def _split_tasks_by_plan(tasks: list[dict]) -> tuple[list[dict], dict[str, list[dict]]]:
    non_plan: list[dict] = []
    by_plan: dict[str, list[dict]] = {}
    for t in tasks:
        plan_id = t.get("plan_id")
        if plan_id:
            by_plan.setdefault(plan_id, []).append(t)
        else:
            non_plan.append(t)
    return non_plan, by_plan


def _write_plan_snapshot(root: Path, plan_id: str, stop_reason: str) -> None:
    backlog_map = _load_backlog_map(root)
    tasks = []
    for entries in backlog_map.values():
        for t in entries:
            if t.get("plan_id") == plan_id:
                tasks.append(t)
    snapshot = {
        "plan_id": plan_id,
        "snapshot_ts": time.time(),
        "stop_reason": stop_reason,
        "tasks": _merge_tasks(tasks),
    }
    exec_dir = root / "artifacts" / "executions" / plan_id
    exec_dir.mkdir(parents=True, exist_ok=True)
    write_json(exec_dir / "snapshot.json", snapshot)


def run_codex_plan(prompt: str, root_dir: Path) -> str:
    schema_path = root_dir / "schemas" / "plan.schema.json"
    cmd = [
        "codex", "exec", "--full-auto",
        "--sandbox", "workspace-write",
        "-C", str(root_dir),
        "--skip-git-repo-check",
        "--output-schema", str(schema_path),
        "--color", "never",
    ]
    result = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=True,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "codex failed").strip())
    return result.stdout.strip()


def has_todo(backlog: dict, plan_id: str) -> bool:
    for t in backlog.get("tasks", []):
        if t.get("plan_id") == plan_id and t.get("status") == "todo":
            return True
    return False


def has_runnable(backlog: dict, plan_id: str) -> bool:
    tasks = backlog.get("tasks", [])
    done = {t["id"] for t in tasks if t.get("plan_id") == plan_id and t.get("status") == "done"}
    for t in tasks:
        if t.get("plan_id") != plan_id or t.get("status") != "todo":
            continue
        deps = t.get("dependencies", [])
        if any(dep not in done for dep in deps):
            continue
        return True
    return False


def _extract_outputs_path(text: str) -> list[str]:
    matches = re.findall(r"(?:run_dir/)?outputs/([A-Za-z0-9_./-]+)", text)
    return [f"outputs/{m}" for m in matches]


def _extract_needle(text: str) -> str | None:
    for kw in ("contains", "含有", "包含"):
        if kw in text:
            after = text.split(kw, 1)[1].strip(" ：:，,。.")
            # Prefer quoted content if present.
            m = re.search(r"['\"]([^'\"]+)['\"]", after)
            if m:
                return m.group(1).strip()
            return after.strip() or None
    return None


def derive_checks_from_acceptance(acceptance: list[str]) -> list[dict]:
    checks: list[dict] = []
    for line in acceptance or []:
        for path in _extract_outputs_path(line):
            needle = _extract_needle(line)
            if needle:
                checks.append({"type": "file_contains", "path": path, "needle": needle})
            else:
                checks.append({"type": "file_exists", "path": path})
    return checks


def main():
    root = Path(__file__).parent
    backlog_dir = root / "backlog"
    goal_path = root / "goal.txt"

    parser = argparse.ArgumentParser(description="????????? Codex ?????")
    parser.add_argument("--task", required=True, help="?????????")
    parser.add_argument("--goal", help="?????????????? goal.txt")
    parser.add_argument("--plan-id", help="?? plan_id???????")
    parser.add_argument("--max-tasks", type=int, default=8, help="??????????????????")
    parser.add_argument("--no-run", action="store_true", help="?????? backlog??????")
    parser.add_argument("--cleanup", action="store_true", help="????/???????? plan ? backlog ?????? plan ??????")
    parser.add_argument("--workspace", help="?? workspace ?????? controller")
    parser.add_argument("--stale-seconds", type=int, default=DEFAULT_STALE_SECONDS, help="mark doing as stale after N seconds (0 to disable)")
    parser.add_argument("--stale-auto-reset", action="store_true", default=DEFAULT_STALE_AUTO_RESET, help="auto reset stale tasks to todo")
    parser.add_argument("--no-stale-auto-reset", action="store_true", help="disable auto reset even if env enables it")
    args = parser.parse_args()

    plan_id = args.plan_id or time.strftime("plan-%Y%m%d-%H%M%S")
    goal_text = args.goal or (goal_path.read_text(encoding="utf-8") if goal_path.exists() else "")
    user_task = args.task.strip()

    backlog_map = _load_backlog_map(root)
    auto_reset = args.stale_auto_reset and not args.no_stale_auto_reset
    if scan_backlog_for_stale(backlog_map, args.stale_seconds, auto_reset, root, source="plan_and_run"):
        _write_backlog_map(backlog_map)
    backlog = {"tasks": _merge_tasks([t for tasks in backlog_map.values() for t in tasks])}

    profile = None
    hard_block = "none"
    soft_block = "none"
    allowed_commands = list(DEFAULT_ALLOWED_COMMANDS)
    if args.workspace:
        profile = ensure_profile(root, Path(args.workspace))
        if profile.get("created"):
            profile = propose_soft(root, Path(args.workspace), reason="new_workspace")
        elif profile.get("fingerprint_changed"):
            profile = propose_soft(root, Path(args.workspace), reason="fingerprint_changed")
        effective_hard = profile.get("effective_hard") or {}
        allowed_commands = effective_hard.get("allowed_commands", allowed_commands) or allowed_commands
        hard_block = json.dumps(
            {
                "allow_write": effective_hard.get("allow_write", []),
                "deny_write": effective_hard.get("deny_write", []),
                "allowed_commands": allowed_commands,
                "command_timeout": effective_hard.get("command_timeout"),
                "max_concurrency": effective_hard.get("max_concurrency"),
                "path_rules": default_path_rules(),
            },
            ensure_ascii=False,
            indent=2,
        )
        soft_approved = profile.get("soft_approved")
        if soft_approved:
            soft_block = json.dumps(soft_approved, ensure_ascii=False, indent=2)
        print(f"[PROFILE] workspace_id={profile.get('workspace_id')} fingerprint={profile.get('fingerprint')}")

    tmpl = (root / "prompts" / "plan.txt").read_text(encoding="utf-8")
    prompt = tmpl.format(
        plan_id=plan_id,
        max_tasks=args.max_tasks,
        task_text=user_task,
        goal_text=goal_text,
        hard_block=hard_block,
        soft_block=soft_block,
    )

    raw_plan = run_codex_plan(prompt.strip(), root)
    plan_obj = json.loads(raw_plan)

    exec_dir = root / "artifacts" / "executions" / plan_id
    exec_dir.mkdir(parents=True, exist_ok=True)
    validation_summary = []
    tasks_record = exec_dir / "plan.tasks.jsonl"
    with tasks_record.open("w", encoding="utf-8") as f:
        for t in plan_obj.get("tasks", []):
            rec = {"plan_id": plan_id, **t}
            if not isinstance(rec.get("checks"), list) or not rec.get("checks"):
                rec["checks"] = derive_checks_from_acceptance(rec.get("acceptance_criteria", []))
            rec["checks"], reasons = validate_checks(rec.get("checks", []), allowed_commands)
            if reasons:
                rec["validation_reasons"] = reasons
                validation_summary.append({"task_id": rec.get("id"), "reasons": reasons})
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


    existing_ids = {t["id"] for t in backlog.get("tasks", []) if t.get("id")}
    plan_backlog_path = backlog_dir / f"{plan_id}.json"
    plan_backlog = read_json(plan_backlog_path)
    plan_tasks = plan_backlog.get("tasks", [])
    for idx, t in enumerate(plan_obj.get("tasks", []), 1):
        task_id = t.get("id") or f"{plan_id}-T{idx:02d}"
        if task_id in existing_ids:
            task_id = f"{task_id}_{int(time.time())}"
        existing_ids.add(task_id)

        checks = t.get("checks", []) if isinstance(t.get("checks"), list) else []
        if not checks:
            checks = derive_checks_from_acceptance(t.get("acceptance_criteria", []))
        checks, reasons = validate_checks(checks, allowed_commands)
        plan_tasks.append(
            {
                "id": task_id,
                "title": t.get("title", f"Task {idx}"),
                "type": "time_for_certainty",
                "priority": t.get("priority", 50),
                "estimated_minutes": t.get("estimated_minutes", 30),
                "status": "todo",
                "dependencies": t.get("dependencies", []),
                "acceptance_criteria": t.get("acceptance_criteria", []),
                "checks": checks,
                "validation_reasons": reasons,
                "plan_id": plan_id,
                "created_from_goal": goal_text,
                "created_ts": time.time(),
                "status_ts": time.time(),
            }
        )

    write_json(plan_backlog_path, {"tasks": plan_tasks})
    write_json(
        exec_dir / "plan.json",
        {
            "plan_id": plan_id,
            "input_task": user_task,
            "goal": goal_text,
            "prompt": prompt,
            "raw_plan": plan_obj,
            "validation": validation_summary,
            "created_ts": time.time(),
        },
    )
    print(f"[PLAN] added {len(plan_obj.get('tasks', []))} tasks to backlog under plan_id={plan_id}")

    if args.no_run:
        print("[PLAN] no-run flag set, skipping execution")
        if args.cleanup:
            print("[CLEANUP] skip cleanup when --no-run is set (nothing executed yet)")
        return

    stop_reason = "unknown"
    while True:
        backlog = _load_active_backlog(root)
        if not has_todo(backlog, plan_id):
            print(f"[PLAN DONE] no todo tasks for plan_id={plan_id}")
            stop_reason = "no_todo"
            break
        if not has_runnable(backlog, plan_id):
            print(f"[PLAN STOP] todo tasks remain but no runnable tasks for plan_id={plan_id} (??????????)")
            stop_reason = "no_runnable"
            break
        print(f"[RUN] invoking controller for plan_id={plan_id}")
        cmd = ["python", "controller.py", "--plan-id", plan_id]
        if args.workspace:
            cmd.extend(["--workspace", args.workspace])
        subprocess.check_call(cmd, cwd=root)

    _write_plan_snapshot(root, plan_id, stop_reason)

    if args.cleanup:
        backlog_map = _load_backlog_map(root)
        removed: list[dict] = []
        for path, tasks in backlog_map.items():
            keep: list[dict] = []
            for t in tasks:
                if t.get("plan_id") == plan_id:
                    removed.append(t)
                else:
                    keep.append(t)
            write_json(path, {"tasks": keep})

        plan_file = exec_dir / "plan.json"
        if plan_file.exists():
            plan_data = read_json(plan_file)
            plan_data["last_cleanup_ts"] = time.time()
            plan_data["cleanup_snapshot"] = removed
            write_json(plan_file, plan_data)

        print(f"[CLEANUP] removed {len(removed)} tasks for plan_id={plan_id} (recorded in plan file)")


if __name__ == "__main__":
    main()
