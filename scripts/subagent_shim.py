import argparse
import json
import subprocess
import time
from pathlib import Path


def write_json(path: Path, obj):
    # 将对象序列化成 JSON 文件，确保父目录存在
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def append_jsonl(path: Path, obj):
    # 以 JSONL 方式追加单行事件
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def run_codex(prompt: str, root_dir: Path) -> str:
    """调用 Codex，返回符合 schema 的 JSON 字符串"""
    schema_path = root_dir / "schemas" / "codex_writes.schema.json"
    cmd = [
        "codex", "exec",
        "--full-auto",
        "--sandbox", "workspace-write",
        "-C", str(root_dir),
        "--skip-git-repo-check",
        "--output-schema", str(schema_path),
        "--color", "never",
    ]
    result = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=True,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "codex failed").strip())
    return result.stdout


def load_task_spec(root: Path, task_id: str) -> dict:
    backlog = json.loads((root / "backlog.json").read_text(encoding="utf-8"))
    for t in backlog.get("tasks", []):
        if t.get("id") == task_id:
            return t
    return {}


def load_rework(run_dir: Path, step_id: str, round_id: int):
    if round_id <= 0:
        return None
    prev = run_dir / "steps" / step_id / f"round-{round_id-1}" / "rework_request.json"
    if prev.exists():
        return json.loads(prev.read_text(encoding="utf-8"))
    return None


def snapshot_outputs(outputs_dir: Path, max_chars_per_file: int = 4000) -> dict:
    snap = {}
    for p in outputs_dir.glob("**/*"):
        if p.is_file():
            rel = p.as_posix()
            try:
                txt = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                txt = ""
            snap[rel] = txt[:max_chars_per_file]
    return snap


def resolve_under(base: Path, rel_path: str) -> Path | None:
    rel_path = rel_path.replace("\\", "/")
    if rel_path.startswith("/") or rel_path.startswith("\\"):
        return None
    parts = Path(rel_path).parts
    if any(p == ".." for p in parts):
        return None
    dest = (base / rel_path).resolve()
    try:
        dest.relative_to(base.resolve())
    except Exception:
        return None
    return dest


def is_allowed(path: Path, allowlist: list[str], denylist: list[str]) -> bool:
    posix = path.as_posix()
    for d in denylist:
        if d and (posix == d or posix.startswith(d.rstrip("/") + "/")):
            return False
    if not allowlist:
        return True
    for a in allowlist:
        if a == "" or posix == a or posix.startswith(a.rstrip("/") + "/"):
            return True
    return False


def apply_writes(run_dir: Path, workspace: Path, writes: list[dict], allow_write: list[str], deny_write: list[str]) -> tuple[list[str], list[dict]]:
    produced = []
    skipped = []
    for w in writes:
        target = w.get("target", "run")
        rel_path = w.get("path", "")
        content = w.get("content", "")
        if target == "workspace":
            if rel_path.replace('\\', '/').startswith('outputs/') or rel_path in ("outputs", "outputs/"):
                skipped.append({"path": rel_path, "reason": "workspace_outputs_disabled"})
                continue
            dest = resolve_under(workspace, rel_path)
            if not dest or not is_allowed(dest.relative_to(workspace), allow_write, deny_write):
                skipped.append({"path": rel_path, "reason": "not_allowed"})
                continue
        else:
            dest = resolve_under(run_dir, rel_path)
            if not dest:
                skipped.append({"path": rel_path, "reason": "invalid_run_path"})
                continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        produced.append(f"{target}:{rel_path}")
    return produced, skipped


def run_commands(workspace: Path, commands, timeout_default: int = 300) -> tuple[list[dict], bool]:
    """
    执行允许的命令，cwd=workspace。commands 可以是字符串或 {cmd, timeout}。
    白名单前缀：python / pytest / mvn / gradle / npm / node / pnpm / yarn
    """
    allowed_prefix = ("python", "pytest", "mvn", "gradle", "npm", "node", "pnpm", "yarn")
    logs = []
    all_passed = True
    if not isinstance(commands, list):
        return [], True
    for cmd_item in commands:
        if isinstance(cmd_item, dict):
            cmd_str = cmd_item.get("cmd", "").strip()
            timeout = int(cmd_item.get("timeout", timeout_default) or timeout_default)
        else:
            cmd_str = str(cmd_item).strip()
            timeout = timeout_default
        if not cmd_str:
            continue
        if not cmd_str.startswith(allowed_prefix):
            logs.append({"cmd": cmd_str, "status": "skipped", "reason": "not_allowed_prefix"})
            all_passed = False
            continue
        try:
            result = subprocess.run(
                cmd_str,
                cwd=workspace,
                shell=True,
                timeout=timeout,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            log = {
                "cmd": cmd_str,
                "returncode": result.returncode,
                "stdout": (result.stdout or "")[:2000],
                "stderr": (result.stderr or "")[:2000],
            }
            logs.append(log)
            if result.returncode != 0:
                all_passed = False
        except subprocess.TimeoutExpired as e:
            logs.append({"cmd": cmd_str, "status": "timeout", "detail": str(e)})
            all_passed = False
    return logs, all_passed


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    parser.add_argument("task_id")
    parser.add_argument("step_id")
    parser.add_argument("round_id")
    parser.add_argument("mode")
    parser.add_argument("--workspace", help="目标 workspace 路径（若缺省则尝试 backlog.task.workspace.path）")
    return parser.parse_args()


def main():
    args = parse_args()
    run_dir = Path(args.run_dir)
    task_id = args.task_id
    step_id = args.step_id
    round_id_str = args.round_id
    round_id = int(round_id_str)
    mode = args.mode

    round_dir = run_dir / "steps" / step_id / f"round-{round_id_str}"
    outputs_dir = run_dir / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    root = Path(__file__).resolve().parent.parent
    task_spec = load_task_spec(root, task_id)
    acceptance = task_spec.get("acceptance_criteria", [])

    workspace_path = Path(args.workspace) if args.workspace else None
    if not workspace_path and isinstance(task_spec.get("workspace"), dict):
        wpath = task_spec["workspace"].get("path")
        if wpath:
            workspace_path = Path(wpath)
    if not workspace_path:
        raise RuntimeError("workspace path is required (use --workspace or task.workspace.path)")
    workspace_path = workspace_path.resolve()
    allow_write = []
    deny_write = [".git", "node_modules", "target", "dist", ".venv", "__pycache__", "outputs"]

    # 若存在 policy.json 或 workspace_config.json，则作为默认 allow/deny
    cfg_path = run_dir / "policy.json"
    if not cfg_path.exists():
        cfg_path = run_dir / "workspace_config.json"
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            allow_write = cfg.get("allow_write", allow_write) or allow_write
            deny_write = cfg.get("deny_write", deny_write) or deny_write
        except Exception:
            pass
    if "outputs" not in deny_write:
        deny_write.append("outputs")
    if isinstance(task_spec.get("workspace"), dict):
        allow_write = task_spec["workspace"].get("allow_write", []) or allow_write
        deny_write = task_spec["workspace"].get("deny_write", []) or deny_write

    rework = load_rework(run_dir, step_id, round_id)
    why_failed = ""
    prev_stdout = ""
    if rework:
        prev = rework.get("why_failed", "")
        if isinstance(prev, list):
            try:
                why_failed = json.dumps(prev, ensure_ascii=False, indent=2)
            except Exception:
                why_failed = str(prev)
        else:
            why_failed = str(prev)
        prev_stdout = rework.get("prev_stdout", "")

    req = {
        "task_id": task_id,
        "step": step_id,
        "round": round_id,
        "mode": mode,
        "ts": time.time(),
        "workspace": str(workspace_path),
    }
    write_json(round_dir / "create_request.json", req)
    append_jsonl(run_dir / "events.jsonl", {"type": "subagent_start", **req})

    snap = snapshot_outputs(outputs_dir)
    acceptance_block = "\n".join("- " + c for c in acceptance) if acceptance else "- (none provided)"
    tmpl = (root / "prompts" / "subagent_fix.txt").read_text(encoding="utf-8")
    prompt = tmpl.format(
        task_id=task_id,
        run_name=run_dir.name,
        acceptance_block=acceptance_block,
        why_failed=why_failed,
        prev_stdout=prev_stdout,
        snap_json=json.dumps(snap, ensure_ascii=False),
        workspace=str(workspace_path),
    )

    raw = run_codex(prompt, root).strip()
    plan = json.loads(raw)
    writes = plan.get("writes", [])
    produced_paths, skipped_writes = apply_writes(run_dir, workspace_path, writes, allow_write, deny_write)

    cmd_logs = []
    cmds = plan.get("commands", [])
    if isinstance(cmds, list) and cmds:
        cmd_logs, cmds_ok = run_commands(workspace_path, cmds)
    else:
        cmds_ok = True

    stdout_lines = []
    stdout_lines.append("Codex applied writes: " + ", ".join(produced_paths or ["<none>"]))
    if skipped_writes:
        for s in skipped_writes:
            stdout_lines.append(f"[skip_write] {s.get('path')} reason={s.get('reason')}")
    if cmd_logs:
        for log in cmd_logs:
            status = "ok" if log.get("returncode", 0) == 0 else log.get("status", "failed")
            stdout_lines.append(f"[cmd] {log.get('cmd')} status={status} rc={log.get('returncode', '')}")
    stdout = "\n".join(stdout_lines)

    write_json(round_dir / "shape_response.json", {
        "ok": True,
        "produced": [str(p.relative_to(run_dir)) for p in outputs_dir.glob("*")],
        "stdout_summary": stdout,
        "commands": cmd_logs,
        "skipped_writes": skipped_writes,
    })
    (round_dir / "stdout.txt").write_text(stdout + "\n", encoding="utf-8")
    (round_dir / "stderr.txt").write_text("", encoding="utf-8")

    append_jsonl(run_dir / "events.jsonl", {
        "type": "subagent_done",
        "task_id": task_id,
        "step": step_id,
        "round": round_id,
        "mode": mode,
        "ts": time.time(),
    })


if __name__ == "__main__":
    main()
