import argparse
import json
import subprocess
import time
from pathlib import Path
from verifier import verify_task
from detect_workspace import detect_workspace
from profile import ensure_profile, propose_soft, should_propose_on_failure


def read_json(path: Path):
    if not path.exists():
        return {"tasks": []}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def append_jsonl(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _list_backlog_files(root: Path) -> list[Path]:
    backlog_dir = root / "backlog"
    if not backlog_dir.exists():
        return []
    return sorted(backlog_dir.glob("*.json"))


def _load_backlog_map(root: Path) -> dict[Path, list[dict]]:
    backlog_map: dict[Path, list[dict]] = {}
    for path in _list_backlog_files(root):
        backlog_map[path] = read_json(path).get("tasks", [])
    return backlog_map


def load_policy(root: Path, workspace_path: str | None) -> tuple[dict, str, dict | None]:
    """
    load effective hard policy (user_hard overlay on system_hard) and optional checks.
    """
    if not workspace_path:
        return {}, "none", None
    workspace = Path(workspace_path)
    profile = ensure_profile(root, workspace)
    if profile.get("created"):
        profile = propose_soft(root, workspace, reason="new_workspace")
    elif profile.get("fingerprint_changed"):
        profile = propose_soft(root, workspace, reason="fingerprint_changed")
    effective_hard = profile.get("effective_hard") or {}
    checks = detect_workspace(workspace).get("checks", [])
    policy = {
        "allow_write": effective_hard.get("allow_write", []),
        "deny_write": effective_hard.get("deny_write", []),
        "allowed_commands": effective_hard.get("allowed_commands", []),
        "command_timeout": effective_hard.get("command_timeout", 300),
        "max_concurrency": effective_hard.get("max_concurrency", 1),
        "checks": checks,
        "workspace_id": profile.get("workspace_id"),
        "fingerprint": profile.get("fingerprint"),
    }
    return policy, "profile", profile


def pick_next_task(tasks_with_path: list[tuple[dict, Path]], plan_filter: str | None = None):
    tasks = [t for t, _ in tasks_with_path]
    if plan_filter:
        done = {t["id"] for t in tasks if t.get("status") == "done" and t.get("plan_id") == plan_filter}
    else:
        done = {t["id"] for t in tasks if t.get("status") == "done"}

    candidates = []
    for t, path in tasks_with_path:
        if plan_filter and t.get("plan_id") != plan_filter:
            continue
        if t.get("status") != "todo":
            continue
        deps = t.get("dependencies", [])
        if any(dep not in done for dep in deps):
            continue
        if t.get("type") != "time_for_certainty":
            continue
        candidates.append((t, path))

    if not candidates:
        return None, None

    candidates.sort(key=lambda x: x[0].get("priority", 0), reverse=True)
    return candidates[0]


def format_checks(checks: list[dict]) -> list[str]:
    lines = []
    for c in checks:
        ctype = c.get("type")
        if ctype == "command":
            timeout = c.get("timeout", "")
            lines.append(f"- command: {c.get('cmd')} timeout={timeout}")
        elif ctype == "file_exists":
            lines.append(f"- file_exists: {c.get('path')}")
        elif ctype == "file_contains":
            lines.append(f"- file_contains: {c.get('path')} needle={c.get('needle')}")
        else:
            lines.append(f"- unknown: {json.dumps(c, ensure_ascii=False)}")
    return lines


def write_verification_report(run_dir: Path, task_id: str, plan_id: str | None, workspace_path: str | None, passed: bool, reasons: list, checks: list[dict]):
    lines = [
        "# Verification Report",
        f"- task_id: {task_id}",
        f"- plan_id: {plan_id}",
        f"- run_dir: {run_dir}",
        f"- workspace: {workspace_path}",
        f"- passed: {passed}",
        "",
        "## Checks",
    ]
    lines.extend(format_checks(checks) or ["- (none)"])
    lines.append("")
    lines.append("## How To Verify")
    if checks:
        for c in checks:
            if c.get("type") == "command":
                lines.append(f"- run: {c.get('cmd')}")
            elif c.get("type") == "file_exists":
                lines.append(f"- check file exists: {c.get('path')}")
            elif c.get("type") == "file_contains":
                lines.append(f"- check file contains: {c.get('path')} -> {c.get('needle')}")
            else:
                lines.append(f"- manual check: {json.dumps(c, ensure_ascii=False)}")
    else:
        lines.append("- no checks available")

    lines.append("")
    lines.append("## Failure Reasons")
    if reasons:
        for r in reasons:
            lines.append(f"- {json.dumps(r, ensure_ascii=False)}")
    else:
        lines.append("- none")

    (run_dir / "verification_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan-id", dest="plan_id", help="?????? plan_id ???")
    parser.add_argument("--workspace", dest="workspace", help="?? workspace ????????? workspace ????????")
    parser.add_argument("--max-rounds", dest="max_rounds", type=int, default=3, help="??????")
    args = parser.parse_args()

    root = Path(__file__).parent
    if args.plan_id:
        backlog_path = root / "backlog" / f"{args.plan_id}.json"
        backlog = read_json(backlog_path)
        tasks_with_path = [(t, backlog_path) for t in backlog.get("tasks", [])]
    else:
        backlog_map = _load_backlog_map(root)
        tasks_with_path = [(t, path) for path, tasks in backlog_map.items() for t in tasks]
        backlog = {"tasks": [t for t, _ in tasks_with_path]}

    task, backlog_path = pick_next_task(tasks_with_path, plan_filter=args.plan_id)
    if not task:
        from curriculum import suggest_next_task

        goal_path = root / "goal.txt"
        goal = goal_path.read_text(encoding="utf-8") if goal_path.exists() else "No goal"

        new_task = suggest_next_task(goal, backlog)
        if new_task:
            if args.plan_id:
                backlog_path = root / "backlog" / f"{args.plan_id}.json"
            else:
                backlog_path = root / "backlog" / "adhoc.json"
            backlog = read_json(backlog_path)
            backlog.setdefault("tasks", []).append(new_task)
            write_json(backlog_path, backlog)
            print(f"[CURRICULUM] appended {new_task['id']} -> retry pick")
            task, backlog_path = pick_next_task([(t, backlog_path) for t in backlog.get("tasks", [])], plan_filter=args.plan_id)

        if not task:
            print("[NOOP] No runnable tasks in backlog")
            return

    task_id = task["id"]
    task_title = task.get("title", "")
    plan_id = task.get("plan_id")

    task["status"] = "doing"
    write_json(backlog_path, backlog)

    run_id = time.strftime("run-%Y%m%d-%H%M%S")
    if plan_id:
        exec_dir = root / "artifacts" / "executions" / plan_id
        exec_dir.mkdir(parents=True, exist_ok=True)
        run_dir = exec_dir / "runs" / run_id
    else:
        run_dir = root / "artifacts" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    workspace_path = args.workspace
    if isinstance(task.get("workspace"), dict) and task["workspace"].get("path"):
        workspace_path = task["workspace"]["path"]
    workspace_path = str(Path(workspace_path).resolve()) if workspace_path else None

    policy, policy_source, profile = load_policy(root, workspace_path)
    write_json(run_dir / "policy.json", policy)
    if profile:
        print(f"[PROFILE] workspace_id={profile.get('workspace_id')} fingerprint={profile.get('fingerprint')}")

    meta = {
        "run_id": run_id,
        "task_id": task_id,
        "plan_id": plan_id,
        "ts": time.time(),
        "workspace_path": workspace_path,
        "policy_source": policy_source,
        "workspace_id": policy.get("workspace_id"),
        "fingerprint": policy.get("fingerprint"),
    }
    write_json(run_dir / "meta.json", meta)
    append_jsonl(run_dir / "events.jsonl", {"type": "run_init", "run_id": run_id, "task_id": task_id, "plan_id": plan_id, "workspace": workspace_path, "ts": time.time()})

    step_id = "step-01"
    passed = False
    final_reasons = []
    max_rounds = max(args.max_rounds, 1)

    for round_id in range(max_rounds):
        mode = "good"
        round_dir = run_dir / "steps" / step_id / f"round-{round_id}"
        append_jsonl(
            run_dir / "events.jsonl",
            {"type": "step_round_start", "task_id": task_id, "plan_id": plan_id, "step": step_id, "round": round_id, "mode": mode, "ts": time.time()},
        )

        cmd = ["python", "scripts/subagent_shim.py", str(run_dir), task_id, step_id, str(round_id), mode]
        if workspace_path:
            cmd.extend(["--workspace", workspace_path])
        subprocess.check_call(cmd, cwd=str(root))

        passed, reasons = verify_task(run_dir, task_id, workspace_path=Path(workspace_path) if workspace_path else None)
        final_reasons = reasons

        write_json(
            round_dir / "verification.json",
            {"passed": passed, "reasons": reasons},
        )

        append_jsonl(
            run_dir / "events.jsonl",
            {"type": "step_round_verified", "task_id": task_id, "plan_id": plan_id, "step": step_id, "round": round_id, "passed": passed, "ts": time.time()},
        )

        if passed:
            break

        if round_id < max_rounds - 1:
            stdout_txt = ""
            stdout_path = round_dir / "stdout.txt"
            if stdout_path.exists():
                try:
                    stdout_txt = stdout_path.read_text(encoding="utf-8", errors="replace")[:1000]
                except Exception:
                    stdout_txt = ""
            validation_reasons = []
            shape_path = round_dir / "shape_response.json"
            if shape_path.exists():
                try:
                    shape = json.loads(shape_path.read_text(encoding="utf-8"))
                    validation_reasons = shape.get("validation_reasons", [])
                except Exception:
                    validation_reasons = []
            write_json(
                round_dir / "rework_request.json",
                {
                    "why_failed": reasons,
                    "validation_reasons": validation_reasons,
                    "prev_stdout": stdout_txt,
                    "next_round_should_do": "Fix outputs so acceptance_criteria pass.",
                    "workspace": workspace_path,
                    "round": round_id,
                },
            )

    task_checks = task.get("checks", []) if isinstance(task.get("checks"), list) else []
    policy_checks = policy.get("checks", []) if isinstance(policy, dict) else []
    effective_checks = task_checks or policy_checks
    write_verification_report(run_dir, task_id, plan_id, workspace_path, passed, final_reasons, effective_checks)

    index_lines = [
        f"# Run {run_id}",
        f"- Task: {task_id} {task_title}",
        "",
        "## Evidence",
        "- meta.json",
        "- events.jsonl",
        "- policy.json",
        "- verification_report.md",
        "- outputs/",
        f"- steps/{step_id}/round-0/",
        f"- steps/{step_id}/round-1/",
    ]
    (run_dir / "index.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")

    append_jsonl(run_dir / "events.jsonl", {"type": "run_done", "run_id": run_id, "task_id": task_id, "plan_id": plan_id, "passed": passed, "ts": time.time()})

    backlog = read_json(backlog_path)
    for t in backlog.get("tasks", []):
        if t.get("id") == task_id:
            t["status"] = "done" if passed else "failed"
            t["last_run"] = run_id
            t["last_reasons"] = final_reasons
            if plan_id:
                t["last_plan"] = plan_id
            break
    write_json(backlog_path, backlog)

    print(f"[DONE] task={task_id} passed={passed} run={run_dir}")
    if not passed and workspace_path and should_propose_on_failure(root, Path(workspace_path), threshold=2):
        propose_soft(root, Path(workspace_path), reason="repeated_failures")


if __name__ == "__main__":
    main()
