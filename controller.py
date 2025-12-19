import argparse
import json
import subprocess
import time
from pathlib import Path

from verifier import verify_task


def read_json(path: Path):
    # 读取 UTF-8 JSON 文件并反序列化
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj):
    # 序列化对象为 JSON 文件，若目录缺失则创建
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def append_jsonl(path: Path, obj):
    # 以 JSONL 方式追加一行记录
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def pick_next_task(backlog: dict, plan_filter: str | None = None):
    # 选取首个可执行的 time_for_certainty 任务
    tasks = backlog.get("tasks", [])
    if plan_filter:
        done = {t["id"] for t in tasks if t.get("status") == "done" and t.get("plan_id") == plan_filter}
    else:
        done = {t["id"] for t in tasks if t.get("status") == "done"}

    candidates = []
    for t in tasks:
        if plan_filter and t.get("plan_id") != plan_filter:
            continue
        if t.get("status") != "todo":
            continue
        deps = t.get("dependencies", [])
        if any(dep not in done for dep in deps):
            continue
        if t.get("type") != "time_for_certainty":
            continue
        candidates.append(t)

    if not candidates:
        return None

    candidates.sort(key=lambda x: x.get("priority", 0), reverse=True)
    return candidates[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan-id", dest="plan_id", help="仅执行匹配该 plan_id 的任务")
    parser.add_argument("--workspace", dest="workspace", help="目标 workspace 路径，若任务定义了 workspace 则优先用任务配置")
    parser.add_argument("--max-rounds", dest="max_rounds", type=int, default=3, help="最多重试轮次")
    args = parser.parse_args()

    root = Path(__file__).parent
    backlog_path = root / "backlog.json"
    backlog = read_json(backlog_path)

    task = pick_next_task(backlog, plan_filter=args.plan_id)
    if not task:
        # 自动课程：尝试追加下一条任务
        from curriculum import suggest_next_task

        goal_path = root / "goal.txt"
        goal = goal_path.read_text(encoding="utf-8") if goal_path.exists() else "No goal"

        new_task = suggest_next_task(goal, backlog)
        if new_task:
            backlog.setdefault("tasks", []).append(new_task)
            write_json(backlog_path, backlog)
            print(f"[CURRICULUM] appended {new_task['id']} -> retry pick")
            task = pick_next_task(backlog, plan_filter=args.plan_id)

        if not task:
            print("[NOOP] No runnable tasks in backlog.json")
            return

    task_id = task["id"]
    task_title = task.get("title", "")
    plan_id = task.get("plan_id")

    # 标记为执行中
    task["status"] = "doing"
    write_json(backlog_path, backlog)

    # 创建运行目录
    run_id = time.strftime("run-%Y%m%d-%H%M%S")
    run_dir = root / "artifacts" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # 解析 workspace
    workspace_path = args.workspace
    if isinstance(task.get("workspace"), dict) and task["workspace"].get("path"):
        workspace_path = task["workspace"]["path"]
    workspace_path = str(Path(workspace_path).resolve()) if workspace_path else None

    # 写入元信息与启动事件
    meta = {"run_id": run_id, "task_id": task_id, "plan_id": plan_id, "ts": time.time(), "workspace_path": workspace_path}
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
            {"type": "step_round_start", "task_id": task_id, "plan_id": plan_id, "step": step_id, "round": round_id, "mode": mode, "ts": time.time()}
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
            write_json(
                round_dir / "rework_request.json",
                {
                    "why_failed": reasons,
                    "prev_stdout": stdout_txt,
                    "next_round_should_do": "Fix outputs so acceptance_criteria pass.",
                    "workspace": workspace_path,
                    "round": round_id,
                },
            )

    index_lines = [
        f"# Run {run_id}",
        f"- Task: {task_id} {task_title}",
        "",
        "## Evidence",
        "- meta.json",
        "- events.jsonl",
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


if __name__ == "__main__":
    main()