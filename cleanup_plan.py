import argparse
import json
import time
from pathlib import Path


def read_json(path: Path) -> dict:
    if not path.exists():
        return {"tasks": []}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def update_plan_status(root: Path, plan_id: str, removed: list[dict]) -> None:
    """将被清理的任务状态写回对应 plan 文件，避免单独的 archive.json。"""
    plan_path = root / "artifacts" / "plans" / f"{plan_id}.json"
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
    backlog_path = root / "backlog.json"

    backlog = read_json(backlog_path)
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
        print(f"[PLAN UPDATED] artifacts/plans/{args.plan_id}.json")


if __name__ == "__main__":
    main()
