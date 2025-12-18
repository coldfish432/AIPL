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
    # 以 JSONL 形式追加一行记录
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def pick_next_task(backlog: dict, plan_filter: str | None = None):
    # 从 backlog 中挑选首个可执行的 time_for_certainty 任务，可按 plan_id 过滤
    tasks = backlog.get("tasks", [])
    # 收集已完成任务用于依赖判定
    if plan_filter:
        done = {t["id"] for t in tasks if t.get("status") == "done" and t.get("plan_id") == plan_filter}
    else:
        done = {t["id"] for t in tasks if t.get("status") == "done"}

    candidates = []
    for t in tasks:
        if plan_filter and t.get("plan_id") != plan_filter:
            continue
        # 只考虑 todo 状态的任务
        if t.get("status") != "todo":
            continue
        deps = t.get("dependencies", [])
        # 若依赖未完成则跳过
        if any(dep not in done for dep in deps):
            continue
        # 仅处理 time_for_certainty 类型
        if t.get("type") != "time_for_certainty":
            continue
        candidates.append(t)

    if not candidates:
        return None

    # 按优先级降序取首个
    candidates.sort(key=lambda x: x.get("priority", 0), reverse=True)
    return candidates[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan-id", dest="plan_id", help="仅执行匹配该 plan_id 的任务")
    args = parser.parse_args()

    # 初始化路径与 backlog
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

    # 写入元信息与启动事件
    write_json(run_dir / "meta.json", {"run_id": run_id, "task_id": task_id, "plan_id": plan_id, "ts": time.time()})
    append_jsonl(run_dir / "events.jsonl", {"type": "run_init", "run_id": run_id, "task_id": task_id, "plan_id": plan_id, "ts": time.time()})

    step_id = "step-01"

    passed = False
    final_reasons = []

    # round-0 故意输出错误，round-1 正常输出（验证复盘流程）
    for round_id, mode in [(0, "bad"), (1, "good")]:
        append_jsonl(
            run_dir / "events.jsonl",
            {"type": "step_round_start", "task_id": task_id, "plan_id": plan_id, "step": step_id, "round": round_id, "mode": mode, "ts": time.time()}
        )

        # 调用子代理生成输出
        cmd = ["python", "scripts/subagent_shim.py", str(run_dir), task_id, step_id, str(round_id), mode]
        subprocess.check_call(cmd, cwd=str(root))

        # 调用验证器检查输出
        passed, reasons = verify_task(run_dir, task_id)
        final_reasons = reasons

        # 记录本轮验证结果
        write_json(
            run_dir / "steps" / step_id / f"round-{round_id}" / "verification.json",
            {"passed": passed, "reasons": reasons},
        )

        append_jsonl(
            run_dir / "events.jsonl",
            {"type": "step_round_verified", "task_id": task_id, "plan_id": plan_id, "step": step_id, "round": round_id, "passed": passed, "ts": time.time()},
        )

        if passed:
            break

        # 创建复盘请求
        write_json(
            run_dir / "steps" / step_id / f"round-{round_id}" / "rework_request.json",
            {"why_failed": reasons, "next_round_should_do": "Fix outputs so acceptance_criteria pass."},
        )

    # 输出可读性更好的索引文件
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

    # 将结果回写 backlog
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
