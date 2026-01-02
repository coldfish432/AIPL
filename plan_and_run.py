import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path

from state import (
    DEFAULT_STALE_AUTO_RESET,
    DEFAULT_STALE_SECONDS,
    scan_backlog_for_stale,
)
from infra.io_utils import read_json, write_json
from services.profile_service import DEFAULT_ALLOWED_COMMANDS, compute_fingerprint
from config import DEFAULT_DENY_COMMANDS, DEFAULT_DENY_WRITE, resolve_db_path
from policy_validator import validate_checks, default_path_rules, is_safe_relative_path
from detect_workspace import detect_workspace
from services.code_graph_service import CodeGraphService
from services.profile_service import ProfileService
from infra.path_guard import is_workspace_unsafe


def _normalize_cmd_path(path: str | Path) -> str:
    raw = str(path)
    if os.name == "nt" and raw.startswith("\\\\?\\"):
        return raw[4:]
    return raw


def _decode_codex_bytes(data: bytes) -> str:
    for enc in ("utf-8", "gbk"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


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
    codex_bin = os.environ.get("CODEX_BIN") or shutil.which("codex")
    if not codex_bin and os.name == "nt":
        for cand in ("codex.cmd", "codex.exe", "codex.bat"):
            codex_bin = shutil.which(cand)
            if codex_bin:
                break
    codex_bin = _normalize_cmd_path(codex_bin or "codex")
    root_arg = _normalize_cmd_path(root_dir)
    schema_arg = _normalize_cmd_path(schema_path)
    io_root = root_dir / ".tmp_custom" / "codex_io"
    io_root.mkdir(parents=True, exist_ok=True)
    prompt_path = io_root / "plan_prompt.txt"
    output_path = io_root / "plan_output.json"
    error_path = io_root / "plan_error.log"
    prompt_path.write_text(prompt, encoding="utf-8")
    cmd = [
        codex_bin, "exec", "--full-auto",
        "--sandbox", "workspace-write",
        "-C", root_arg,
        "--skip-git-repo-check",
        "--output-schema", schema_arg,
        "--color", "never",
    ]
    with prompt_path.open("r", encoding="utf-8") as stdin, output_path.open("w", encoding="utf-8") as stdout, error_path.open(
        "w", encoding="utf-8"
    ) as stderr:
        result = subprocess.run(
            cmd,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            shell=False,
        )
    if result.returncode != 0:
        err = _decode_codex_bytes(error_path.read_bytes()) if error_path.exists() else ""
        out = _decode_codex_bytes(output_path.read_bytes()) if output_path.exists() else ""
        raise RuntimeError((err or out or "codex failed").strip())
    return _decode_codex_bytes(output_path.read_bytes()).strip()


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


def _extract_safe_path(value: str) -> str | None:
    if not isinstance(value, str):
        return None
    if is_safe_relative_path(value):
        return value
    for token in re.findall(r"[A-Za-z0-9._/\\-]+", value):
        if is_safe_relative_path(token):
            return token
    return None


def _normalize_checks(checks: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for check in checks or []:
        if not isinstance(check, dict):
            continue
        ctype = check.get("type")
        if ctype in {"file_exists", "file_contains", "json_schema"}:
            raw_path = check.get("path", "")
            safe_path = _extract_safe_path(raw_path)
            if safe_path:
                check = dict(check)
                check["path"] = safe_path
        normalized.append(check)
    return normalized


def _auto_select_workspace(workspace: Path) -> Path:
    workspace = workspace.resolve()
    info = detect_workspace(workspace)
    detected = info.get("detected") or []
    if info.get("project_type") != "unknown" or detected or info.get("checks"):
        return workspace
    candidates: list[tuple[int, Path]] = []
    deny = set(DEFAULT_DENY_WRITE or [])
    for child in sorted(workspace.iterdir()):
        if not child.is_dir():
            continue
        name = child.name
        if name.startswith(".") or name in deny:
            continue
        sub_info = detect_workspace(child)
        sub_detected = sub_info.get("detected") or []
        if sub_info.get("project_type") == "unknown" and not sub_detected and not sub_info.get("checks"):
            continue
        score = len(sub_detected) + (1 if sub_info.get("checks") else 0)
        candidates.append((score, child))
    if not candidates:
        return workspace
    candidates.sort(key=lambda item: (-item[0], item[1].name.lower()))
    chosen = candidates[0][1]
    print(f"[WORKSPACE] auto-selected subdir: {chosen}")
    return chosen


# build readable task chain text
def build_task_chain_text(tasks: list[dict]) -> str:
    if not tasks:
        return "Task chain: (empty)"
    lines = ["Task chain:"]
    for idx, task in enumerate(tasks, 1):
        step_id = task.get("step_id") or task.get("id") or f"task-{idx}"
        title = task.get("title") or f"Task {idx}"
        deps = task.get("dependencies") or []
        dep_text = ", ".join(deps) if isinstance(deps, list) and deps else "-"
        lines.append(f"{idx}. {title} [{step_id}] (deps: {dep_text})")
    return "\n".join(lines)


def _ensure_sqlite_schema(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, plan_id TEXT, status TEXT, updated_at INTEGER, raw_json TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS plans (plan_id TEXT PRIMARY KEY, updated_at INTEGER, raw_json TEXT)")


def _mirror_plan_to_sqlite(root: Path, plan_id: str, tasks_count: int) -> None:
    db_path = resolve_db_path(root)
    if not db_path:
        return
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        now_ms = int(time.time() * 1000)
        payload = {
            "ok": True,
            "ts": int(time.time()),
            "data": {
                "plan_id": plan_id,
                "tasks_count": tasks_count,
            },
        }
        raw_json = json.dumps(payload, ensure_ascii=False)
        with sqlite3.connect(str(db_path)) as conn:
            _ensure_sqlite_schema(conn)
            conn.execute(
                "INSERT INTO plans(plan_id, updated_at, raw_json) VALUES(?,?,?) "
                "ON CONFLICT(plan_id) DO UPDATE SET updated_at=excluded.updated_at, raw_json=excluded.raw_json",
                (plan_id, now_ms, raw_json),
            )
            conn.commit()
    except Exception:
        return

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
    parser.add_argument("--mode", default="autopilot", choices=["autopilot", "manual"], help="run mode")
    parser.add_argument("--policy", default="guarded", help="execution policy")
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
    command_blacklist = list(DEFAULT_DENY_COMMANDS or [])
    workspace_checks: list[dict] = []
    workspace_path = None
    if args.workspace:
        workspace_path = _auto_select_workspace(Path(args.workspace))
        if is_workspace_unsafe(root, workspace_path):
            print(f"[POLICY] workspace path {workspace_path} includes engine root {root}; refusing to proceed.")
            return
        workspace_info = detect_workspace(workspace_path)
        workspace_checks = workspace_info.get("checks", []) if isinstance(workspace_info, dict) else []
        capabilities = (workspace_info or {}).get("capabilities", {}) if isinstance(workspace_info, dict) else {}
        discovered = [c.get("cmd") for c in capabilities.get("commands", []) if isinstance(c, dict) and c.get("cmd")]
        if discovered:
            command_blacklist = list(DEFAULT_DENY_COMMANDS or [])
        if capabilities:
            capabilities_block = json.dumps(capabilities, ensure_ascii=False, indent=2)
        profile = profile_service.ensure_profile(root, workspace_path)
        if profile.get("created"):
            profile = profile_service.propose_soft(root, workspace_path, reason="new_workspace")
        elif profile.get("fingerprint_changed"):
            profile = profile_service.propose_soft(root, workspace_path, reason="fingerprint_changed")
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
    task_chain_text = plan_obj.get("task_chain_text")
    if not isinstance(task_chain_text, str) or not task_chain_text.strip():
        task_chain_text = build_task_chain_text(plan_obj.get("tasks", []))

    exec_dir = root / "artifacts" / "executions" / plan_id
    exec_dir.mkdir(parents=True, exist_ok=True)
    if capabilities_block != "none":
        try:
            write_json(exec_dir / "capabilities.json", {"workspace": str(workspace_path) if workspace_path else args.workspace, "capabilities": json.loads(capabilities_block)})
        except Exception:
            pass
    workspace_fingerprint = None
    code_graph_path = None
    if workspace_path:
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
        for idx, t in enumerate(plan_obj.get("tasks", []), 1):
            rec = {"plan_id": plan_id, **t}
            step_id = rec.get("step_id") or rec.get("id") or f"step-{idx:02d}"
            rec["step_id"] = step_id
            if not isinstance(rec.get("checks"), list) or not rec.get("checks"):
                rec["checks"] = derive_checks_from_acceptance(rec.get("acceptance_criteria", []))
            rec["checks"] = _normalize_checks(rec.get("checks", []))
            rec["checks"] = _merge_checks(rec.get("checks", []), workspace_checks)
            rec["checks"], reasons = validate_checks(rec.get("checks", []), allowed_commands, command_blacklist=command_blacklist)
            if reasons:
                rec["validation_reasons"] = reasons
                validation_summary.append({"task_id": rec.get("id"), "reasons": reasons})
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


    existing_ids = {t["id"] for t in backlog.get("tasks", []) if t.get("id")}
    plan_backlog_path = backlog_dir / f"{plan_id}.json"
    plan_backlog = read_json(plan_backlog_path, default={"tasks": []})
    plan_tasks = plan_backlog.get("tasks", [])
    for idx, t in enumerate(plan_obj.get("tasks", []), 1):
        step_id = t.get("step_id") or f"step-{idx:02d}"
        task_id = t.get("id") or step_id
        if task_id in existing_ids:
            task_id = f"{task_id}_{int(time.time())}"
        existing_ids.add(task_id)

        checks = t.get("checks", []) if isinstance(t.get("checks"), list) else []
        if not checks:
            checks = derive_checks_from_acceptance(t.get("acceptance_criteria", []))
        checks = _normalize_checks(checks)
        checks = _merge_checks(checks, workspace_checks)
        checks, reasons = validate_checks(checks, allowed_commands, command_blacklist=command_blacklist)
        plan_tasks.append(
            {
                "id": task_id,
                "step_id": step_id,
                "title": t.get("title", f"Task {idx}"),
                "description": t.get("description", ""),
                "capabilities": t.get("capabilities", []),
                "artifacts": t.get("artifacts", []),
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
            "task_chain_text": task_chain_text,
            "validation": validation_summary,
            "code_graph_path": code_graph_path,
            "workspace_fingerprint": workspace_fingerprint,
            "created_ts": time.time(),
        },
    )
    (exec_dir / "plan.txt").write_text(task_chain_text, encoding="utf-8")
    _mirror_plan_to_sqlite(root, plan_id, len(plan_obj.get("tasks", []) or []))
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
        cmd = ["python", "-m", "services.controller_service", "--root", str(root), "--plan-id", plan_id, "--mode", args.mode, "--policy", args.policy]
        if workspace_path:
            cmd.extend(["--workspace", str(workspace_path)])
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
