import argparse
import json
import os
import subprocess
import time
import uuid
import hashlib
from pathlib import Path


def envelope(ok: bool, data=None, error=None):
    return {
        "ok": ok,
        "ts": int(time.time()),
        "trace_id": f"trc_{uuid.uuid4().hex[:12]}",
        "data": data,
        "error": error,
    }


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def find_latest_run(exec_dir: Path) -> Path | None:
    runs_dir = exec_dir / "runs"
    if not runs_dir.exists():
        return None
    runs = [p for p in runs_dir.iterdir() if p.is_dir()]
    if not runs:
        return None
    runs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return runs[0]


def resolve_run_dir(root: Path, plan_id: str | None, run_id: str | None) -> Path | None:
    if plan_id:
        exec_dir = root / "artifacts" / "executions" / plan_id
        if run_id:
            cand = exec_dir / "runs" / run_id
            return cand if cand.exists() else None
        return find_latest_run(exec_dir)
    if run_id:
        # fallback legacy location
        cand = root / "artifacts" / "runs" / run_id
        return cand if cand.exists() else None
    return None


def read_status(run_dir: Path) -> dict:
    events_path = run_dir / "events.jsonl"
    status = "running"
    passed = None
    if (run_dir / "cancel.flag").exists():
        status = "canceled"
    if events_path.exists():
        try:
            lines = events_path.read_text(encoding="utf-8").splitlines()
            for line in reversed(lines):
                if '"type": "run_done"' in line:
                    evt = json.loads(line)
                    passed = evt.get("passed")
                    status = evt.get("status") or ("done" if passed else "failed")
                    break
        except Exception:
            pass
    meta = {}
    meta_path = run_dir / "meta.json"
    if meta_path.exists():
        meta = read_json(meta_path)
    # latest round
    round_id = None
    reasons = []
    steps_dir = run_dir / "steps" / "step-01"
    if steps_dir.exists():
        rounds = [p for p in steps_dir.iterdir() if p.is_dir() and p.name.startswith("round-")]
        if rounds:
            rounds.sort(key=lambda p: p.name)
            latest = rounds[-1]
            round_id = latest.name.replace("round-", "")
            ver_path = latest / "verification.json"
            if ver_path.exists():
                try:
                    ver = read_json(ver_path)
                    reasons = ver.get("reasons", [])
                except Exception:
                    reasons = []
    return {
        "run_id": run_dir.name,
        "status": status,
        "current_task_id": meta.get("task_id"),
        "round": round_id,
        "passed": passed,
        "last_reasons": reasons,
    }





def list_runs(exec_dir: Path) -> list[dict]:
    runs_dir = exec_dir / "runs"
    if not runs_dir.exists():
        return []
    runs = []
    for p in runs_dir.iterdir():
        if not p.is_dir():
            continue
        runs.append({
            "run_id": p.name,
            "run_dir": str(p),
            "outputs": str(p / "outputs"),
            "report_path": str(p / "verification_report.md"),
        })
    runs.sort(key=lambda x: x["run_id"])
    return runs


def list_artifacts(run_dir: Path) -> list[dict]:
    items = []
    for root, _, files in os.walk(run_dir):
        for name in files:
            p = Path(root) / name
            rel = p.relative_to(run_dir).as_posix()
            stat = p.stat()
            h = hashlib.sha256()
            with p.open("rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            items.append({
                "path": rel,
                "size": stat.st_size,
                "sha256": h.hexdigest(),
                "updated_at": int(stat.st_mtime),
            })
    return items


def cmd_plan(args, root: Path):
    plan_id = args.plan_id or time.strftime("plan-%Y%m%d-%H%M%S")
    cmd = ["python", "plan_and_run.py", "--task", args.goal, "--plan-id", plan_id, "--no-run"]
    if args.workspace:
        cmd.extend(["--workspace", args.workspace])
    subprocess.check_call(cmd, cwd=root)
    exec_dir = root / "artifacts" / "executions" / plan_id
    plan_path = exec_dir / "plan.json"
    tasks_count = 0
    if plan_path.exists():
        plan = read_json(plan_path)
        tasks = plan.get("raw_plan", {}).get("tasks", [])
        tasks_count = len(tasks)
    data = {
        "plan_id": plan_id,
        "tasks_count": tasks_count,
        "backlog_written": True,
        "artifacts_root": str(exec_dir),
    }
    print(json.dumps(envelope(True, data=data), ensure_ascii=False))


def cmd_run(args, root: Path):
    plan_id = args.plan_id or time.strftime("plan-%Y%m%d-%H%M%S")
    cmd = ["python", "plan_and_run.py", "--task", args.goal, "--plan-id", plan_id]
    if args.workspace:
        cmd.extend(["--workspace", args.workspace])
    subprocess.check_call(cmd, cwd=root)
    exec_dir = root / "artifacts" / "executions" / plan_id
    run_dir = find_latest_run(exec_dir)
    status = read_status(run_dir) if run_dir else {"status": "unknown"}
    data = {
        "run_id": run_dir.name if run_dir else None,
        "plan_id": plan_id,
        "status": status.get("status"),
    }
    print(json.dumps(envelope(True, data=data), ensure_ascii=False))


def cmd_status(args, root: Path):
    run_dir = resolve_run_dir(root, args.plan_id, args.run_id)
    if not run_dir:
        print(json.dumps(envelope(False, error="run not found"), ensure_ascii=False))
        return
    print(json.dumps(envelope(True, data=read_status(run_dir)), ensure_ascii=False))


def cmd_events(args, root: Path):
    run_dir = resolve_run_dir(root, args.plan_id, args.run_id)
    if not run_dir:
        print(json.dumps(envelope(False, error="run not found"), ensure_ascii=False))
        return
    events_path = run_dir / "events.jsonl"
    if not events_path.exists():
        print(json.dumps(envelope(True, data={"events": [], "cursor": args.cursor, "next_cursor": args.cursor}), ensure_ascii=False))
        return
    lines = events_path.read_text(encoding="utf-8").splitlines()
    start = max(args.cursor - 1, 0)
    end = min(start + args.limit, len(lines))
    events = []
    for idx, line in enumerate(lines[start:end], start=start):
        if not line.strip():
            continue
        evt = json.loads(line)
        evt["event_id"] = idx + 1
        events.append(evt)
    data = {
        "run_id": run_dir.name,
        "cursor": start + 1,
        "next_cursor": end + 1,
        "cursor_type": "event_id",
        "total": len(lines),
        "events": events,
    }
    print(json.dumps(envelope(True, data=data), ensure_ascii=False))


def cmd_artifacts(args, root: Path):
    run_dir = resolve_run_dir(root, args.plan_id, args.run_id)
    if not run_dir and not args.plan_id:
        print(json.dumps(envelope(False, error="run not found"), ensure_ascii=False))
        return
    if args.plan_id:
        exec_dir = root / "artifacts" / "executions" / args.plan_id
        data = {
            "plan_id": args.plan_id,
            "artifacts_root": str(exec_dir),
            "runs": list_runs(exec_dir),
        }
        if run_dir:
            data["run_id"] = run_dir.name
            data["items"] = list_artifacts(run_dir)
        print(json.dumps(envelope(True, data=data), ensure_ascii=False))
        return
    data = {
        "run_id": run_dir.name,
        "items": list_artifacts(run_dir),
    }
    print(json.dumps(envelope(True, data=data), ensure_ascii=False))



def cmd_cancel(args, root: Path):
    run_dir = resolve_run_dir(root, args.plan_id, args.run_id)
    if not run_dir:
        print(json.dumps(envelope(False, error="run not found"), ensure_ascii=False))
        return
    flag = run_dir / "cancel.flag"
    flag.write_text(str(int(time.time())), encoding="utf-8")
    data = {"run_id": run_dir.name, "status": "canceled"}
    print(json.dumps(envelope(True, data=data), ensure_ascii=False))


def main():
    root = Path(__file__).parent
    parser = argparse.ArgumentParser(description="AIPL Engine CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_plan = sub.add_parser("plan")
    p_plan.add_argument("--goal", required=True)
    p_plan.add_argument("--plan-id")
    p_plan.add_argument("--workspace")
    p_plan.set_defaults(func=cmd_plan)

    p_run = sub.add_parser("run")
    p_run.add_argument("--goal", required=True)
    p_run.add_argument("--plan-id")
    p_run.add_argument("--workspace")
    p_run.set_defaults(func=cmd_run)

    p_status = sub.add_parser("status")
    p_status.add_argument("--plan-id")
    p_status.add_argument("--run-id")
    p_status.set_defaults(func=cmd_status)

    p_events = sub.add_parser("events")
    p_events.add_argument("--plan-id")
    p_events.add_argument("--run-id")
    p_events.add_argument("--cursor", type=int, default=0)
    p_events.add_argument("--limit", type=int, default=200)
    p_events.set_defaults(func=cmd_events)

    p_art = sub.add_parser("artifacts")
    p_art.add_argument("--plan-id")
    p_art.add_argument("--run-id")
    p_art.set_defaults(func=cmd_artifacts)

    p_cancel = sub.add_parser("cancel")
    p_cancel.add_argument("--plan-id")
    p_cancel.add_argument("--run-id")
    p_cancel.set_defaults(func=cmd_cancel)

    args = parser.parse_args()
    args.func(args, root)


if __name__ == "__main__":
    main()
