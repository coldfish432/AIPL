from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from infra.io_utils import append_jsonl, read_json, write_json
from infra.path_guard import is_workspace_unsafe
from interfaces.protocols import ICodeGraphService, IProfileService, IVerifier
from services.patchset_service import build_patchset
from services.stage_workspace import StageWorkspaceManager
from state import append_state_events, transition_task

from .backlog import load_backlog_map_filtered
from .policy import is_high_risk, load_policy, merge_checks
from .reporting import extract_paths_from_checks, extract_paths_from_reasons, write_verification_report
from sqlite_mirror import mirror_run, update_run_status
from .task_picker import pick_next_task
from .workspace import auto_select_workspace
from workspace_utils import find_plan_workspace, get_backlog_dir, get_plan_dir

__all__ = ["TaskController"]


def _load_code_graph(root: Path, plan_id: str | None, code_graph_service: ICodeGraphService):
    if not plan_id:
        return None
    workspace = find_plan_workspace(root, plan_id)
    plan_dir = get_plan_dir(root, workspace, plan_id)
    plan_path = plan_dir / "plan.json"
    graph_path = None
    if plan_path.exists():
        try:
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            graph_path = plan.get("code_graph_path")
        except Exception:
            graph_path = None
    if not graph_path:
        graph_path = plan_dir / "code-graph.json"
    graph_path = Path(graph_path)
    if not graph_path.exists():
        return None
    try:
        return code_graph_service.load(graph_path)
    except Exception:
        return None


def _write_meta(meta_path: Path, updates: dict) -> dict:
    meta = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
    meta.update(updates)
    meta["updated_at"] = time.time()
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def _append_event(run_dir: Path, payload: dict) -> None:
    append_jsonl(run_dir / "events.jsonl", payload)


def _check_canceled(run_dir: Path) -> bool:
    """检查当前 run 是否被标记为取消"""
    return (run_dir / "cancel.flag").exists()


def _check_paused(run_dir: Path) -> bool:
    """检查当前 run 是否被标记为暂停"""
    return (run_dir / "pause.flag").exists()


def _wait_while_paused(run_dir: Path, check_interval: float = 2.0) -> bool:
    """在被暂停期间轮询标志；返回 True 表示期间收到取消请求"""
    while _check_paused(run_dir):
        if _check_canceled(run_dir):
            return True
        time.sleep(check_interval)
    return False


class TaskController:
    def __init__(
        self,
        root: Path,
        profile_service: IProfileService,
        verifier: IVerifier,
        code_graph_service: ICodeGraphService,
    ) -> None:
        self._root = root
        self._profile_service = profile_service
        self._verifier = verifier
        self._code_graph_service = code_graph_service

    def run(self, args: argparse.Namespace) -> None:
        root = self._root
        initial_workspace = args.workspace
        plan_workspace = find_plan_workspace(root, args.plan_id) if args.plan_id else None
        workspace_target = plan_workspace or initial_workspace
        backlog_dir = get_backlog_dir(root, workspace_target)
        backlog_dir.mkdir(parents=True, exist_ok=True)
        if args.plan_id:
            backlog_path = backlog_dir / f"{args.plan_id}.json"
            backlog = read_json(backlog_path, default={"tasks": []})
            tasks_with_path = [(t, backlog_path) for t in backlog.get("tasks", [])]
        else:
            backlog_map = load_backlog_map_filtered(root, workspace_target)
            tasks_with_path = [(t, path) for path, tasks in backlog_map.items() for t in tasks]
            backlog = {"tasks": [t for t, _ in tasks_with_path]}

        task, backlog_path = pick_next_task(tasks_with_path, plan_filter=args.plan_id, workspace=workspace_target)
        if not task:
            from curriculum import suggest_next_task

            new_task = suggest_next_task("", backlog)
            if new_task:
                if args.plan_id:
                    backlog_path = backlog_dir / f"{args.plan_id}.json"
                else:
                    backlog_path = backlog_dir / "adhoc.json"
                backlog = read_json(backlog_path, default={"tasks": []})
                backlog.setdefault("tasks", []).append(new_task)
                write_json(backlog_path, backlog)
                print(f"[CURRICULUM] appended {new_task['id']} -> retry pick")
                task, backlog_path = pick_next_task(
                    [(t, backlog_path) for t in backlog.get("tasks", [])],
                    plan_filter=args.plan_id,
                    workspace=workspace_target,
                )

            if not task:
                print("[NOOP] No runnable tasks in backlog")
                return

        plan_id = task.get("plan_id")
        plan_id_for_run = plan_id or time.strftime("plan-%Y%m%d-%H%M%S")

        run_id = time.strftime("run-%Y%m%d-%H%M%S")

        workspace_path = initial_workspace
        task_workspace_path = task.get("workspace_path")
        if isinstance(task_workspace_path, str) and task_workspace_path.strip():
            workspace_path = task_workspace_path
        elif isinstance(task.get("workspace"), dict) and task["workspace"].get("path"):
            workspace_path = task["workspace"]["path"]
        workspace_path = str(auto_select_workspace(Path(workspace_path))) if workspace_path else None
        if workspace_path and is_workspace_unsafe(root, Path(workspace_path)):
            print(f"[POLICY] workspace path {workspace_path} includes engine root {root}; refusing to run.")
            return

        exec_dir = get_plan_dir(root, workspace_path, plan_id_for_run)
        exec_dir.mkdir(parents=True, exist_ok=True)
        run_dir = exec_dir / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        policy, policy_source, profile, capabilities = load_policy(root, workspace_path, self._profile_service)
        write_json(run_dir / "policy.json", policy)
        if capabilities:
            write_json(run_dir / "capabilities.json", {"workspace": workspace_path, "capabilities": capabilities})
        if profile:
            print(f"[PROFILE] workspace_id={profile.get('workspace_id')} fingerprint={profile.get('fingerprint')}")

        stage_manager = StageWorkspaceManager(root, stage_root=run_dir / "stage")
        stage_meta = None
        if workspace_path:
            stage_meta = stage_manager.create_stage(run_id, Path(workspace_path))

        def cleanup_stage() -> None:
            if not stage_meta or not workspace_path:
                return
            stage_root = stage_meta.get("stage_root")
            if not stage_root:
                return
            stage_manager.remove_stage(Path(stage_root), Path(workspace_path))

        meta_path = run_dir / "meta.json"
        disable_tests = args.mode != "manual"
        if os.getenv("AIPL_ALLOW_TESTS", "").lower() in {"1", "true", "yes"}:
            disable_tests = False
        if os.getenv("AIPL_DISABLE_TESTS", "").lower() in {"1", "true", "yes"}:
            disable_tests = True
        _write_meta(
            meta_path,
            {
                "run_id": run_id,
                "task_id": task.get("id"),
                "plan_id": plan_id_for_run,
                "ts": time.time(),
                "workspace_main_root": workspace_path,
                "workspace_stage_root": stage_meta.get("stage_root") if stage_meta else None,
                "stage_mode": stage_meta.get("mode") if stage_meta else None,
                "base_ref": stage_meta.get("base_ref") if stage_meta else None,
                "policy_source": policy_source,
                "workspace_id": policy.get("workspace_id"),
                "fingerprint": policy.get("fingerprint"),
                "mode": args.mode,
                "status": "running",
                "disable_tests": disable_tests,
            },
        )
        _append_event(run_dir, {"type": "run_init", "run_id": run_id, "plan_id": plan_id_for_run, "workspace": workspace_path, "ts": time.time()})
        if stage_meta:
            _append_event(
                run_dir,
                {
                    "type": "workspace_stage_ready",
                    "run_id": run_id,
                    "stage_root": stage_meta.get("stage_root"),
                    "base_ref": stage_meta.get("base_ref"),
                    "stage_mode": stage_meta.get("mode"),
                    "ts": time.time(),
                },
            )

        passed_all = True
        final_reasons = []
        last_step_id = None
        max_rounds = max(args.max_rounds, 1)

        while task:
            # ========== 新增：取消检测 ==========
            if _check_canceled(run_dir):
                print(f"[CANCELED] Run {run_id} canceled by user request")
                _append_event(
                    run_dir,
                    {
                        "type": "run_canceled",
                        "run_id": run_id,
                        "plan_id": plan_id_for_run,
                        "ts": time.time(),
                    },
                )
                _write_meta(meta_path, {"status": "canceled", "canceled_at": time.time()})
                update_run_status(root, run_id, "canceled")
                cleanup_stage()
                return
            # ========== 新增：暂停检测 ==========
            if _check_paused(run_dir):
                print(f"[PAUSED] Run {run_id} paused by user request, waiting for resume...")
                _append_event(
                    run_dir,
                    {
                        "type": "run_paused",
                        "run_id": run_id,
                        "plan_id": plan_id_for_run,
                        "ts": time.time(),
                    },
                )
                _write_meta(meta_path, {"status": "paused", "paused_at": time.time()})
                if _wait_while_paused(run_dir):
                    print(f"[CANCELED] Run {run_id} canceled while paused")
                    _append_event(
                        run_dir,
                        {
                            "type": "run_canceled",
                            "run_id": run_id,
                            "plan_id": plan_id_for_run,
                            "ts": time.time(),
                        },
                    )
                    _write_meta(meta_path, {"status": "canceled", "canceled_at": time.time()})
                    update_run_status(root, run_id, "canceled")
                    cleanup_stage()
                    return
                print(f"[RESUMED] Run {run_id} resumed")
                _append_event(
                    run_dir,
                    {
                        "type": "run_resumed",
                        "run_id": run_id,
                        "plan_id": plan_id_for_run,
                        "ts": time.time(),
                    },
                )
                _write_meta(meta_path, {"status": "running", "resumed_at": time.time()})
            # ========== 新增结束 ==========
            task_id = task["id"]
            task_title = task.get("title", "")
            task["status"] = "doing"
            write_json(backlog_path, backlog)
            step_id = task.get("step_id") or task_id
            _write_meta(meta_path, {"task_id": task_id, "step_id": step_id, "task_title": task_title, "status": "running"})
            step_event = {"type": "step_start", "task_id": task_id, "plan_id": plan_id_for_run, "step": step_id, "ts": time.time()}
            if task_title:
                step_event["task_title"] = task_title
                step_event["summary"] = task_title
            _append_event(run_dir, step_event)

            last_step_id = step_id
            passed = False

            for round_id in range(max_rounds):
                if _check_canceled(run_dir):
                    print(f"[CANCELED] Run {run_id} canceled during round {round_id}")
                    _append_event(
                        run_dir,
                        {
                            "type": "run_canceled",
                            "run_id": run_id,
                            "plan_id": plan_id_for_run,
                            "round": round_id,
                            "ts": time.time(),
                        },
                    )
                    passed_all = False
                    break
                mode = "good"
                round_dir = run_dir / "steps" / step_id / f"round-{round_id}"
                _append_event(
                    run_dir,
                    {"type": "step_round_start", "task_id": task_id, "plan_id": plan_id_for_run, "step": step_id, "round": round_id, "mode": mode, "ts": time.time()},
                )

                if args.mode != "manual":
                    cmd = [
                        "python",
                        "scripts/subagent_shim.py",
                        "--root",
                        str(root),
                        str(run_dir),
                        task_id,
                        step_id,
                        str(round_id),
                        mode,
                    ]
                    if stage_meta:
                        cmd.extend(["--workspace", stage_meta.get("stage_root"), "--workspace-main", workspace_path])
                    elif workspace_path:
                        cmd.extend(["--workspace", workspace_path])
                    subprocess.check_call(cmd, cwd=str(root))
                else:
                    round_dir.mkdir(parents=True, exist_ok=True)
                    (round_dir / "stdout.txt").write_text("manual mode: no side effects\n", encoding="utf-8")
                    (round_dir / "stderr.txt").write_text("", encoding="utf-8")

                verify_root = None
                if stage_meta and stage_meta.get("stage_root"):
                    verify_root = Path(stage_meta.get("stage_root"))
                elif workspace_path:
                    verify_root = Path(workspace_path)
                if args.mode == "manual":
                    passed = True
                    reasons = []
                else:
                    passed, reasons = self._verifier.verify_task(run_dir, task_id, workspace_path=verify_root)
                final_reasons = reasons

                write_json(round_dir / "verification.json", {"passed": passed, "reasons": reasons})

                _append_event(
                    run_dir,
                    {"type": "step_round_verified", "task_id": task_id, "plan_id": plan_id_for_run, "step": step_id, "round": round_id, "passed": passed, "ts": time.time()},
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
                    shape = {}
                    shape_path = round_dir / "shape_response.json"
                    if shape_path.exists():
                        try:
                            shape = json.loads(shape_path.read_text(encoding="utf-8"))
                            validation_reasons = shape.get("validation_reasons", [])
                        except Exception:
                            validation_reasons = []
                    suspected_related_files = []
                    graph = _load_code_graph(root, plan_id, self._code_graph_service)
                    if graph:
                        seeds = []
                        seeds.extend(extract_paths_from_reasons(reasons))
                        seeds.extend(extract_paths_from_checks(task.get("checks", [])))
                        normalized = [graph.normalize_path(p) for p in seeds]
                        normalized = [p for p in normalized if p]
                        if normalized:
                            suspected_related_files = graph.related_files(normalized, max_hops=2)
                    rework = self._verifier.collect_errors_for_retry(
                        run_dir=run_dir,
                        round_id=round_id,
                        max_rounds=max_rounds,
                        reasons=reasons,
                        produced_files=shape.get("produced", []) if isinstance(shape, dict) else [],
                        workspace_path=workspace_path,
                        prev_stdout=stdout_txt,
                        suspected_related_files=suspected_related_files,
                    )
                    payload = rework.to_dict() if hasattr(rework, "to_dict") else rework
                    if validation_reasons:
                        payload["validation_reasons"] = validation_reasons
                    write_json(round_dir / "rework_request.json", payload)

            if _check_canceled(run_dir):
                passed_all = False
                break

            task_checks = task.get("checks", []) if isinstance(task.get("checks"), list) else []
            policy_checks = policy.get("checks", []) if isinstance(policy, dict) else []
            task_risk = task.get("risk_level", task.get("risk", task.get("high_risk")))
            effective_checks = merge_checks(task_checks, policy_checks, high_risk=is_high_risk(task_risk))
            write_verification_report(run_dir, task_id, plan_id_for_run, workspace_path, passed, final_reasons, effective_checks)

            backlog = read_json(backlog_path, default={"tasks": []})
            events = []
            for t in backlog.get("tasks", []):
                if t.get("id") == task_id:
                    event = transition_task(
                        t,
                        "done" if passed else "failed",
                        now=time.time(),
                        source="controller",
                        reason=final_reasons,
                    )
                    if event:
                        events.append(event)
                    t["last_run"] = run_id
                    t["last_reasons"] = final_reasons
                    if plan_id_for_run:
                        t["last_plan"] = plan_id_for_run
                    break
            write_json(backlog_path, backlog)
            append_state_events(root, events)

            if not passed:
                passed_all = False
                break

            _append_event(run_dir, {"type": "step_done", "task_id": task_id, "plan_id": plan_id_for_run, "step": step_id, "ts": time.time()})

            if args.plan_id:
                task, backlog_path = pick_next_task(
                    [(t, backlog_path) for t in backlog.get("tasks", [])],
                    plan_filter=args.plan_id,
                    workspace=initial_workspace,
                )
                if not task:
                    break
            else:
                break

        index_lines = [
            f"# Run {run_id}",
            f"- Task: {last_step_id or '-'}",
            "",
            "## Evidence",
            "- meta.json",
            "- events.jsonl",
            "- policy.json",
            "- capabilities.json",
            "- verification_result.json",
            "- verification_report.md",
            "- outputs/",
        ]
        if last_step_id:
            index_lines.append(f"- steps/{last_step_id}/round-0/")
            index_lines.append(f"- steps/{last_step_id}/round-1/")
        (run_dir / "index.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")

        patchset = None
        if passed_all and stage_meta and workspace_path:
            patchset = build_patchset(Path(stage_meta.get("stage_root")), Path(workspace_path), run_dir)
            changed_count = len(patchset.changed_files)
            _append_event(
                run_dir,
                {
                    "type": "patchset_ready",
                    "run_id": run_id,
                    "changed_files": changed_count,
                    "patchset_path": str(patchset.patchset_path.relative_to(run_dir).as_posix()),
                    "ts": time.time(),
                },
            )
            patch_rel = patchset.patchset_path.relative_to(run_dir).as_posix()
            changed_rel = patchset.changed_files_path.relative_to(run_dir).as_posix()
            _write_meta(
                meta_path,
                {
                    "patchset_path": patch_rel,
                    "changed_files_path": changed_rel,
                    "changed_files_count": changed_count,
                },
            )
        final_status = "failed"
        if _check_canceled(run_dir):
            final_status = "canceled"
            _append_event(
                run_dir,
                {"type": "run_done", "run_id": run_id, "plan_id": plan_id_for_run, "passed": False, "status": final_status, "ts": time.time()},
            )
            _write_meta(meta_path, {"status": final_status})
        elif passed_all:
            if patchset and len(patchset.changed_files) > 0:
                final_status = "awaiting_review"
                _append_event(run_dir, {"type": "awaiting_review", "run_id": run_id, "ts": time.time()})
                _write_meta(meta_path, {"status": final_status})
            else:
                final_status = "done"
                _append_event(run_dir, {"type": "run_done", "run_id": run_id, "plan_id": plan_id_for_run, "passed": True, "status": final_status, "ts": time.time()})
                _write_meta(meta_path, {"status": final_status})
        else:
            final_status = "failed"
            _append_event(run_dir, {"type": "run_done", "run_id": run_id, "plan_id": plan_id_for_run, "passed": False, "status": final_status, "ts": time.time()})
            _write_meta(meta_path, {"status": final_status})
        if final_status in {"done", "failed", "canceled"}:
            cleanup_stage()

        try:
            meta_snapshot = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            meta_snapshot = {}
        workspace_value = (
            meta_snapshot.get("workspace_main_root")
            or meta_snapshot.get("workspace_stage_root")
            or ""
        )
        mirror_run(
            root,
            run_id,
            plan_id_for_run,
            workspace=workspace_value,
            status=final_status,
            task=meta_snapshot.get("task_title", "") or "",
        )

        print(f"[DONE] run={run_dir} status={final_status}")
