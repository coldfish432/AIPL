import argparse
import time
from pathlib import Path

from infra.io_utils import read_json, write_json
from workspace_utils import find_plan_workspace, get_backlog_dir, get_plan_dir


# 将被清理的任务状态写回对应 plan 文件
def update_plan_status(root: Path, plan_id: str, removed: list[dict]) -> None:
    """将被清理的任务状态写回对应 plan 文件。"""
    workspace = find_plan_workspace(root, plan_id)
    plan_path = get_plan_dir(root, workspace, plan_id) / "plan.json"
    if not plan_path.exists():
        return
    plan = read_json(plan_path)
    plan["last_cleanup_ts"] = time.time()
    plan["cleanup_snapshot"] = removed
    write_json(plan_path, plan)


# 主入口，解析命令行参数，读取文件内容
def main():
    parser = argparse.ArgumentParser(description="清理 backlog 中指定 plan_id 的任务，并将状态写回 plan 文件。")
    parser.add_argument("--root", required=True, help="repo root path")
    parser.add_argument("--plan-id", required=True, help="要清理的 plan_id")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    workspace_path = find_plan_workspace(root, args.plan_id)
    backlog_dir = get_backlog_dir(root, workspace_path)
    backlog_dir.mkdir(parents=True, exist_ok=True)
    backlog_path = backlog_dir / f"{args.plan_id}.json"

    backlog = read_json(backlog_path, default={"tasks": []})
    tasks = backlog.get("tasks", [])

    keep = []
    removed = []
    for t in tasks:
        if t.get("plan_id") == args.plan_id:
            removed.append(t)
        else:
            keep.append(t)

    backlog["tasks"] = keep
    write_json(backlog_path, backlog)

    if removed:
        update_plan_status(root, args.plan_id, removed)

    print(f"[CLEAN] plan_id={args.plan_id}, removed={len(removed)}, kept={len(keep)}")
    if removed:
        plan_file = get_plan_dir(root, workspace_path, args.plan_id) / "plan.json"
        print(f"[PLAN UPDATED] {plan_file}")


if __name__ == "__main__":
    main()
