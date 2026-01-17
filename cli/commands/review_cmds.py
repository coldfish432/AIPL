from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from sqlite_mirror import update_run_status
from cli.utils import envelope, resolve_run_dir
from infra.io_utils import append_jsonl, read_json, write_json
from services.patchset_service import apply_patchset, build_patchset
from services.stage_workspace import StageWorkspaceManager
from services.verifier import VerifierService


def cmd_cancel(args, root: Path):
    run_dir = resolve_run_dir(root, args.plan_id, args.run_id)
    if not run_dir:
        print(json.dumps(envelope(False, error="run not found"), ensure_ascii=False))
        return

    meta_path = run_dir / "meta.json"
    meta = read_json(meta_path, default={})
    current_status = meta.get("status", "")
    plan_id = meta.get("plan_id") or args.plan_id

    if current_status in ("done", "failed", "canceled", "discarded"):
        print(
            json.dumps(
                envelope(
                    True,
                    data={
                        "run_id": run_dir.name,
                        "plan_id": plan_id,
                        "status": current_status,
                        "message": f"run already in terminal state: {current_status}",
                    },
                ),
                ensure_ascii=False,
            )
        )
        return

    flag = run_dir / "cancel.flag"
    flag.write_text(str(int(time.time())), encoding="utf-8")

    pause_flag = run_dir / "pause.flag"
    if pause_flag.exists():
        pause_flag.unlink()

    meta["status"] = "canceled"
    meta["canceled_at"] = time.time()
    write_json(meta_path, meta)

    append_jsonl(
        run_dir / "events.jsonl",
        {"type": "run_canceled", "run_id": run_dir.name, "plan_id": plan_id, "ts": time.time()},
    )

    data = {
        "run_id": run_dir.name,
        "plan_id": plan_id,
        "status": "canceled",
        "workspace_main_root": meta.get("workspace_main_root", ""),
    }
    res = envelope(True, data=data)
    update_run_status(root, run_dir.name, "canceled")
    print(json.dumps(res, ensure_ascii=False))


def cmd_pause(args, root: Path):
    run_dir = resolve_run_dir(root, args.plan_id, args.run_id)
    if not run_dir:
        print(json.dumps(envelope(False, error="run not found"), ensure_ascii=False))
        return

    meta_path = run_dir / "meta.json"
    meta = read_json(meta_path, default={})
    current_status = meta.get("status", "")
    plan_id = meta.get("plan_id") or args.plan_id

    if current_status not in ("running", "doing"):
        print(json.dumps(envelope(False, error=f"cannot pause: current status is '{current_status}'"), ensure_ascii=False))
        return

    pause_flag = run_dir / "pause.flag"
    pause_flag.write_text(str(int(time.time())), encoding="utf-8")

    meta["status"] = "paused"
    meta["paused_at"] = time.time()
    write_json(meta_path, meta)

    append_jsonl(
        run_dir / "events.jsonl",
        {"type": "run_paused", "run_id": run_dir.name, "plan_id": plan_id, "ts": time.time()},
    )

    data = {"run_id": run_dir.name, "plan_id": plan_id, "status": "paused"}
    res = envelope(True, data=data)
    update_run_status(root, run_dir.name, "paused")
    print(json.dumps(res, ensure_ascii=False))


def cmd_resume(args, root: Path):
    run_dir = resolve_run_dir(root, args.plan_id, args.run_id)
    if not run_dir:
        print(json.dumps(envelope(False, error="run not found"), ensure_ascii=False))
        return

    meta_path = run_dir / "meta.json"
    meta = read_json(meta_path, default={})
    current_status = meta.get("status", "")
    plan_id = meta.get("plan_id") or args.plan_id

    if current_status != "paused":
        print(json.dumps(envelope(False, error=f"cannot resume: current status is '{current_status}'"), ensure_ascii=False))
        return

    pause_flag = run_dir / "pause.flag"
    if pause_flag.exists():
        pause_flag.unlink()

    meta["status"] = "running"
    meta["resumed_at"] = time.time()
    write_json(meta_path, meta)

    append_jsonl(
        run_dir / "events.jsonl",
        {"type": "run_resumed", "run_id": run_dir.name, "plan_id": plan_id, "ts": time.time()},
    )

    data = {"run_id": run_dir.name, "plan_id": plan_id, "status": "running"}
    res = envelope(True, data=data)
    update_run_status(root, run_dir.name, "running")
    print(json.dumps(res, ensure_ascii=False))


def cmd_cancel_plan_runs(args, root: Path):
    if not args.plan_id:
        print(json.dumps(envelope(False, error="plan_id is required"), ensure_ascii=False))
        return

    exec_dir = root / "artifacts" / "executions" / args.plan_id
    runs_dir = exec_dir / "runs"

    if not runs_dir.exists():
        print(json.dumps(envelope(True, data={"plan_id": args.plan_id, "canceled": 0, "canceled_runs": []}), ensure_ascii=False))
        return

    canceled_runs: list[str] = []

    for run_dir in runs_dir.iterdir():
        if not run_dir.is_dir():
            continue

        meta_path = run_dir / "meta.json"
        meta = read_json(meta_path, default={})
        status = meta.get("status", "")

        if status in ("running", "doing", "paused", "starting"):
            run_id = run_dir.name

            cancel_flag = run_dir / "cancel.flag"
            cancel_flag.write_text(str(int(time.time())), encoding="utf-8")

            pause_flag = run_dir / "pause.flag"
            if pause_flag.exists():
                pause_flag.unlink()

            meta["status"] = "canceled"
            meta["canceled_at"] = time.time()
            write_json(meta_path, meta)

            append_jsonl(
                run_dir / "events.jsonl",
                {
                    "type": "run_canceled",
                    "run_id": run_id,
                    "plan_id": args.plan_id,
                    "reason": "plan_canceled",
                    "ts": time.time(),
                },
            )

            update_run_status(root, run_id, "canceled")

            canceled_runs.append(run_id)

    print(
        json.dumps(
            envelope(
                True,
                data={
                    "plan_id": args.plan_id,
                    "canceled": len(canceled_runs),
                    "canceled_runs": canceled_runs,
                },
            ),
            ensure_ascii=False,
        )
    )


def cmd_rework(args, root: Path):
    run_dir = resolve_run_dir(root, args.plan_id, args.run_id)
    if not run_dir:
        print(json.dumps(envelope(False, error="run not found"), ensure_ascii=False))
        return
    meta = read_json(run_dir / "meta.json", default={})
    stage_root = meta.get("workspace_stage_root")
    main_root = meta.get("workspace_main_root")
    task_id = meta.get("task_id")
    if not stage_root or not main_root or not task_id:
        print(json.dumps(envelope(False, error="missing stage/main/task"), ensure_ascii=False))
        return
    step_id = args.step_id or "step-01"
    steps_dir = run_dir / "steps" / step_id
    steps_dir.mkdir(parents=True, exist_ok=True)
    rounds = [p for p in steps_dir.iterdir() if p.is_dir() and p.name.startswith("round-")]
    next_round = 0
    if rounds:
        try:
            next_round = max(int(p.name.replace("round-", "")) for p in rounds) + 1
        except Exception:
            next_round = len(rounds)
    round_dir = steps_dir / f"round-{next_round}"
    round_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "step_id": step_id,
        "feedback": args.feedback or "",
        "scope": args.scope,
        "ts": time.time(),
    }
    write_json(round_dir / "rework_request.json", payload)
    append_jsonl(run_dir / "events.jsonl", {"type": "rework_start", "run_id": meta.get("run_id"), "step": step_id, "round": next_round, "ts": time.time()})

    cancel_flag = run_dir / "cancel.flag"
    if cancel_flag.exists():
        cancel_flag.unlink()

    # ensure the run transitions to running before the child process starts
    meta.update({"status": "running", "updated_at": time.time()})
    write_json(run_dir / "meta.json", meta)
    update_run_status(root, run_dir.name, "running")
    cmd = ["python", "scripts/subagent_shim.py", "--root", str(root), str(run_dir), task_id, step_id, str(next_round), "good", "--workspace", stage_root, "--workspace-main", main_root]
    subprocess.check_call(cmd, cwd=root)
    passed, reasons = VerifierService(root).verify_task(run_dir, task_id, workspace_path=Path(stage_root))
    write_json(round_dir / "verification.json", {"passed": passed, "reasons": reasons})
    append_jsonl(run_dir / "events.jsonl", {"type": "rework_done", "run_id": meta.get("run_id"), "step": step_id, "round": next_round, "passed": passed, "ts": time.time()})
    append_jsonl(run_dir / "events.jsonl", {"type": "step_round_verified", "run_id": meta.get("run_id"), "step": step_id, "round": next_round, "passed": passed, "ts": time.time()})
    if passed:
        patchset = build_patchset(Path(stage_root), Path(main_root), run_dir)
        changed_count = len(patchset.changed_files)
        patch_rel = patchset.patchset_path.relative_to(run_dir).as_posix()
        changed_rel = patchset.changed_files_path.relative_to(run_dir).as_posix()
        meta.update({
            "patchset_path": patch_rel,
            "changed_files_path": changed_rel,
            "changed_files_count": changed_count,
            "status": "awaiting_review",
            "updated_at": time.time(),
        })
        write_json(run_dir / "meta.json", meta)
        append_jsonl(run_dir / "events.jsonl", {"type": "patchset_ready", "run_id": meta.get("run_id"), "changed_files": changed_count, "patchset_path": patch_rel, "ts": time.time()})
        append_jsonl(run_dir / "events.jsonl", {"type": "awaiting_review", "run_id": meta.get("run_id"), "ts": time.time()})
        res = envelope(True, data={"run_id": meta.get("run_id"), "plan_id": meta.get("plan_id"), "status": "awaiting_review"})
    else:
        meta.update({"status": "failed", "updated_at": time.time()})
        write_json(run_dir / "meta.json", meta)
        append_jsonl(run_dir / "events.jsonl", {"type": "run_done", "run_id": meta.get("run_id"), "status": "failed", "passed": False, "ts": time.time()})
        res = envelope(False, error="rework failed")
    update_run_status(root, run_dir.name, meta.get("status", "unknown"))
    print(json.dumps(res, ensure_ascii=False))


def cmd_apply(args, root: Path):
    run_dir = resolve_run_dir(root, args.plan_id, args.run_id)
    if not run_dir:
        print(json.dumps(envelope(False, error="run not found"), ensure_ascii=False))
        return
    meta = read_json(run_dir / "meta.json", default={})
    if meta.get("status") != "awaiting_review":
        print(json.dumps(envelope(False, error="run not awaiting_review"), ensure_ascii=False))
        return
    stage_root = meta.get("workspace_stage_root")
    main_root = meta.get("workspace_main_root")
    if not stage_root or not main_root:
        print(json.dumps(envelope(False, error="missing stage/main root"), ensure_ascii=False))
        return
    changed_path = meta.get("changed_files_path")
    if changed_path:
        changed_path = Path(changed_path)
        if not changed_path.is_absolute():
            changed_path = run_dir / changed_path
    else:
        changed_path = run_dir / "patchset" / "changed_files.json"
    changed_payload = read_json(Path(changed_path), default={})
    changed_files = changed_payload.get("changed_files", []) if isinstance(changed_payload, dict) else []
    append_event = {"type": "apply_start", "run_id": meta.get("run_id"), "ts": time.time()}
    append_jsonl(run_dir / "events.jsonl", append_event)
    results = apply_patchset(Path(stage_root), Path(main_root), changed_files)
    StageWorkspaceManager(root).remove_stage(Path(stage_root), Path(main_root))
    meta.update({"status": "done", "apply_results": results, "updated_at": time.time()})
    write_json(run_dir / "meta.json", meta)
    append_jsonl(run_dir / "events.jsonl", {"type": "apply_done", "run_id": meta.get("run_id"), "ts": time.time(), "status": "done"})
    append_jsonl(run_dir / "events.jsonl", {"type": "run_done", "run_id": meta.get("run_id"), "status": "done", "passed": True, "ts": time.time()})
    res = envelope(
        True,
        data={
            "run_id": meta.get("run_id"),
            "plan_id": meta.get("plan_id"),
            "status": "done",
            "apply_results": results,
            "workspace_main_root": meta.get("workspace_main_root"),
            "workspace_stage_root": meta.get("workspace_stage_root"),
        },
    )
    update_run_status(root, run_dir.name, meta.get("status", "unknown"))
    print(json.dumps(res, ensure_ascii=False))


def cmd_discard(args, root: Path):
    run_dir = resolve_run_dir(root, args.plan_id, args.run_id)
    if not run_dir:
        print(json.dumps(envelope(False, error="run not found"), ensure_ascii=False))
        return
    meta = read_json(run_dir / "meta.json", default={})
    stage_root = meta.get("workspace_stage_root")
    main_root = meta.get("workspace_main_root")
    if stage_root and main_root:
        StageWorkspaceManager(root).remove_stage(Path(stage_root), Path(main_root))
    meta.update({"status": "discarded", "updated_at": time.time()})
    write_json(run_dir / "meta.json", meta)
    append_jsonl(run_dir / "events.jsonl", {"type": "discard_done", "run_id": meta.get("run_id"), "status": "discarded", "ts": time.time()})
    append_jsonl(run_dir / "events.jsonl", {"type": "run_done", "run_id": meta.get("run_id"), "status": "discarded", "passed": False, "ts": time.time()})
    res = envelope(
        True,
        data={
            "run_id": meta.get("run_id"),
            "plan_id": meta.get("plan_id"),
            "status": "discarded",
            "workspace_main_root": meta.get("workspace_main_root"),
            "workspace_stage_root": meta.get("workspace_stage_root"),
        },
    )
    update_run_status(root, run_dir.name, meta.get("status", "unknown"))
    print(json.dumps(res, ensure_ascii=False))
