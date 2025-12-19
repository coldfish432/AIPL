import argparse
import json
import subprocess
import time
from pathlib import Path


def read_json(path: Path) -> dict:
    # 读取 JSON，默认返回空结构
    if not path.exists():
        return {"tasks": []}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj) -> None:
    # 写出 JSON 并确保父目录存在
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def run_codex_plan(prompt: str, root_dir: Path) -> str:
    """
    调用 Codex 生成计划，输出符合 plan.schema.json 的 JSON 字符串。
    """
    schema_path = root_dir / "schemas" / "plan.schema.json"
    cmd = [
        "codex",
        "exec",
        "--full-auto",
        "--sandbox",
        "workspace-write",
        "-C",
        str(root_dir),
        "--skip-git-repo-check",
        "--output-schema",
        str(schema_path),
        "--color",
        "never",
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
    # 判断是否还有该计划的待办任务
    for t in backlog.get("tasks", []):
        if t.get("plan_id") == plan_id and t.get("status") == "todo":
            return True
    return False


def has_runnable(backlog: dict, plan_id: str) -> bool:
    """
    判断计划内是否存在可执行的任务（todo 且依赖均已 done）。
    避免 controller 在无可执行任务时反复 NOOP 而导致无限循环。
    """
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


def main():
    root = Path(__file__).parent
    backlog_path = root / "backlog.json"
    goal_path = root / "goal.txt"

    parser = argparse.ArgumentParser(description="将自然语言任务交给 Codex 拆解并执行。")
    parser.add_argument("--task", required=True, help="要完成的长任务描述")
    parser.add_argument("--goal", help="可选的目标描述，未提供则读取 goal.txt")
    parser.add_argument("--plan-id", help="指定 plan_id，缺省自动生成")
    parser.add_argument("--max-tasks", type=int, default=8, help="拆解的最大子任务数（用于提示词约束）")
    parser.add_argument("--no-run", action="store_true", help="只生成计划与 backlog，不立即执行")
    parser.add_argument("--cleanup", action="store_true", help="计划完成/停止后自动清理该 plan 的 backlog 任务，并写回 plan 文件记录状态")
    args = parser.parse_args()

    plan_id = args.plan_id or time.strftime("plan-%Y%m%d-%H%M%S")
    goal_text = args.goal or (goal_path.read_text(encoding="utf-8") if goal_path.exists() else "")
    user_task = args.task.strip()

    backlog = read_json(backlog_path)

    # 构造提示词：要求输出拓扑序的细粒度子任务
    tmpl = (root / "prompts" / "plan.txt").read_text(encoding="utf-8")
    prompt = tmpl.format(
        plan_id=plan_id,
        max_tasks=args.max_tasks,
        task_text=user_task,
        goal_text=goal_text,
    )

    raw_plan = run_codex_plan(prompt.strip(), root)
    plan_obj = json.loads(raw_plan)

    # 持久化计划
    plan_dir = root / "artifacts" / "plans"
    plan_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        plan_dir / f"{plan_id}.json",
        {
            "plan_id": plan_id,
            "input_task": user_task,
            "goal": goal_text,
            "prompt": prompt,
            "raw_plan": plan_obj,
            "created_ts": time.time(),
        },
    )
    # 记录拆解出的子任务列表（JSONL，便于浏览与审计）
    tasks_record = plan_dir / f"{plan_id}.tasks.jsonl"
    with tasks_record.open("w", encoding="utf-8") as f:
        for t in plan_obj.get("tasks", []):
            rec = {"plan_id": plan_id, **t}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # 追加任务到 backlog
    existing_ids = {t["id"] for t in backlog.get("tasks", [])}
    for idx, t in enumerate(plan_obj.get("tasks", []), 1):
        task_id = t.get("id") or f"{plan_id}-T{idx:02d}"
        if task_id in existing_ids:
            task_id = f"{task_id}_{int(time.time())}"
        existing_ids.add(task_id)

        backlog.setdefault("tasks", []).append(
            {
                "id": task_id,
                "title": t.get("title", f"Task {idx}"),
                "type": "time_for_certainty",
                "priority": t.get("priority", 50),
                "estimated_minutes": t.get("estimated_minutes", 30),
                "status": "todo",
                "dependencies": t.get("dependencies", []),
                "acceptance_criteria": t.get("acceptance_criteria", []),
                "plan_id": plan_id,
                "created_from_goal": goal_text,
                "created_ts": time.time(),
            }
        )

    write_json(backlog_path, backlog)
    print(f"[PLAN] added {len(plan_obj.get('tasks', []))} tasks to backlog under plan_id={plan_id}")

    if args.no_run:
        print("[PLAN] no-run flag set, skipping execution")
        if args.cleanup:
            print("[CLEANUP] skip cleanup when --no-run is set (nothing executed yet)")
        return

    # 循环调用 controller 逐个执行计划内任务
    while True:
        backlog = read_json(backlog_path)
        if not has_todo(backlog, plan_id):
            print(f"[PLAN DONE] no todo tasks for plan_id={plan_id}")
            break
        if not has_runnable(backlog, plan_id):
            print(f"[PLAN STOP] todo tasks remain but no runnable tasks for plan_id={plan_id} (依赖未满足或前置失败)")
            break
        print(f"[RUN] invoking controller for plan_id={plan_id}")
        subprocess.check_call(["python", "controller.py", "--plan-id", plan_id], cwd=root)

    if args.cleanup:
        backlog = read_json(backlog_path)
        keep, removed = [], []
        for t in backlog.get("tasks", []):
            if t.get("plan_id") == plan_id:
                removed.append(t)
            else:
                keep.append(t)
        backlog["tasks"] = keep
        write_json(backlog_path, backlog)

        # 将清理出的任务状态写回 plan 文件，取代单独的 archive
        plan_file = root / "artifacts" / "plans" / f"{plan_id}.json"
        if plan_file.exists():
            plan_data = read_json(plan_file)
            plan_data["last_cleanup_ts"] = time.time()
            plan_data["cleanup_snapshot"] = removed
            write_json(plan_file, plan_data)

        print(f"[CLEANUP] removed {len(removed)} tasks for plan_id={plan_id} (recorded in plan file)")


if __name__ == "__main__":
    main()
