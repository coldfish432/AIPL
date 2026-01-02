import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path

from config import DEFAULT_COMMAND_TIMEOUT, DEFAULT_MAX_CONCURRENCY, DEFAULT_DENY_WRITE
from detect_workspace import detect_workspace
from infra.io_utils import append_jsonl, read_json, write_json
from state import append_state_events, transition_task
from interfaces.protocols import ICodeGraphService, IProfileService, IVerifier
from services.code_graph_service import CodeGraphService
from services.patchset_service import build_patchset
from services.profile_service import ProfileService
from services.stage_workspace import StageWorkspaceManager
from services.chain_workspace import ChainWorkspaceManager
from services.verifier import VerifierService
from config import resolve_db_path
from infra.path_guard import is_workspace_unsafe


# ????files?????????

def _list_backlog_files(root: Path) -> list[Path]:
    backlog_dir = root / "backlog"
    if not backlog_dir.exists():
        return []
    return sorted(backlog_dir.glob("*.json"))


# ????map???????

def _load_backlog_map(root: Path) -> dict[Path, list[dict]]:
    backlog_map: dict[Path, list[dict]] = {}
    for path in _list_backlog_files(root):
        data = read_json(path, default={"tasks": []})
        backlog_map[path] = (data or {}).get("tasks", [])
    return backlog_map


def _auto_select_workspace(workspace: Path) -> Path:
    workspace = workspace.resolve()
    info = detect_workspace(workspace)
    detected = info.get("detected") or []
    if info.get("project_type") != "unknown" or detected or info.get("checks"):
        return workspace
    candidates: list[tuple[int, Path]] = []
    deny = set(DEFAULT_DENY_WRITE or [])
    for child in sorted(workspace.iterdir()):
        if not child.is_dir():
            continue
        name = child.name
        if name.startswith(".") or name in deny:
            continue
        sub_info = detect_workspace(child)
        sub_detected = sub_info.get("detected") or []
        if sub_info.get("project_type") == "unknown" and not sub_detected and not sub_info.get("checks"):
            continue
        score = len(sub_detected) + (1 if sub_info.get("checks") else 0)
        candidates.append((score, child))
    if not candidates:
        return workspace
    candidates.sort(key=lambda item: (-item[0], item[1].name.lower()))
    chosen = candidates[0][1]
    print(f"[WORKSPACE] auto-selected subdir: {chosen}")
    return chosen


# ?? load effective hard policy (user_hard overlay on system_hard) and optional checks

def load_policy(root: Path, workspace_path: str | None, profile_service: IProfileService) -> tuple[dict, str, dict | None, dict | None]:
    """
    load effective hard policy (user_hard overlay on system_hard) and optional checks.
    """
    if not workspace_path:
        return {}, "none", None, None
    workspace = Path(workspace_path)
    profile = profile_service.ensure_profile(root, workspace)
    if profile.get("created"):
        profile = profile_service.propose_soft(root, workspace, reason="new_workspace")
    elif profile.get("fingerprint_changed"):
        profile = profile_service.propose_soft(root, workspace, reason="fingerprint_changed")
    effective_hard = profile.get("effective_hard") or {}
    workspace_info = detect_workspace(workspace)
    checks = workspace_info.get("checks", [])
    capabilities = workspace_info.get("capabilities", {})
    policy = {
        "allow_write": effective_hard.get("allow_write", []),
        "deny_write": effective_hard.get("deny_write", []),
        "allowed_commands": effective_hard.get("allowed_commands", []),
        "command_timeout": effective_hard.get("command_timeout", DEFAULT_COMMAND_TIMEOUT),
        "max_concurrency": effective_hard.get("max_concurrency", DEFAULT_MAX_CONCURRENCY),
        "checks": checks,
        "workspace_id": profile.get("workspace_id"),
        "fingerprint": profile.get("fingerprint"),
    }
    return policy, "profile", profile, capabilities


# ??????

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


# ??????????JSON

def format_checks(checks: list[dict]) -> list[str]:
    lines = []
    for c in checks:
        ctype = c.get("type")
        if ctype == "command":
            timeout = c.get("timeout", "")
            lines.append(f"- command: {c.get('cmd')} timeout={timeout}")
        elif ctype == "command_contains":
            timeout = c.get("timeout", "")
            lines.append(f"- command_contains: {c.get('cmd')} needle={c.get('needle')} timeout={timeout}")
        elif ctype == "file_exists":
            lines.append(f"- file_exists: {c.get('path')}")
        elif ctype == "file_contains":
            lines.append(f"- file_contains: {c.get('path')} needle={c.get('needle')}")
        elif ctype == "json_schema":
            lines.append(f"- json_schema: {c.get('path')}")
        elif ctype == "http_check":
            lines.append(f"- http_check: {c.get('url')}")
        else:
            lines.append(f"- unknown: {json.dumps(c, ensure_ascii=False)}")
    return lines


# ?????????????????JSON

def write_verification_report(run_dir: Path, task_id: str, plan_id: str | None, workspace_path: str | None, passed: bool, reasons: list, checks: list[dict]):
    lines = [
        "# Verification Report",
        f"- task_id: {task_id}",
        f"- plan_id: {plan_id}",
        f"- run_dir: {run_dir}",
        f"- workspace: {workspace_path}",
        f"- passed: {passed}",
        f"- verification_result: {run_dir / 'verification_result.json'}",
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
            elif c.get("type") == "command_contains":
                lines.append(f"- run: {c.get('cmd')} (expect contains {c.get('needle')})")
            elif c.get("type") == "file_exists":
                lines.append(f"- check file exists: {c.get('path')}")
            elif c.get("type") == "file_contains":
                lines.append(f"- check file contains: {c.get('path')} -> {c.get('needle')}")
            elif c.get("type") == "json_schema":
                lines.append(f"- check json schema: {c.get('path')}")
            elif c.get("type") == "http_check":
                lines.append(f"- http check: {c.get('url')}")
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


# extract??from??

def _extract_paths_from_reasons(reasons: list) -> list[str]:
    paths: list[str] = []
    for reason in reasons or []:
        if not isinstance(reason, dict):
            continue
        for key in ("file", "path"):
            value = reason.get(key)
            if isinstance(value, str) and value.strip():
                paths.append(value.strip())
    return paths


# extract??from???

def _extract_paths_from_checks(checks: list[dict]) -> list[str]:
    paths: list[str] = []
    for check in checks or []:
        if not isinstance(check, dict):
            continue
        value = check.get("path")
        if isinstance(value, str) and value.strip():
            paths.append(value.strip())
    return paths


# ??????execution??

def _has_execution_check(checks: list[dict]) -> bool:
    for check in checks or []:
        if check.get("type") in {"command", "command_contains", "http_check"}:
            return True
    return False


# ?????

def _merge_checks(task_checks: list[dict], policy_checks: list[dict], high_risk: bool = False) -> list[dict]:
    if _has_execution_check(task_checks) and not high_risk:
        return list(task_checks or [])
    merged = list(task_checks or [])
    merged.extend(policy_checks or [])
    return merged


# ???????

def _is_high_risk(value) -> bool:
    if value is True:
        return True
    if isinstance(value, (int, float)) and value >= 7:
        return True
    if isinstance(value, str) and value.strip().lower() in {"high", "critical"}:
        return True
    return False


# ?????????????????JSON

def _load_code_graph(root: Path, plan_id: str | None, code_graph_service: ICodeGraphService):
    if not plan_id:
        return None
    plan_path = root / "artifacts" / "executions" / plan_id / "plan.json"
    graph_path = None
    if plan_path.exists():
        try:
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            graph_path = plan.get("code_graph_path")
        except Exception:
            graph_path = None
    if not graph_path:
        graph_path = root / "artifacts" / "executions" / plan_id / "code-graph.json"
    graph_path = Path(graph_path)
    if not graph_path.exists():
        return None
    try:
        return code_graph_service.load(graph_path)
    except Exception:
        return None


# ??run meta

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


# ??run??

def _append_event(run_dir: Path, payload: dict) -> None:
    append_jsonl(run_dir / "events.jsonl", payload)


def _ensure_sqlite_schema(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, plan_id TEXT, status TEXT, updated_at INTEGER, raw_json TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS plans (plan_id TEXT PRIMARY KEY, updated_at INTEGER, raw_json TEXT)")


def _mirror_run_to_sqlite(root: Path, payload: dict) -> None:
    run_id = payload.get("run_id")
    plan_id = payload.get("plan_id")
    if not run_id:
        return
    db_path = resolve_db_path(root)
    if not db_path:
        return
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        now_ms = int(time.time() * 1000)
        raw_json = json.dumps({"ok": True, "ts": int(time.time()), "data": payload}, ensure_ascii=False)
        with sqlite3.connect(str(db_path)) as conn:
            _ensure_sqlite_schema(conn)
            conn.execute(
                "INSERT INTO runs(run_id, plan_id, status, updated_at, raw_json) VALUES(?,?,?,?,?) "
                "ON CONFLICT(run_id) DO UPDATE SET plan_id=excluded.plan_id, status=excluded.status, updated_at=excluded.updated_at, raw_json=excluded.raw_json",
                (run_id, plan_id, payload.get("status"), now_ms, raw_json),
            )
            conn.commit()
    except Exception:
        return


class TaskController:
    # ???
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

    # ??????????????
    def run(self, args: argparse.Namespace) -> None:
        root = self._root
        if args.plan_id:
            backlog_path = root / "backlog" / f"{args.plan_id}.json"
            backlog = read_json(backlog_path, default={"tasks": []})
            tasks_with_path = [(t, backlog_path) for t in backlog.get("tasks", [])]
        else:
            backlog_map = _load_backlog_map(root)
            tasks_with_path = [(t, path) for path, tasks in backlog_map.items() for t in tasks]
            backlog = {"tasks": [t for t, _ in tasks_with_path]}

        task, backlog_path = pick_next_task(tasks_with_path, plan_filter=args.plan_id)
        if not task:
            from curriculum import suggest_next_task

            new_task = suggest_next_task("", backlog)
            if new_task:
                if args.plan_id:
                    backlog_path = root / "backlog" / f"{args.plan_id}.json"
                else:
                    backlog_path = root / "backlog" / "adhoc.json"
                backlog = read_json(backlog_path, default={"tasks": []})
                backlog.setdefault("tasks", []).append(new_task)
                write_json(backlog_path, backlog)
                print(f"[CURRICULUM] appended {new_task['id']} -> retry pick")
                task, backlog_path = pick_next_task([(t, backlog_path) for t in backlog.get("tasks", [])], plan_filter=args.plan_id)

            if not task:
                print("[NOOP] No runnable tasks in backlog")
                return

        plan_id = task.get("plan_id")
        plan_id_for_run = plan_id or time.strftime("plan-%Y%m%d-%H%M%S")

        run_id = time.strftime("run-%Y%m%d-%H%M%S")
        exec_dir = root / "artifacts" / "executions" / plan_id_for_run
        exec_dir.mkdir(parents=True, exist_ok=True)
        run_dir = exec_dir / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        workspace_path = args.workspace
        if isinstance(task.get("workspace"), dict) and task["workspace"].get("path"):
            workspace_path = task["workspace"]["path"]
        workspace_path = str(_auto_select_workspace(Path(workspace_path))) if workspace_path else None
        if workspace_path and is_workspace_unsafe(root, Path(workspace_path)):
            print(f"[POLICY] workspace path {workspace_path} includes engine root {root}; refusing to run.")
            return

        policy, policy_source, profile, capabilities = load_policy(root, workspace_path, self._profile_service)
        write_json(run_dir / "policy.json", policy)
        if capabilities:
            write_json(run_dir / "capabilities.json", {"workspace": workspace_path, "capabilities": capabilities})
        if profile:
            print(f"[PROFILE] workspace_id={profile.get('workspace_id')} fingerprint={profile.get('fingerprint')}")

        stage_manager = StageWorkspaceManager(root, stage_root=run_dir / "stage")
        chain_manager = None
        stage_meta = None
        if workspace_path:
            use_chain = os.getenv("AIPL_CHAIN_WORKSPACE", "1") != "0"
            if use_chain and plan_id_for_run:
                chain_manager = ChainWorkspaceManager(root)
                chain_manager.ensure_chain(plan_id_for_run, Path(workspace_path))
                stage_meta = chain_manager.create_run_stage(plan_id_for_run, run_id, run_dir / "stage")
            else:
                stage_meta = stage_manager.create_stage(run_id, Path(workspace_path))

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
                "policy": args.policy,
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
            task_id = task["id"]
            task_title = task.get("title", "")
            task["status"] = "doing"
            write_json(backlog_path, backlog)
            step_id = task.get("step_id") or task_id
            _write_meta(meta_path, {"task_id": task_id, "step_id": step_id, "task_title": task_title, "status": "running"})
            _append_event(run_dir, {"type": "step_start", "task_id": task_id, "plan_id": plan_id_for_run, "step": step_id, "ts": time.time()})

            last_step_id = step_id
            passed = False

            for round_id in range(max_rounds):
                mode = "good"
                round_dir = run_dir / "steps" / step_id / f"round-{round_id}"
                _append_event(
                    run_dir,
                    {"type": "step_round_start", "task_id": task_id, "plan_id": plan_id_for_run, "step": step_id, "round": round_id, "mode": mode, "ts": time.time()},
                )

                if args.mode != "manual":
                    cmd = ["python", "scripts/subagent_shim.py", "--root", str(root), str(run_dir), task_id, step_id, str(round_id), mode]
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

                write_json(
                    round_dir / "verification.json",
                    {"passed": passed, "reasons": reasons},
                )

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
                        seeds.extend(_extract_paths_from_reasons(reasons))
                        seeds.extend(_extract_paths_from_checks(task.get("checks", [])))
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

            task_checks = task.get("checks", []) if isinstance(task.get("checks"), list) else []
            policy_checks = policy.get("checks", []) if isinstance(policy, dict) else []
            task_risk = task.get("risk_level", task.get("risk", task.get("high_risk")))
            effective_checks = _merge_checks(task_checks, policy_checks, high_risk=_is_high_risk(task_risk))
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
                task, backlog_path = pick_next_task([(t, backlog_path) for t in backlog.get("tasks", [])], plan_filter=args.plan_id)
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
            if chain_manager:
                try:
                    chain_manager.complete_run(plan_id_for_run, run_id, Path(stage_meta.get("stage_root")))
                except Exception:
                    pass

        final_status = "failed"
        if passed_all:
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
            if chain_manager:
                try:
                    chain_manager.fail_run(plan_id_for_run, run_id, error="verification_failed")
                except Exception:
                    pass

        if final_status in {"done", "failed"} and stage_meta and workspace_path:
            if chain_manager:
                try:
                    stage_root = Path(stage_meta.get("stage_root"))
                    if stage_root.exists():
                        shutil.rmtree(stage_root, ignore_errors=True)
                except Exception:
                    pass
            else:
                stage_manager.remove_stage(Path(stage_meta.get("stage_root")), Path(workspace_path))

        try:
            meta_snapshot = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            meta_snapshot = {}
        payload = {
            "run_id": run_id,
            "plan_id": plan_id_for_run,
            "status": final_status,
            "mode": meta_snapshot.get("mode"),
            "policy": meta_snapshot.get("policy"),
            "patchset_path": meta_snapshot.get("patchset_path"),
            "changed_files_count": meta_snapshot.get("changed_files_count"),
            "workspace_main_root": meta_snapshot.get("workspace_main_root"),
            "workspace_stage_root": meta_snapshot.get("workspace_stage_root"),
        }
        _mirror_run_to_sqlite(root, payload)

        print(f"[DONE] run={run_dir} status={final_status}")
        if not passed_all and workspace_path and self._profile_service.should_propose_on_failure(root, Path(workspace_path), threshold=2):
            self._profile_service.propose_soft(root, Path(workspace_path), reason="repeated_failures")


# ???????

def create_default_controller(root: Path) -> TaskController:
    return TaskController(root, ProfileService(), VerifierService(root), CodeGraphService(cache_root=root))


# ???????????

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, help="repo root path")
    parser.add_argument("--plan-id", dest="plan_id", help="?? plan_id ??")
    parser.add_argument("--workspace", dest="workspace", help="?? workspace ???????")
    parser.add_argument("--max-rounds", dest="max_rounds", type=int, default=3, help="????")
    parser.add_argument("--mode", dest="mode", default="autopilot", choices=["autopilot", "manual"], help="run mode")
    parser.add_argument("--policy", dest="policy", default="guarded", help="execution policy")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    controller = create_default_controller(root)
    controller.run(args)


if __name__ == "__main__":
    main()
