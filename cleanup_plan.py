import argparse
import time
from pathlib import Path

from infra.io_utils import read_json, write_json


def update_plan_status(root: Path, plan_id: str, removed: list[dict]) -> None:
    """将被清理的任务状态写回对应 plan 文件。"""
    plan_path = root / "artifacts" / "executions" / plan_id / "plan.json"
    if not plan_path.exists():
        return
    plan = read_json(plan_path)
    plan["last_cleanup_ts"] = time.time()
    plan["cleanup_snapshot"] = removed  # 记录被移除任务的完整状态
    write_json(plan_path, plan)


def main():
    parser = argparse.ArgumentParser(description="清理 backlog 中指定 plan_id 的任务，并将状态写回 plan 文件。")
    parser.add_argument("--plan-id", required=True, help="要清理的 plan_id")
    args = parser.parse_args()

    root = Path(__file__).parent
    backlog_path = root / "backlog" / f"{args.plan_id}.json"

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
        print(f"[PLAN UPDATED] artifacts/executions/{args.plan_id}/plan.json")


if __name__ == "__main__":
    main()
