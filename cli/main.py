import argparse
import json
import os
import subprocess
import time
import uuid
import hashlib
import sqlite3
import shutil
from pathlib import Path
from dataclasses import asdict

from config import resolve_db_path
from detect_workspace import detect_workspace
from infra.io_utils import append_jsonl, read_json, write_json
from infra.path_guard import normalize_path
from state import append_state_events, build_transition_event
from profile_store import ensure_profile_tables
from services.profile_service import compute_fingerprint, compute_workspace_id
from engine.patterns.service import LanguagePackService
from engine.memory.pack_service import ExperiencePackService
from services.code_graph_service import CodeGraphService
from services.profile_service import ProfileService
from services.patchset_service import apply_patchset, build_patchset
from services.stage_workspace import StageWorkspaceManager
from services.verifier import VerifierService


def _extract_last_json(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in reversed(lines):
        if line.startswith("{") or line.startswith("["):
            return line
    return text.strip()


def _decode_codex_bytes(data: bytes) -> str:
    for enc in ("utf-8", "gbk"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _format_conversation(messages: list[dict]) -> str:
    lines = []
    for msg in messages:
        role = str(msg.get("role", "user")).strip().lower()
        content = str(msg.get("content", "")).strip()
        if not content:
            continue
        label = "User" if role == "user" else "Assistant"
        lines.append(f"{label}: {content}")
    return "\n".join(lines)


def run_codex_chat(prompt: str, root_dir: Path, workspace: Path | None = None) -> str:
    """
    Run Codex chat from the given workspace (if supplied) or the engine root.
    """
    schema_path = (root_dir / "schemas" / "chat.schema.json").resolve()
    codex_bin = os.environ.get("CODEX_BIN") or shutil.which("codex")
    if not codex_bin and os.name == "nt":
        for cand in ("codex.cmd", "codex.exe", "codex.bat"):
            codex_bin = shutil.which(cand)
            if codex_bin:
                break
    codex_bin = codex_bin or "codex"
    work_dir = str(workspace.resolve()) if workspace else str(root_dir)
    cmd = [
        codex_bin, "exec", "--full-auto",
        "--sandbox", "workspace-write",
        "-C", work_dir,
        "--skip-git-repo-check",
        "--output-schema", str(schema_path),
        "--color", "never",
    ]
    result = subprocess.run(
        cmd,
        input=prompt.encode("utf-8"),
        capture_output=True,
        text=False,
        shell=False,
    )
    if result.returncode != 0:
        err = _decode_codex_bytes(result.stderr or result.stdout or b"")
        raise RuntimeError((err or "codex failed").strip())
    return _decode_codex_bytes(result.stdout or b"").strip()


def _build_workspace_context(root: Path, workspace_path: Path | None) -> str:
    """
    Build a lightweight workspace context summary for the chat prompt.
    """
    if not workspace_path:
        return "No workspace configured. Please set a workspace path first."

    workspace_path = workspace_path.resolve()
    parts = [f"**Workspace Path:** `{workspace_path}`"]

    workspace_info = detect_workspace(workspace_path)
    if workspace_info:
        project_type = workspace_info.get("project_type", "unknown")
        parts.append(f"**Project Type:** {project_type}")

        capabilities = workspace_info.get("capabilities", {})
        detected = capabilities.get("detected", [])
        if detected:
            parts.append(f"**Detected Config Files:** {', '.join(detected)}")

        commands = capabilities.get("commands", [])
        if commands:
            cmd_list = [f"`{c.get('cmd')}` ({c.get('kind')})" for c in commands if c.get("cmd")]
            if cmd_list:
                parts.append(f"**Available Commands:** {', '.join(cmd_list)}")

    IGNORE_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv',
                   'dist', 'build', 'target', '.idea', '.vscode', 'coverage'}
    try:
        tree_lines = []
        items = sorted(workspace_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        for item in items[:40]:
            if item.name.startswith('.') and item.name not in ('.env.example',):
                continue
            if item.name in IGNORE_DIRS:
                continue
            prefix = "📁 " if item.is_dir() else "📄 "
            tree_lines.append(prefix + item.name)

        if tree_lines:
            parts.append("**Directory Structure:**\n```\n" + "\n".join(tree_lines) + "\n```")
    except Exception:
        pass

    key_files_content = []
    for readme_name in ("README.md", "readme.md", "README.txt", "README"):
        readme_path = workspace_path / readme_name
        if readme_path.exists():
            try:
                content = readme_path.read_text(encoding="utf-8")
                if len(content) > 1500:
                    content = content[:1500] + "\n... (truncated)"
                key_files_content.append(f"### {readme_name}\n```markdown\n{content}\n```")
            except Exception:
                pass
            break

    config_files = [
        ("package.json", "json", 1000),
        ("pyproject.toml", "toml", 800),
        ("Cargo.toml", "toml", 800),
        ("pom.xml", "xml", 800),
        ("go.mod", "go", 500),
        ("Makefile", "makefile", 500),
    ]
    for filename, lang, max_chars in config_files:
        filepath = workspace_path / filename
        if filepath.exists():
            try:
                content = filepath.read_text(encoding="utf-8")
                if len(content) > max_chars:
                    content = content[:max_chars] + "\n... (truncated)"
                key_files_content.append(f"### {filename}\n```{lang}\n{content}\n```")
            except Exception:
                pass

    if key_files_content:
        parts.append("**Key Files:**\n" + "\n\n".join(key_files_content))

    return "\n\n".join(parts)


# envelope
def envelope(ok: bool, data=None, error=None):
    return {
        "ok": ok,
        "ts": int(time.time()),
        "trace_id": f"trc_{uuid.uuid4().hex[:12]}",
        "data": data,
        "error": error,
    }


# 解析db路径
def _resolve_db_path(root: Path) -> Path | None:
    return resolve_db_path(root)


def _load_payload(path: str | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    return read_json(p, default={})


def _resolve_workspace_id(workspace_id: str | None, workspace: str | None) -> str | None:
    if workspace_id:
        return workspace_id
    if workspace:
        return compute_workspace_id(Path(workspace))
    return None


# 确保sqliteSchema
def _ensure_sqlite_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            plan_id TEXT,
            status TEXT,
            workspace TEXT,
            updated_at INTEGER,
            raw_json TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS plans (
            plan_id TEXT PRIMARY KEY,
            workspace TEXT,
            updated_at INTEGER,
            raw_json TEXT
        )"""
    )
    conn.execute("CREATE TABLE IF NOT EXISTS event_cursors (run_id TEXT PRIMARY KEY, cursor INTEGER, updated_at INTEGER)")
    try:
        conn.execute("ALTER TABLE runs ADD COLUMN workspace TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE plans ADD COLUMN workspace TEXT")
    except sqlite3.OperationalError:
        pass
    ensure_profile_tables(conn)


# mirror计划tosqlite，序列化JSON，创建目录
def _mirror_plan_to_sqlite(res: dict, root: Path) -> None:
    data = res.get("data") if isinstance(res, dict) else None
    if not isinstance(data, dict):
        return
    plan_id = data.get("plan_id")
    if not plan_id:
        return
    db_path = _resolve_db_path(root)
    if not db_path:
        return
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        raw_json = json.dumps(res, ensure_ascii=False)
        now_ms = int(time.time() * 1000)
        plan_workspace = _resolve_plan_workspace(root, plan_id)
        with sqlite3.connect(str(db_path)) as conn:
            _ensure_sqlite_schema(conn)
            conn.execute(
                "INSERT INTO plans(plan_id, workspace, updated_at, raw_json) VALUES(?,?,?,?) "
                "ON CONFLICT(plan_id) DO UPDATE SET workspace=excluded.workspace, updated_at=excluded.updated_at, raw_json=excluded.raw_json",
                (plan_id, plan_workspace or "", now_ms, raw_json),
            )
            conn.commit()
    except Exception:
        return


# mirror运行tosqlite，序列化JSON，创建目录
def _mirror_run_to_sqlite(res: dict, root: Path) -> None:
    data = res.get("data") if isinstance(res, dict) else None
    if not isinstance(data, dict):
        return
    run_id = data.get("run_id")
    if not run_id:
        return
    db_path = _resolve_db_path(root)
    if not db_path:
        return
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        raw_json = json.dumps(res, ensure_ascii=False)
        now_ms = int(time.time() * 1000)
        plan_id = data.get("plan_id")
        status = data.get("status")
        workspace = (
            data.get("workspace_main_root")
            or data.get("workspace")
            or data.get("workspace_path")
            or ""
        )
        with sqlite3.connect(str(db_path)) as conn:
            _ensure_sqlite_schema(conn)
            conn.execute(
                "INSERT INTO runs(run_id, plan_id, status, workspace, updated_at, raw_json) VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(run_id) DO UPDATE SET plan_id=excluded.plan_id, status=excluded.status, workspace=excluded.workspace, updated_at=excluded.updated_at, raw_json=excluded.raw_json",
                (run_id, plan_id, status, workspace, now_ms, raw_json),
            )
            conn.commit()
    except Exception:
        return


# 查找latest运行，检查路径是否存在
def find_latest_run(exec_dir: Path) -> Path | None:
    runs_dir = exec_dir / "runs"
    if not runs_dir.exists():
        return None
    runs = [p for p in runs_dir.iterdir() if p.is_dir()]
    if not runs:
        return None
    runs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return runs[0]


# 解析运行dir，检查路径是否存在
def resolve_run_dir(root: Path, plan_id: str | None, run_id: str | None) -> Path | None:
    if plan_id:
        exec_dir = root / "artifacts" / "executions" / plan_id
        if run_id:
            cand = exec_dir / "runs" / run_id
            return cand if cand.exists() else None
        return find_latest_run(exec_dir)
    if run_id:
        exec_root = root / "artifacts" / "executions"
        if exec_root.exists():
            for plan_dir in exec_root.iterdir():
                cand = plan_dir / "runs" / run_id
                if cand.exists():
                    return cand
    return None


def _resolve_plan_workspace(root: Path, plan_id: str) -> str | None:
    """Resolve the workspace path stored with the plan."""
    exec_dir = root / "artifacts" / "executions" / plan_id
    cap_path = exec_dir / "capabilities.json"
    if cap_path.exists():
        try:
            cap = read_json(cap_path, default={})
            if isinstance(cap, dict):
                ws = cap.get("workspace")
                if isinstance(ws, str) and ws.strip():
                    return ws
        except Exception:
            pass

    plan_path = exec_dir / "plan.json"
    if plan_path.exists():
        try:
            plan = read_json(plan_path, default={})
            if isinstance(plan, dict):
                for key in ["workspace", "workspace_path", "workspace_main_root"]:
                    ws = plan.get(key)
                    if isinstance(ws, str) and ws.strip():
                        return ws
        except Exception:
            pass

    return None


def list_plans_for_workspace(root: Path, workspace: str | None) -> list[dict]:
    """List plan metadata, optionally filtered by workspace."""
    exec_root = root / "artifacts" / "executions"
    if not exec_root.exists():
        return []

    plans: list[dict] = []
    workspace_normalized = normalize_path(workspace) if workspace else None

    for plan_dir in exec_root.iterdir():
        if not plan_dir.is_dir():
            continue

        plan_id = plan_dir.name
        plan_workspace = _resolve_plan_workspace(root, plan_id)

        if workspace_normalized:
            plan_workspace_normalized = normalize_path(plan_workspace) if plan_workspace else None
            if plan_workspace_normalized != workspace_normalized:
                continue

        plan_path = plan_dir / "plan.json"
        if not plan_path.exists():
            continue

        try:
            plan_data = read_json(plan_path, default={})
        except Exception:
            continue

        if not isinstance(plan_data, dict):
            continue

        tasks_count = len(plan_data.get("raw_plan", {}).get("tasks", []))
        plans.append(
            {
                "plan_id": plan_id,
                "workspace": plan_workspace,
                "created_ts": plan_data.get("created_ts"),
                "task_chain_text": plan_data.get("task_chain_text"),
                "tasks_count": tasks_count,
            }
        )

    return sorted(plans, key=lambda x: x.get("created_ts") or 0, reverse=True)


# 读取status，检查路径是否存在，读取文件内容
def read_status(run_dir: Path) -> dict:
    events_path = run_dir / "events.jsonl"
    status = "running"
    passed = None
    progress = None
    meta = {}
    meta_path = run_dir / "meta.json"
    if meta_path.exists():
        meta = read_json(meta_path, default={})
    if meta.get("status"):
        status = meta.get("status")
    if (run_dir / "cancel.flag").exists():
        status = "canceled"
    if events_path.exists():
        try:
            lines = events_path.read_text(encoding="utf-8").splitlines()
            mapping = {
                "run_init": 1,
                "workspace_stage_ready": 5,
                "step_round_start": 20,
                "step_round_verified": 70,
                "patchset_ready": 85,
                "awaiting_review": 90,
                "apply_start": 95,
                "apply_done": 98,
                "discard_done": 100,
                "run_done": 100,
            }
            for line in lines:
                for key, val in mapping.items():
                    if f'"type": "{key}"' in line:
                        progress = max(progress or 0, val)
            if not meta.get("status"):
                for line in reversed(lines):
                    if '"type": "run_done"' in line or '"type": "awaiting_review"' in line:
                        evt = json.loads(line)
                        if evt.get("type") == "awaiting_review":
                            status = "awaiting_review"
                            break
                        passed = evt.get("passed")
                        status = evt.get("status") or ("done" if passed else "failed")
                        break
        except Exception:
            pass
    if status in {"done", "failed", "discarded", "canceled"}:
        progress = 100
    if status == "awaiting_review":
        progress = max(progress or 0, 90)
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
                    ver = read_json(ver_path, default={})
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
        "progress": progress,
        "mode": meta.get("mode"),
        "workspace_main_root": meta.get("workspace_main_root"),
        "workspace_stage_root": meta.get("workspace_stage_root"),
        "patchset_path": meta.get("patchset_path"),
        "changed_files_count": meta.get("changed_files_count"),
    }
def list_runs(exec_dir: Path) -> list[dict]:
    """List the runs inside the execution directory with extra metadata."""
    runs_dir = exec_dir / "runs"
    if not runs_dir.exists():
        return []
    runs: list[dict] = []
    for p in runs_dir.iterdir():
        if not p.is_dir():
            continue

        run_info = {
            "run_id": p.name,
            "run_dir": str(p),
            "outputs": str(p / "outputs"),
            "report_path": str(p / "verification_report.md"),
        }

        meta_path = p / "meta.json"
        if meta_path.exists():
            try:
                meta = read_json(meta_path, default={})
                if isinstance(meta, dict):
                    run_info.update(
                        {
                            "status": meta.get("status"),
                            "workspace": meta.get("workspace_main_root")
                            or meta.get("workspace")
                            or meta.get("workspace_path"),
                            "mode": meta.get("mode"),
                            "task_id": meta.get("task_id"),
                            "plan_id": meta.get("plan_id"),
                            "created_at": meta.get("ts"),
                            "updated_at": meta.get("updated_at"),
                        }
                    )
            except Exception:
                pass

        runs.append(run_info)

    runs.sort(key=lambda x: x.get("run_id", ""), reverse=True)
    return runs


def list_runs_for_workspace(root: Path, workspace: str | None) -> list[dict]:
    """Filter listed runs by workspace."""
    exec_root = root / "artifacts" / "executions"
    if not exec_root.exists():
        return []

    all_runs: list[dict] = []
    workspace_normalized = normalize_path(workspace) if workspace else None

    for plan_dir in exec_root.iterdir():
        if not plan_dir.is_dir():
            continue

        plan_workspace = _resolve_plan_workspace(root, plan_dir.name)
        runs = list_runs(plan_dir)
        for run in runs:
            if workspace_normalized:
                run_workspace = run.get("workspace")
                if run_workspace:
                    if normalize_path(run_workspace) != workspace_normalized:
                        continue
                else:
                    if not plan_workspace or normalize_path(plan_workspace) != workspace_normalized:
                        continue
            all_runs.append(run)

    return sorted(all_runs, key=lambda x: x.get("run_id", ""), reverse=True)


def count_runs_by_status(root: Path, workspace: str | None) -> dict:
    """Return counts grouped by run status."""
    runs = list_runs_for_workspace(root, workspace)

    counts = {
        "total": len(runs),
        "running": 0,
        "completed": 0,
        "failed": 0,
        "awaiting_review": 0,
    }

    for run in runs:
        status = (run.get("status") or "").lower()
        if status in ("running", "doing"):
            counts["running"] += 1
        elif status in ("done", "completed", "success"):
            counts["completed"] += 1
        elif status == "failed":
            counts["failed"] += 1
        elif status == "awaiting_review":
            counts["awaiting_review"] += 1

    return counts


# 列出artifacts，读取文件
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


def _collect_retry_ids(tasks_by_id: dict[str, dict], task_id: str, include_deps: bool) -> set[str]:
    if not include_deps:
        return {task_id}
    seen: set[str] = set()
    stack = [task_id]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        task = tasks_by_id.get(current)
        if not task:
            continue
        deps = task.get("dependencies", [])
        if not isinstance(deps, list):
            continue
        for dep in deps:
            if isinstance(dep, str) and dep and dep not in seen:
                stack.append(dep)
    return seen


def _reset_tasks_to_todo(tasks: list[dict], reset_ids: set[str], reason: dict, now: float) -> list[dict]:
    events: list[dict] = []
    for task in tasks:
        task_id = task.get("id")
        if task_id not in reset_ids:
            continue
        from_status = task.get("status")
        if from_status == "todo":
            continue
        task["status"] = "todo"
        task["status_ts"] = now
        task.pop("heartbeat_ts", None)
        task.pop("stale_ts", None)
        events.append(build_transition_event(task, from_status, "todo", now, source="retry", reason=reason))
    return events


def _load_backlog_tasks(backlog_path: Path) -> tuple[dict, list[dict]]:
    backlog = read_json(backlog_path, default={"tasks": []})
    tasks = backlog.get("tasks", []) if isinstance(backlog, dict) else []
    if not isinstance(tasks, list):
        tasks = []
    return backlog, tasks


# cmd计划，执行外部命令，检查路径是否存在
def cmd_plan(args, root: Path):
    plan_id = args.plan_id or time.strftime("plan-%Y%m%d-%H%M%S")
    cmd = ["python", "plan_and_run.py", "--root", str(root), "--task", args.task, "--plan-id", plan_id, "--no-run"]
    if args.workspace:
        cmd.extend(["--workspace", args.workspace])
    subprocess.check_call(cmd, cwd=root)
    exec_dir = root / "artifacts" / "executions" / plan_id
    plan_path = exec_dir / "plan.json"
    tasks_count = 0
    if plan_path.exists():
        plan = read_json(plan_path, default={})
        tasks = plan.get("raw_plan", {}).get("tasks", [])
        tasks_count = len(tasks)
    data = {
        "plan_id": plan_id,
        "tasks_count": tasks_count,
        "backlog_written": True,
        "artifacts_root": str(exec_dir),
    }
    res = envelope(True, data=data)
    _mirror_plan_to_sqlite(res, root)
    print(json.dumps(res, ensure_ascii=False))


# cmd运行，执行外部命令，序列化JSON
def cmd_run(args, root: Path):
    plan_id = args.plan_id or time.strftime("plan-%Y%m%d-%H%M%S")
    cmd = ["python", "plan_and_run.py", "--root", str(root), "--task", args.task, "--plan-id", plan_id, "--mode", args.mode]
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
        "progress": status.get("progress"),
        "mode": status.get("mode"),
        "patchset_path": status.get("patchset_path"),
        "changed_files_count": status.get("changed_files_count"),
        "workspace_main_root": status.get("workspace_main_root"),
        "workspace_stage_root": status.get("workspace_stage_root"),
    }
    res = envelope(True, data=data)
    _mirror_run_to_sqlite(res, root)
    print(json.dumps(res, ensure_ascii=False))


# cmd????plan
def cmd_run_plan(args, root: Path):
    if not args.plan_id:
        print(json.dumps(envelope(False, error="plan_id is required"), ensure_ascii=False))
        return
    plan_workspace = _resolve_plan_workspace(root, args.plan_id)
    workspace_arg = plan_workspace or args.workspace
    cmd = ["python", "-m", "services.controller_service", "--root", str(root), "--plan-id", args.plan_id, "--mode", args.mode]
    if workspace_arg:
        cmd.extend(["--workspace", workspace_arg])
    subprocess.check_call(cmd, cwd=root)
    exec_dir = root / "artifacts" / "executions" / args.plan_id
    run_dir = find_latest_run(exec_dir)
    status = read_status(run_dir) if run_dir else {"status": "unknown"}
    data = {
        "run_id": run_dir.name if run_dir else None,
        "plan_id": args.plan_id,
        "status": status.get("status"),
        "progress": status.get("progress"),
        "mode": status.get("mode"),
        "patchset_path": status.get("patchset_path"),
        "changed_files_count": status.get("changed_files_count"),
        "workspace_main_root": status.get("workspace_main_root"),
        "workspace_stage_root": status.get("workspace_stage_root"),
    }
    res = envelope(True, data=data)
    _mirror_run_to_sqlite(res, root)
    print(json.dumps(res, ensure_ascii=False))


def cmd_retry(args, root: Path):
    run_dir = resolve_run_dir(root, args.plan_id, args.run_id)
    if not run_dir:
        print(json.dumps(envelope(False, error="run not found"), ensure_ascii=False))
        return
    status = read_status(run_dir)
    if not args.force and status.get("status") not in {"failed", "canceled", "discarded"}:
        print(json.dumps(envelope(False, error="run not retryable without force"), ensure_ascii=False))
        return
    meta = read_json(run_dir / "meta.json", default={})
    plan_id = args.plan_id or meta.get("plan_id")
    if not plan_id:
        print(json.dumps(envelope(False, error="plan_id not found"), ensure_ascii=False))
        return
    task_id = meta.get("task_id") or meta.get("step_id") or status.get("current_task_id")
    if not task_id:
        print(json.dumps(envelope(False, error="task_id not found"), ensure_ascii=False))
        return
    backlog_path = root / "backlog" / f"{plan_id}.json"
    if not backlog_path.exists():
        print(json.dumps(envelope(False, error="backlog not found"), ensure_ascii=False))
        return
    backlog, tasks = _load_backlog_tasks(backlog_path)
    tasks_by_id = {t.get("id"): t for t in tasks if t.get("id")}
    if task_id not in tasks_by_id:
        print(json.dumps(envelope(False, error="task not found in backlog"), ensure_ascii=False))
        return

    reset_ids = _collect_retry_ids(tasks_by_id, task_id, args.retry_deps)
    now = time.time()
    reason = {"type": "retry_reset", "run_id": args.run_id, "retry_deps": bool(args.retry_deps)}
    events = _reset_tasks_to_todo(tasks, reset_ids, reason, now)
    if events:
        append_state_events(root, events)
    backlog["tasks"] = tasks
    write_json(backlog_path, backlog)

    snapshot_path = root / "artifacts" / "executions" / plan_id / "snapshot.json"
    if snapshot_path.exists():
        snapshot = read_json(snapshot_path, default={})
        snap_tasks = snapshot.get("tasks", []) if isinstance(snapshot, dict) else []
        if isinstance(snap_tasks, list):
            _reset_tasks_to_todo(snap_tasks, reset_ids, reason, now)
            snapshot["tasks"] = snap_tasks
            snapshot["snapshot_ts"] = now
            write_json(snapshot_path, snapshot)

    workspace_arg = meta.get("workspace_main_root") or _resolve_plan_workspace(root, plan_id)
    mode = meta.get("mode") or "autopilot"
    exec_dir = root / "artifacts" / "executions" / plan_id
    before_run = find_latest_run(exec_dir)
    before_id = before_run.name if before_run else None
    cmd = ["python", "-m", "services.controller_service", "--root", str(root), "--plan-id", plan_id, "--mode", mode]
    if workspace_arg:
        cmd.extend(["--workspace", workspace_arg])
    subprocess.check_call(cmd, cwd=root)

    run_dir = find_latest_run(exec_dir)
    if not run_dir or (before_id and run_dir.name == before_id):
        print(json.dumps(envelope(False, error="no new run created"), ensure_ascii=False))
        return
    status = read_status(run_dir)
    data = {
        "run_id": run_dir.name,
        "plan_id": plan_id,
        "status": status.get("status"),
        "progress": status.get("progress"),
        "mode": status.get("mode"),
        "patchset_path": status.get("patchset_path"),
        "changed_files_count": status.get("changed_files_count"),
        "workspace_main_root": status.get("workspace_main_root"),
        "workspace_stage_root": status.get("workspace_stage_root"),
    }
    res = envelope(True, data=data)
    _mirror_run_to_sqlite(res, root)
    print(json.dumps(res, ensure_ascii=False))


# cmdstatus，序列化JSON
def cmd_assistant_chat(args, root: Path):
    if not args.messages_file:
        print(json.dumps(envelope(False, error="messages_file is required"), ensure_ascii=False))
        return
    messages_path = Path(args.messages_file)
    if not messages_path.exists():
        print(json.dumps(envelope(False, error="messages_file not found"), ensure_ascii=False))
        return
    payload = read_json(messages_path, default={})
    messages = payload.get("messages", []) if isinstance(payload, dict) else []
    if not isinstance(messages, list):
        messages = []

    workspace_path = None
    if hasattr(args, "workspace") and args.workspace:
        workspace_path = Path(args.workspace).resolve()

    workspace_context = _build_workspace_context(root, workspace_path)
    conversation = _format_conversation(messages)
    tmpl_path = root / "prompts" / "chat.txt"
    tmpl = tmpl_path.read_text(encoding="utf-8")
    prompt = tmpl.format(
        workspace_context=workspace_context,
        conversation=conversation,
    )
    raw_reply = run_codex_chat(prompt.strip(), root, workspace_path)
    reply = ""
    try:
        reply_obj = json.loads(_extract_last_json(raw_reply))
        reply = reply_obj.get("reply", "")
    except Exception:
        reply = raw_reply.strip()
    res = envelope(True, data={"reply": reply})
    print(json.dumps(res, ensure_ascii=False))


def cmd_status(args, root: Path):
    run_dir = resolve_run_dir(root, args.plan_id, args.run_id)
    if not run_dir:
        print(json.dumps(envelope(False, error="run not found"), ensure_ascii=False))
        return
    res = envelope(True, data=read_status(run_dir))
    _mirror_run_to_sqlite(res, root)
    print(json.dumps(res, ensure_ascii=False))


# cmdevents，解析JSON，序列化JSON
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


# cmdartifacts，序列化JSON
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



def load_backlog_map(root: Path) -> dict[str, list[dict]]:
    backlog_root = root / "backlog"
    if not backlog_root.exists():
        return {}

    backlog_map: dict[str, list[dict]] = {}
    for backlog_file in backlog_root.iterdir():
        if not backlog_file.is_file():
            continue
        try:
            backlog = read_json(backlog_file, default={})
        except Exception:
            continue
        tasks = backlog.get("tasks", []) if isinstance(backlog, dict) else []
        if not isinstance(tasks, list):
            continue
        for task in tasks:
            if not isinstance(task, dict):
                continue
            workspace = (
                task.get("workspace_path")
                or task.get("workspace")
                or task.get("workspace_main_root")
                or ""
            )
            backlog_map.setdefault(workspace, []).append(task)

    return backlog_map


def load_backlog_map_filtered(root: Path, workspace: str | None) -> dict[str, list[dict]]:
    if not workspace:
        return load_backlog_map(root)
    normalized_target = normalize_path(workspace)
    filtered: dict[str, list[dict]] = {}
    for ws, tasks in load_backlog_map(root).items():
        if not ws:
            continue
        if normalize_path(ws) == normalized_target:
            filtered[ws] = tasks
    return filtered


def cmd_dashboard_stats(args, root: Path):
    workspace = args.workspace
    plans = list_plans_for_workspace(root, workspace)
    plan_items = [
        {
            "plan_id": plan["plan_id"],
            "workspace": plan["workspace"],
            "tasks_count": plan["tasks_count"],
        }
        for plan in plans[:20]
    ]

    run_counts = count_runs_by_status(root, workspace)
    backlog_map = (
        load_backlog_map_filtered(root, workspace)
        if workspace
        else load_backlog_map(root)
    )
    all_tasks = [task for tasks in backlog_map.values() for task in tasks]
    tasks_by_status: dict[str, int] = {}
    for task in all_tasks:
        status = task.get("status") or "unknown"
        tasks_by_status[status] = tasks_by_status.get(status, 0) + 1

    data = {
        "workspace": workspace,
        "plans": {"total": len(plans), "items": plan_items},
        "runs": run_counts,
        "tasks": {"total": len(all_tasks), "by_status": tasks_by_status},
    }
    print(json.dumps(envelope(True, data=data), ensure_ascii=False))


# cmdcancel，写入文件内容，序列化JSON
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
    _mirror_run_to_sqlite(res, root)
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
    _mirror_run_to_sqlite(res, root)
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
    _mirror_run_to_sqlite(res, root)
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

            _mirror_run_to_sqlite(
                envelope(
                    True,
                    data={
                        "run_id": run_id,
                        "plan_id": args.plan_id,
                        "status": "canceled",
                        "workspace_main_root": meta.get("workspace_main_root", ""),
                    },
                ),
                root,
            )

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


# cmd档案，序列化JSON
# cmdrework?????
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
    _mirror_run_to_sqlite(res, root)
    print(json.dumps(res, ensure_ascii=False))


def cmd_profile(args, root: Path):
    profile_service = ProfileService()
    if not args.workspace:
        print(json.dumps(envelope(False, error="workspace is required"), ensure_ascii=False))
        return
    workspace = Path(args.workspace)
    action = args.action
    if action == "get":
        profile = profile_service.ensure_profile(root, workspace)
    elif action == "update":
        payload = _load_payload(args.payload)
        user_hard = payload.get("user_hard") if isinstance(payload, dict) else None
        if isinstance(payload, dict) and "user_hard" not in payload:
            user_hard = payload
        profile = profile_service.update_user_hard(root, workspace, user_hard if isinstance(user_hard, dict) else None)
    else:
        print(json.dumps(envelope(False, error="unknown action"), ensure_ascii=False))
        return

    effective_hard = profile.get("effective_hard")
    if effective_hard is None:
        effective_hard = ensure_profile(root, workspace).get("effective_hard")
    payload = {
        "workspace_id": profile.get("workspace_id"),
        "workspace_path": profile.get("workspace_path"),
        "fingerprint": profile.get("fingerprint"),
        "effective_hard": effective_hard,
        "system_hard": profile.get("system_hard"),
        "user_hard": profile.get("user_hard"),
    }
    res = envelope(True, data=payload)
    print(json.dumps(res, ensure_ascii=False))


def cmd_language_packs(args, root: Path):
    service = LanguagePackService(root)
    action = args.action
    if action == "list":
        ws_path = Path(args.workspace) if args.workspace else None
        project_type = None
        if ws_path:
            try:
                info = detect_workspace(ws_path)
                project_type = info.get("project_type") if isinstance(info, dict) else None
            except Exception:
                project_type = None
        data = service.list_packs(ws_path, project_type)
        print(json.dumps(envelope(True, data=data), ensure_ascii=False))
        return
    if action == "get":
        pack = service.export_pack(args.pack_id)
        if not pack:
            print(json.dumps(envelope(False, error="pack not found"), ensure_ascii=False))
            return
        print(json.dumps(envelope(True, data=pack), ensure_ascii=False))
        return
    if action == "import":
        payload = _load_payload(args.payload)
        if not payload:
            print(json.dumps(envelope(False, error="payload required"), ensure_ascii=False))
            return
        try:
            pack = service.import_pack(payload)
        except ValueError as err:
            print(json.dumps(envelope(False, error=str(err)), ensure_ascii=False))
            return
        payload = service.pack_to_dict(pack)
        print(json.dumps(envelope(True, data=payload), ensure_ascii=False))
        return
    if action == "export":
        pack = service.export_pack(args.pack_id)
        if not pack:
            print(json.dumps(envelope(False, error="pack not found"), ensure_ascii=False))
            return
        print(json.dumps(envelope(True, data=pack), ensure_ascii=False))
        return
    if action == "export-merged":
        pack = service.export_merged(args.pack_id, args.name or "", args.description or "")
        if not pack:
            print(json.dumps(envelope(False, error="pack not found"), ensure_ascii=False))
            return
        print(json.dumps(envelope(True, data=pack), ensure_ascii=False))
        return
    if action == "learned-export":
        pack = service.export_learned(args.name or "", args.description or "")
        if not pack:
            print(json.dumps(envelope(False, error="learned pack not found"), ensure_ascii=False))
            return
        print(json.dumps(envelope(True, data=pack), ensure_ascii=False))
        return
    if action == "delete":
        ok = service.delete_pack(args.pack_id)
        if not ok:
            print(json.dumps(envelope(False, error="pack not found"), ensure_ascii=False))
            return
        print(json.dumps(envelope(True, data={"deleted": True}), ensure_ascii=False))
        return
    if action == "update":
        pack = service.update_pack(args.pack_id, enabled=args.enabled)
        if not pack:
            print(json.dumps(envelope(False, error="pack not found"), ensure_ascii=False))
            return
        payload = service.pack_to_dict(pack)
        print(json.dumps(envelope(True, data=payload), ensure_ascii=False))
        return
    if action == "learned-clear":
        service.clear_learned()
        print(json.dumps(envelope(True, data={"cleared": True}), ensure_ascii=False))
        return
    print(json.dumps(envelope(False, error="unknown action"), ensure_ascii=False))


def cmd_memory(args, root: Path):
    workspace_id = _resolve_workspace_id(args.workspace_id, args.workspace)
    if not workspace_id:
        print(json.dumps(envelope(False, error="workspace_id is required"), ensure_ascii=False))
        return
    service = ExperiencePackService(root)
    data = service.get_memory(workspace_id)
    print(json.dumps(envelope(True, data=data), ensure_ascii=False))


def cmd_experience_packs(args, root: Path):
    workspace_id = _resolve_workspace_id(args.workspace_id, args.workspace)
    if not workspace_id:
        print(json.dumps(envelope(False, error="workspace_id is required"), ensure_ascii=False))
        return
    service = ExperiencePackService(root)
    action = args.action
    if action == "list":
        packs = [asdict(p) for p in service.list_packs(workspace_id)]
        print(json.dumps(envelope(True, data=packs), ensure_ascii=False))
        return
    if action == "get":
        pack = service.get_pack(workspace_id, args.pack_id)
        if not pack:
            print(json.dumps(envelope(False, error="pack not found"), ensure_ascii=False))
            return
        print(json.dumps(envelope(True, data=asdict(pack)), ensure_ascii=False))
        return
    if action == "import":
        payload = _load_payload(args.payload)
        if not payload:
            print(json.dumps(envelope(False, error="payload required"), ensure_ascii=False))
            return
        try:
            pack = service.import_pack(workspace_id, payload, source=payload.get("source", "file"))
        except ValueError as err:
            print(json.dumps(envelope(False, error=str(err)), ensure_ascii=False))
            return
        print(json.dumps(envelope(True, data=asdict(pack)), ensure_ascii=False))
        return
    if action == "import-workspace":
        pack = service.import_workspace(
            workspace_id,
            args.from_workspace_id,
            include_rules=bool(args.include_rules),
            include_checks=bool(args.include_checks),
            include_lessons=bool(args.include_lessons),
            include_patterns=bool(args.include_patterns),
        )
        print(json.dumps(envelope(True, data=asdict(pack)), ensure_ascii=False))
        return
    if action == "export":
        payload = service.export_pack(
            workspace_id,
            args.name or "",
            args.description or "",
            include_rules=bool(args.include_rules),
            include_checks=bool(args.include_checks),
            include_lessons=bool(args.include_lessons),
            include_patterns=bool(args.include_patterns),
        )
        print(json.dumps(envelope(True, data=payload), ensure_ascii=False))
        return
    if action == "delete":
        ok = service.delete_pack(workspace_id, args.pack_id)
        if not ok:
            print(json.dumps(envelope(False, error="pack not found"), ensure_ascii=False))
            return
        print(json.dumps(envelope(True, data={"deleted": True}), ensure_ascii=False))
        return
    if action == "update":
        pack = service.update_pack(workspace_id, args.pack_id, enabled=args.enabled)
        if not pack:
            print(json.dumps(envelope(False, error="pack not found"), ensure_ascii=False))
            return
        print(json.dumps(envelope(True, data=asdict(pack)), ensure_ascii=False))
        return
    print(json.dumps(envelope(False, error="unknown action"), ensure_ascii=False))


def cmd_rules(args, root: Path):
    workspace_id = _resolve_workspace_id(args.workspace_id, args.workspace)
    if not workspace_id:
        print(json.dumps(envelope(False, error="workspace_id is required"), ensure_ascii=False))
        return
    service = ExperiencePackService(root)
    if args.action == "add":
        rule = service.add_rule(workspace_id, args.content or "", args.scope, args.category)
        print(json.dumps(envelope(True, data=asdict(rule)), ensure_ascii=False))
        return
    if args.action == "delete":
        ok = service.delete_rule(workspace_id, args.rule_id)
        if not ok:
            print(json.dumps(envelope(False, error="rule not found"), ensure_ascii=False))
            return
        print(json.dumps(envelope(True, data={"deleted": True}), ensure_ascii=False))
        return
    print(json.dumps(envelope(False, error="unknown action"), ensure_ascii=False))


def cmd_checks(args, root: Path):
    workspace_id = _resolve_workspace_id(args.workspace_id, args.workspace)
    if not workspace_id:
        print(json.dumps(envelope(False, error="workspace_id is required"), ensure_ascii=False))
        return
    service = ExperiencePackService(root)
    if args.action == "add":
        payload = _load_payload(args.payload)
        if not payload:
            print(json.dumps(envelope(False, error="payload required"), ensure_ascii=False))
            return
        scope = payload.get("scope") if isinstance(payload, dict) else None
        if not scope:
            scope = args.scope
        check = service.add_check(workspace_id, payload.get("check", {}), scope)
        print(json.dumps(envelope(True, data=asdict(check)), ensure_ascii=False))
        return
    if args.action == "delete":
        ok = service.delete_check(workspace_id, args.check_id)
        if not ok:
            print(json.dumps(envelope(False, error="check not found"), ensure_ascii=False))
            return
        print(json.dumps(envelope(True, data={"deleted": True}), ensure_ascii=False))
        return
    print(json.dumps(envelope(False, error="unknown action"), ensure_ascii=False))


def cmd_lessons(args, root: Path):
    workspace_id = _resolve_workspace_id(args.workspace_id, args.workspace)
    if not workspace_id:
        print(json.dumps(envelope(False, error="workspace_id is required"), ensure_ascii=False))
        return
    service = ExperiencePackService(root)
    if args.action == "delete":
        count = service.delete_lesson(workspace_id, args.lesson_id)
        print(json.dumps(envelope(True, data={"deleted": count}), ensure_ascii=False))
        return
    if args.action == "clear":
        count = service.delete_lesson(workspace_id, None)
        print(json.dumps(envelope(True, data={"deleted": count}), ensure_ascii=False))
        return
    print(json.dumps(envelope(False, error="unknown action"), ensure_ascii=False))

# cmd代码图构建，序列化JSON
def cmd_code_graph_build(args, root: Path):
    code_graph_service = CodeGraphService(cache_root=root)
    workspace = Path(args.workspace)
    fingerprint = compute_fingerprint(workspace)
    graph = code_graph_service.build(workspace, fingerprint=fingerprint, watch=args.watch)
    graph_path = None
    if args.output:
        graph_path = Path(args.output)
        code_graph_service.save(graph, graph_path)
    data = {
        "workspace": str(workspace.resolve()),
        "fingerprint": fingerprint,
        "graph_path": str(graph_path) if graph_path else None,
        "graph": graph.to_dict(),
    }
    print(json.dumps(envelope(True, data=data), ensure_ascii=False))


# cmd代码图related，序列化JSON，检查路径是否存在
def cmd_code_graph_related(args, root: Path):
    code_graph_service = CodeGraphService(cache_root=root)
    workspace = Path(args.workspace)
    graph = None
    if args.graph:
        graph_path = Path(args.graph)
        if graph_path.exists():
            try:
                graph = code_graph_service.load(graph_path)
            except Exception:
                graph = None
    if not graph:
        fingerprint = compute_fingerprint(workspace)
        graph = code_graph_service.build(workspace, fingerprint=fingerprint)
    related = graph.related_files([args.file], max_hops=args.max_hops)
    data = {
        "file": args.file,
        "related_files": related,
    }
    print(json.dumps(envelope(True, data=data), ensure_ascii=False))


# 主入口，解析命令行参数
# cmdapply???patchset
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
    _mirror_run_to_sqlite(res, root)
    print(json.dumps(res, ensure_ascii=False))


# cmddiscard???patchset
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
    _mirror_run_to_sqlite(res, root)
    print(json.dumps(res, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="AIPL Engine CLI")
    parser.add_argument("--root", required=True, help="repo root path")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_plan = sub.add_parser("plan")
    p_plan.add_argument("--task", required=True)
    p_plan.add_argument("--plan-id")
    p_plan.add_argument("--workspace")
    p_plan.set_defaults(func=cmd_plan)

    p_run = sub.add_parser("run")
    p_run.add_argument("--task", required=True)
    p_run.add_argument("--plan-id")
    p_run.add_argument("--workspace")
    p_run.add_argument("--mode", default="autopilot", choices=["autopilot", "manual"])
    p_run.set_defaults(func=cmd_run)

    p_run_plan = sub.add_parser("run-plan")
    p_run_plan.add_argument("--plan-id", required=True)
    p_run_plan.add_argument("--workspace")
    p_run_plan.add_argument("--mode", default="autopilot", choices=["autopilot", "manual"])
    p_run_plan.set_defaults(func=cmd_run_plan)

    p_retry = sub.add_parser("retry")
    p_retry.add_argument("--plan-id")
    p_retry.add_argument("--run-id", required=True)
    p_retry.add_argument("--force", action="store_true")
    p_retry.add_argument("--retry-deps", action="store_true")
    p_retry.add_argument("--retry-id-suffix")
    p_retry.add_argument("--reuse-task-id", action="store_true")
    p_retry.set_defaults(func=cmd_retry)

    p_chat = sub.add_parser("assistant-chat")
    p_chat.add_argument("--messages-file", required=True)
    p_chat.add_argument("--workspace", help="workspace path (Codex will run here)")
    p_chat.set_defaults(func=cmd_assistant_chat)

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

    p_dashboard = sub.add_parser("dashboard-stats")
    p_dashboard.add_argument("--workspace")
    p_dashboard.set_defaults(func=cmd_dashboard_stats)

    p_cancel = sub.add_parser("cancel")
    p_cancel.add_argument("--plan-id")
    p_cancel.add_argument("--run-id")
    p_cancel.set_defaults(func=cmd_cancel)

    p_pause = sub.add_parser("pause")
    p_pause.add_argument("--plan-id")
    p_pause.add_argument("--run-id")
    p_pause.set_defaults(func=cmd_pause)

    p_resume = sub.add_parser("resume")
    p_resume.add_argument("--plan-id")
    p_resume.add_argument("--run-id")
    p_resume.set_defaults(func=cmd_resume)

    p_cancel_plan = sub.add_parser("cancel-plan-runs")
    p_cancel_plan.add_argument("--plan-id", required=True)
    p_cancel_plan.set_defaults(func=cmd_cancel_plan_runs)

    p_apply = sub.add_parser("apply")
    p_apply.add_argument("--plan-id")
    p_apply.add_argument("--run-id")
    p_apply.set_defaults(func=cmd_apply)

    p_discard = sub.add_parser("discard")
    p_discard.add_argument("--plan-id")
    p_discard.add_argument("--run-id")
    p_discard.set_defaults(func=cmd_discard)

    p_rework = sub.add_parser("rework")
    p_rework.add_argument("--plan-id")
    p_rework.add_argument("--run-id")
    p_rework.add_argument("--step-id")
    p_rework.add_argument("--feedback")
    p_rework.add_argument("--scope")
    p_rework.set_defaults(func=cmd_rework)

    p_profile = sub.add_parser("profile")
    p_profile.add_argument("--action", required=True, choices=["get", "update"])
    p_profile.add_argument("--workspace", required=True)
    p_profile.add_argument("--payload")
    p_profile.set_defaults(func=cmd_profile)

    p_lang = sub.add_parser("language-packs")
    p_lang.add_argument("--action", required=True, choices=["list", "get", "import", "export", "export-merged", "learned-export", "delete", "update", "learned-clear"])
    p_lang.add_argument("--pack-id")
    p_lang.add_argument("--payload")
    p_lang.add_argument("--name")
    p_lang.add_argument("--description")
    p_lang.add_argument("--enabled", type=int)
    p_lang.add_argument("--workspace")
    p_lang.set_defaults(func=cmd_language_packs)

    p_mem = sub.add_parser("memory")
    p_mem.add_argument("--workspace-id")
    p_mem.add_argument("--workspace")
    p_mem.set_defaults(func=cmd_memory)

    p_exp = sub.add_parser("experience-packs")
    p_exp.add_argument("--action", required=True, choices=["list", "get", "import", "import-workspace", "export", "delete", "update"])
    p_exp.add_argument("--workspace-id")
    p_exp.add_argument("--workspace")
    p_exp.add_argument("--pack-id")
    p_exp.add_argument("--payload")
    p_exp.add_argument("--name")
    p_exp.add_argument("--description")
    p_exp.add_argument("--enabled", type=int)
    p_exp.add_argument("--from-workspace-id")
    p_exp.add_argument("--include-rules", action="store_true")
    p_exp.add_argument("--include-checks", action="store_true")
    p_exp.add_argument("--include-lessons", action="store_true")
    p_exp.add_argument("--include-patterns", action="store_true")
    p_exp.set_defaults(func=cmd_experience_packs)

    p_rules = sub.add_parser("rules")
    p_rules.add_argument("--action", required=True, choices=["add", "delete"])
    p_rules.add_argument("--workspace-id")
    p_rules.add_argument("--workspace")
    p_rules.add_argument("--rule-id")
    p_rules.add_argument("--content")
    p_rules.add_argument("--scope")
    p_rules.add_argument("--category")
    p_rules.set_defaults(func=cmd_rules)

    p_checks = sub.add_parser("checks")
    p_checks.add_argument("--action", required=True, choices=["add", "delete"])
    p_checks.add_argument("--workspace-id")
    p_checks.add_argument("--workspace")
    p_checks.add_argument("--check-id")
    p_checks.add_argument("--payload")
    p_checks.add_argument("--scope")
    p_checks.set_defaults(func=cmd_checks)

    p_lessons = sub.add_parser("lessons")
    p_lessons.add_argument("--action", required=True, choices=["delete", "clear"])
    p_lessons.add_argument("--workspace-id")
    p_lessons.add_argument("--workspace")
    p_lessons.add_argument("--lesson-id")
    p_lessons.set_defaults(func=cmd_lessons)

    p_graph = sub.add_parser("code-graph")
    graph_sub = p_graph.add_subparsers(dest="graph_cmd", required=True)

    p_graph_build = graph_sub.add_parser("build")
    p_graph_build.add_argument("--workspace", required=True)
    p_graph_build.add_argument("--output")
    p_graph_build.add_argument("--watch", action="store_true")
    p_graph_build.set_defaults(func=cmd_code_graph_build)

    p_graph_related = graph_sub.add_parser("related")
    p_graph_related.add_argument("--workspace", required=True)
    p_graph_related.add_argument("--file", required=True)
    p_graph_related.add_argument("--graph")
    p_graph_related.add_argument("--max-hops", type=int, default=2)
    p_graph_related.set_defaults(func=cmd_code_graph_related)

    args = parser.parse_args()
    root = Path(args.root).resolve()
    args.func(args, root)


if __name__ == "__main__":
    main()
