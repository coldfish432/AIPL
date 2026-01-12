from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
import uuid
from pathlib import Path

from detect_workspace import detect_workspace
from infra.codex_runner import decode_output, find_codex_bin
from infra.fields import get_workspace
from infra.io_utils import read_json
from infra.json_utils import read_json_dict
from infra.status import is_running, is_terminal
from services.controller.workspace import auto_select_workspace
from services.profile_service import compute_workspace_id
from workspace_utils import get_backlog_dir, get_plan_dir, normalize_workspace_path, find_plan_workspace


def _extract_last_json(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in reversed(lines):
        if line.startswith("{") or line.startswith("["):
            return line
    return text.strip()


def _format_conversation(messages: list[dict]) -> str:
    lines: list[str] = []
    for msg in messages:
        role = str(msg.get("role", "user")).strip().lower()
        content = str(msg.get("content", "")).strip()
        if not content:
            continue
        label = "User" if role == "user" else "Assistant"
        lines.append(f"{label}: {content}")
    return "\n".join(lines)


def _workspace_has_context(info: dict | None) -> bool:
    if not isinstance(info, dict):
        return False
    if info.get("project_type") != "unknown":
        return True
    if info.get("checks"):
        return True
    capabilities = info.get("capabilities")
    if isinstance(capabilities, dict):
        if capabilities.get("detected"):
            return True
        if capabilities.get("commands"):
            return True
    return False


def _resolve_workspace_target(root: Path, workspace_path: Path | None) -> Path | None:
    if workspace_path:
        try:
            candidate = workspace_path.resolve()
        except Exception:
            return None
        if candidate.exists() and candidate.is_dir():
            return candidate
        return None

    env_workspace = os.getenv("AIPL_DEFAULT_WORKSPACE")
    if env_workspace:
        try:
            candidate = Path(env_workspace).expanduser()
            if not candidate.is_absolute():
                candidate = (root / candidate).resolve()
            candidate = candidate.resolve()
        except Exception:
            candidate = None
        if candidate and candidate.exists() and candidate.is_dir():
            return candidate

    try:
        candidate = auto_select_workspace(root)
    except Exception:
        return None
    if not candidate or not candidate.exists() or not candidate.is_dir():
        return None
    info = detect_workspace(candidate)
    if _workspace_has_context(info):
        return candidate
    return None


def run_codex_chat(prompt: str, root_dir: Path, workspace: Path | None = None) -> str:
    schema_path = (root_dir / "schemas" / "chat.schema.json").resolve()
    codex_bin = find_codex_bin()
    work_dir = str(workspace.resolve()) if workspace else str(root_dir)
    cmd = [
        str(codex_bin or "codex"), "exec", "--full-auto",
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
        err = decode_output(result.stderr or result.stdout or b"")
        raise RuntimeError((err or "codex failed").strip())
    return decode_output(result.stdout or b"").strip()


def _build_workspace_context(root: Path, workspace_path: Path | None, resolved_workspace: Path | None = None) -> str:
    workspace_path = resolved_workspace or _resolve_workspace_target(root, workspace_path)
    if not workspace_path:
        return "No workspace configured. Please set a workspace path first."
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

    key_files_content: list[str] = []
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


def envelope(ok: bool, data=None, error=None) -> dict:
    return {
        "ok": ok,
        "ts": int(time.time()),
        "trace_id": f"trc_{uuid.uuid4().hex[:12]}",
        "data": data,
        "error": error,
    }


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
    if not run_id:
        return None

    ws_root = root / "artifacts" / "workspaces"
    if not ws_root.exists():
        return None

    if plan_id:
        for ws_dir in ws_root.iterdir():
            if not ws_dir.is_dir():
                continue
            plan_dir = ws_dir / "executions" / plan_id
            if not plan_dir.exists():
                continue
            run_dir = plan_dir / "runs" / run_id
            if run_dir.exists():
                return run_dir
        return None

    for ws_dir in ws_root.iterdir():
        if not ws_dir.is_dir():
            continue
        exec_dir = ws_dir / "executions"
        if not exec_dir.exists():
            continue
        for plan_dir in exec_dir.iterdir():
            if not plan_dir.is_dir():
                continue
            run_dir = plan_dir / "runs" / run_id
            if run_dir.exists():
                return run_dir
    return None


def _resolve_plan_workspace(root: Path, plan_id: str) -> str | None:
    if not plan_id:
        return None
    return find_plan_workspace(root, plan_id)


def list_plans_for_workspace(root: Path, workspace: str | None) -> list[dict]:
    workspace_normalized = normalize_workspace_path(workspace) if workspace else None
    ws_root = root / "artifacts" / "workspaces"
    if not ws_root.exists():
        return []

    plans: list[dict] = []
    for ws_dir in ws_root.iterdir():
        if not ws_dir.is_dir():
            continue
        exec_dir = ws_dir / "executions"
        if not exec_dir.exists():
            continue
        for plan_dir in exec_dir.iterdir():
            if not plan_dir.is_dir():
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
            plan_workspace = plan_data.get("workspace_path") or plan_data.get("workspace_main_root")
            if workspace_normalized:
                plan_workspace_normalized = normalize_workspace_path(plan_workspace) if plan_workspace else None
                if plan_workspace_normalized != workspace_normalized:
                    continue
            activities = plan_data.get("raw_plan", {}).get("tasks", [])
            tasks_count = len(activities) if isinstance(activities, list) else 0
            plans.append(
                {
                    "plan_id": plan_dir.name,
                    "workspace": plan_workspace,
                    "created_ts": plan_data.get("created_ts"),
                    "task_chain_text": plan_data.get("task_chain_text"),
                    "tasks_count": tasks_count,
                }
            )

    return sorted(plans, key=lambda x: x.get("created_ts") or 0, reverse=True)


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
    round_id = None
    reasons: list[str] = []
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
                meta = read_json_dict(meta_path)
                workspace_value = get_workspace(meta)
                run_info.update(
                    {
                        "status": meta.get("status"),
                        "workspace": workspace_value,
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
    workspace_normalized = normalize_workspace_path(workspace) if workspace else None
    ws_root = root / "artifacts" / "workspaces"
    if not ws_root.exists():
        return []

    all_runs: list[dict] = []
    for ws_dir in ws_root.iterdir():
        if not ws_dir.is_dir():
            continue
        execs_dir = ws_dir / "executions"
        if not execs_dir.exists():
            continue
        for plan_dir in execs_dir.iterdir():
            if not plan_dir.is_dir():
                continue
            runs_dir = plan_dir / "runs"
            if not runs_dir.exists():
                continue
            for run_dir in runs_dir.iterdir():
                if not run_dir.is_dir():
                    continue
                run_workspace = None
                run_info = {
                    "run_id": run_dir.name,
                    "run_dir": str(run_dir),
                    "plan_id": plan_dir.name,
                }
                meta_path = run_dir / "meta.json"
                if meta_path.exists():
                    meta = read_json(meta_path, default={})
                    run_workspace = (
                        meta.get("workspace_main_root")
                        or meta.get("workspace_stage_root")
                        or meta.get("workspace")
                    )
                    run_info.update(
                        {
                            "status": meta.get("status"),
                            "workspace": run_workspace,
                            "task_id": meta.get("task_id"),
                            "created_at": meta.get("ts"),
                            "updated_at": meta.get("updated_at"),
                        }
                    )
                if workspace_normalized:
                    candidate = normalize_workspace_path(run_workspace) if run_workspace else None
                    if candidate != workspace_normalized:
                        continue
                all_runs.append(run_info)

    return sorted(all_runs, key=lambda x: x.get("run_id", ""), reverse=True)


def count_runs_by_status(root: Path, workspace: str | None) -> dict:
    runs = list_runs_for_workspace(root, workspace)

    counts = {
        "total": len(runs),
        "running": 0,
        "completed": 0,
        "failed": 0,
        "awaiting_review": 0,
    }

    for run in runs:
        raw_status = run.get("status") or ""
        status = raw_status.lower()
        if is_running(status):
            counts["running"] += 1
        elif status == "failed":
            counts["failed"] += 1
        elif status == "awaiting_review":
            counts["awaiting_review"] += 1
        elif is_terminal(status):
            counts["completed"] += 1

    return counts


def list_artifacts(run_dir: Path) -> list[dict]:
    items: list[dict] = []
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
