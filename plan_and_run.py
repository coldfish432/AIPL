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
from infra.io_utils import read_json, write_json
from services.profile_service import DEFAULT_ALLOWED_COMMANDS, compute_fingerprint
from policy_validator import validate_checks, default_path_rules
from detect_workspace import detect_workspace
from services.code_graph_service import CodeGraphService
from services.profile_service import ProfileService


# 合并任务
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


# 列出待办files，检查路径是否存在
def _list_backlog_files(root: Path) -> list[Path]:
    backlog_dir = root / "backlog"
    if not backlog_dir.exists():
        return []
    return sorted(backlog_dir.glob("*.json"))


# 加载待办map，读取文件内容
def _load_backlog_map(root: Path) -> dict[Path, list[dict]]:
    backlog_map: dict[Path, list[dict]] = {}
    for path in _list_backlog_files(root):
        data = read_json(path, default={"tasks": []})
        backlog_map[path] = (data or {}).get("tasks", [])
    return backlog_map


# 写入待办map，写入文件内容
def _write_backlog_map(backlog_map: dict[Path, list[dict]]) -> None:
    for path, tasks in backlog_map.items():
        write_json(path, {"tasks": tasks})


# 加载active待办
def _load_active_backlog(root: Path) -> dict:
    backlog_map = _load_backlog_map(root)
    merged = _merge_tasks([t for tasks in backlog_map.values() for t in tasks])
    return {"tasks": merged}


# split任务by计划
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


# 写入计划snapshot，写入文件内容，创建目录
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


# 运行codex计划，执行外部命令
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


# 判断是否包含todo
def has_todo(backlog: dict, plan_id: str) -> bool:
    for t in backlog.get("tasks", []):
        if t.get("plan_id") == plan_id and t.get("status") == "todo":
            return True
    return False


# 判断是否包含runnable
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


# extract输出路径
def _extract_outputs_path(text: str) -> list[str]:
    matches = re.findall(r"(?:run_dir/)?outputs/([A-Za-z0-9_./-]+)", text)
    return [f"outputs/{m}" for m in matches]


# extractneedle
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


# derive检查项fromacceptance
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


# 判断是否包含execution检查
def _has_execution_check(checks: list[dict]) -> bool:
    for check in checks or []:
        if check.get("type") in {"command", "command_contains", "http_check"}:
            return True
    return False


# 合并检查项
def _merge_checks(task_checks: list[dict], fallback_checks: list[dict]) -> list[dict]:
    if _has_execution_check(task_checks):
        return task_checks
    merged = list(task_checks or [])
    merged.extend(fallback_checks or [])
    return merged


# 主入口，解析命令行参数，读取文件内容
def main():
    parser = argparse.ArgumentParser(description="????????? Codex ?????")
    parser.add_argument("--root", required=True, help="repo root path")
    parser.add_argument("--task", required=True, help="?????????")
    parser.add_argument("--plan-id", help="?? plan_id???????")
    parser.add_argument("--max-tasks", type=int, default=8, help="??????????????????")
    parser.add_argument("--no-run", action="store_true", help="?????? backlog??????")
    parser.add_argument("--cleanup", action="store_true", help="????/???????? plan ? backlog ?????? plan ??????")
    parser.add_argument("--workspace", help="?? workspace ?????? controller")
    parser.add_argument("--code-graph-watch", action="store_true", help="watch workspace and update code graph cache")
    parser.add_argument("--stale-seconds", type=int, default=DEFAULT_STALE_SECONDS, help="mark doing as stale after N seconds (0 to disable)")
    parser.add_argument("--stale-auto-reset", action="store_true", default=DEFAULT_STALE_AUTO_RESET, help="auto reset stale tasks to todo")
    parser.add_argument("--no-stale-auto-reset", action="store_true", help="disable auto reset even if env enables it")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    backlog_dir = root / "backlog"
    profile_service = ProfileService()
    code_graph_service = CodeGraphService(cache_root=root)

    plan_id = args.plan_id or time.strftime("plan-%Y%m%d-%H%M%S")
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
    capabilities_block = "none"
    command_whitelist = None
    workspace_checks: list[dict] = []
    if args.workspace:
        workspace_info = detect_workspace(Path(args.workspace))
        workspace_checks = workspace_info.get("checks", []) if isinstance(workspace_info, dict) else []
        capabilities = (workspace_info or {}).get("capabilities", {}) if isinstance(workspace_info, dict) else {}
        discovered = [c.get("cmd") for c in capabilities.get("commands", []) if isinstance(c, dict) and c.get("cmd")]
        command_whitelist = [c for c in discovered if isinstance(c, str)]
        if capabilities:
            capabilities_block = json.dumps(capabilities, ensure_ascii=False, indent=2)
        profile = profile_service.ensure_profile(root, Path(args.workspace))
        if profile.get("created"):
            profile = profile_service.propose_soft(root, Path(args.workspace), reason="new_workspace")
        elif profile.get("fingerprint_changed"):
            profile = profile_service.propose_soft(root, Path(args.workspace), reason="fingerprint_changed")
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
        hard_block=hard_block,
        soft_block=soft_block,
        capabilities_block=capabilities_block,
    )

    raw_plan = run_codex_plan(prompt.strip(), root)
    plan_obj = json.loads(raw_plan)

    exec_dir = root / "artifacts" / "executions" / plan_id
    exec_dir.mkdir(parents=True, exist_ok=True)
    if capabilities_block != "none":
        try:
            write_json(exec_dir / "capabilities.json", {"workspace": args.workspace, "capabilities": json.loads(capabilities_block)})
        except Exception:
            pass
    workspace_fingerprint = None
    code_graph_path = None
    if args.workspace:
        workspace_path = Path(args.workspace)
        workspace_fingerprint = profile.get("fingerprint") if profile else compute_fingerprint(workspace_path)
        graph_path = exec_dir / "code-graph.json"
        needs_build = True
        if graph_path.exists():
            try:
                existing = code_graph_service.load(graph_path)
                if existing.fingerprint == workspace_fingerprint:
                    needs_build = False
            except Exception:
                needs_build = True
        if needs_build:
            try:
                graph = code_graph_service.build(workspace_path, fingerprint=workspace_fingerprint, watch=args.code_graph_watch)
                code_graph_service.save(graph, graph_path)
                print(f"[GRAPH] built code graph at {graph_path}")
            except Exception as e:
                print(f"[GRAPH] failed to build code graph: {e}")
        if graph_path.exists():
            code_graph_path = str(graph_path)
    validation_summary = []
    tasks_record = exec_dir / "plan.tasks.jsonl"
    with tasks_record.open("w", encoding="utf-8") as f:
        for t in plan_obj.get("tasks", []):
            rec = {"plan_id": plan_id, **t}
            if not isinstance(rec.get("checks"), list) or not rec.get("checks"):
                rec["checks"] = derive_checks_from_acceptance(rec.get("acceptance_criteria", []))
            rec["checks"] = _merge_checks(rec.get("checks", []), workspace_checks)
            rec["checks"], reasons = validate_checks(rec.get("checks", []), allowed_commands, command_whitelist=command_whitelist)
            if reasons:
                rec["validation_reasons"] = reasons
                validation_summary.append({"task_id": rec.get("id"), "reasons": reasons})
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


    existing_ids = {t["id"] for t in backlog.get("tasks", []) if t.get("id")}
    plan_backlog_path = backlog_dir / f"{plan_id}.json"
    plan_backlog = read_json(plan_backlog_path, default={"tasks": []})
    plan_tasks = plan_backlog.get("tasks", [])
    for idx, t in enumerate(plan_obj.get("tasks", []), 1):
        task_id = t.get("id") or f"{plan_id}-T{idx:02d}"
        if task_id in existing_ids:
            task_id = f"{task_id}_{int(time.time())}"
        existing_ids.add(task_id)

        checks = t.get("checks", []) if isinstance(t.get("checks"), list) else []
        if not checks:
            checks = derive_checks_from_acceptance(t.get("acceptance_criteria", []))
        checks = _merge_checks(checks, workspace_checks)
        checks, reasons = validate_checks(checks, allowed_commands, command_whitelist=command_whitelist)
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
            "prompt": prompt,
            "raw_plan": plan_obj,
            "validation": validation_summary,
            "code_graph_path": code_graph_path,
            "workspace_fingerprint": workspace_fingerprint,
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
        cmd = ["python", "-m", "services.controller_service", "--root", str(root), "--plan-id", plan_id]
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
            plan_data = read_json(plan_file, default={})
            plan_data["last_cleanup_ts"] = time.time()
            plan_data["cleanup_snapshot"] = removed
            write_json(plan_file, plan_data)

        print(f"[CLEANUP] removed {len(removed)} tasks for plan_id={plan_id} (recorded in plan file)")


if __name__ == "__main__":
    main()
