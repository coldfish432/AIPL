import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
import sys


# extractroot
def _extract_root(argv: list[str]) -> Path | None:
    for idx, arg in enumerate(argv):
        if arg == "--root" and idx + 1 < len(argv):
            return Path(argv[idx + 1])
    return None


ROOT_DIR = _extract_root(sys.argv)
if not ROOT_DIR:
    raise RuntimeError("--root is required (pass --root <repo_root>)")
ROOT_DIR = ROOT_DIR.resolve()
sys.path.insert(0, str(ROOT_DIR))

from infra.io_utils import append_jsonl, write_json
from policy_validator import validate_writes, validate_commands, default_path_rules
from services.profile_service import ensure_profile, DEFAULT_ALLOWED_COMMANDS, DEFAULT_COMMAND_TIMEOUT, DEFAULT_DENY_WRITE
from services.code_graph_service import CodeGraph


# 调用 Codex，返回符合 schema 的 JSON 字符串
def run_codex(prompt: str, root_dir: Path) -> str:
    """调用 Codex，返回符合 schema 的 JSON 字符串"""
    schema_path = root_dir / "schemas" / "codex_writes.schema.json"
    codex_bin = os.environ.get("CODEX_BIN") or shutil.which("codex")
    if not codex_bin and os.name == "nt":
        for cand in ("codex.cmd", "codex.exe", "codex.bat"):
            codex_bin = shutil.which(cand)
            if codex_bin:
                break
    codex_bin = codex_bin or "codex"
    cmd = [
        codex_bin, "exec",
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
        shell=False,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "codex failed").strip())
    return result.stdout


# 加载任务spec，解析JSON，检查路径是否存在
def load_task_spec(root: Path, task_id: str) -> dict:
    backlog_dir = root / "backlog"
    if not backlog_dir.exists():
        return {}
    for path in sorted(backlog_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for t in data.get("tasks", []):
            if t.get("id") == task_id:
                return t
    return {}


# 加载rework，检查路径是否存在，解析JSON
def load_rework(run_dir: Path, step_id: str, round_id: int):
    if round_id <= 0:
        return None
    prev = run_dir / "steps" / step_id / f"round-{round_id-1}" / "rework_request.json"
    if prev.exists():
        return json.loads(prev.read_text(encoding="utf-8"))
    return None


# extract路径from原因
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


# extract路径from检查项
def _extract_paths_from_checks(checks: list[dict]) -> list[str]:
    paths: list[str] = []
    for check in checks or []:
        if not isinstance(check, dict):
            continue
        value = check.get("path")
        if isinstance(value, str) and value.strip():
            paths.append(value.strip())
    return paths


# 加载代码图，解析JSON，检查路径是否存在
def _load_code_graph(root: Path, run_dir: Path) -> CodeGraph | None:
    meta_path = run_dir / "meta.json"
    if not meta_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    plan_id = meta.get("plan_id")
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
        return CodeGraph.load(graph_path)
    except Exception:
        return None


# summarizerelatedfiles，读取文件内容，检查路径是否存在
def _summarize_related_files(graph: CodeGraph, seed_paths: list[str], max_files: int = 20, max_lines: int = 200) -> str:
    related = graph.related_files(seed_paths, max_hops=2)
    if not related:
        return "none"
    blocks = []
    count = 0
    for rel_path in related:
        if count >= max_files:
            break
        abs_path = graph.workspace_root / rel_path
        if not abs_path.exists() or not abs_path.is_file():
            continue
        try:
            text = abs_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        snippet = "\n".join(text.splitlines()[:max_lines])
        blocks.append(f"[file] {rel_path}\n{snippet}")
        count += 1
    return "\n\n".join(blocks) if blocks else "none"


# snapshot输出，读取文件内容
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


# 解析under
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


# 判断是否allowed
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


# applywrites，写入文件内容，创建目录
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


# 执行允许的命令，cwd=workspace。commands 可以是字符串或 {cmd, timeout}
def run_commands(workspace: Path, commands, timeout_default: int = 300, allowed_prefix: tuple[str, ...] = tuple(DEFAULT_ALLOWED_COMMANDS)) -> tuple[list[dict], bool]:
    """
    执行允许的命令，cwd=workspace。commands 可以是字符串或 {cmd, timeout}。
    白名单前缀：python / pytest / mvn / gradle / npm / node / pnpm / yarn
    """
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


# 解析参数，解析命令行参数
def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, help="repo root path")
    parser.add_argument("run_dir")
    parser.add_argument("task_id")
    parser.add_argument("step_id")
    parser.add_argument("round_id")
    parser.add_argument("mode")
    parser.add_argument("--workspace", help="目标 workspace 路径（若缺省则尝试 backlog.task.workspace.path）")
    return parser.parse_args()


# 主入口，写入文件内容，追加记录
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

    root = Path(args.root).resolve()
    task_spec = load_task_spec(root, task_id)
    acceptance = task_spec.get("acceptance_criteria", [])
    checks = task_spec.get("checks", [])

    workspace_path = Path(args.workspace) if args.workspace else None
    if not workspace_path and isinstance(task_spec.get("workspace"), dict):
        wpath = task_spec["workspace"].get("path")
        if wpath:
            workspace_path = Path(wpath)
    if not workspace_path:
        raise RuntimeError("workspace path is required (use --workspace or task.workspace.path)")
    workspace_path = workspace_path.resolve()
    allow_write = []
    deny_write = list(DEFAULT_DENY_WRITE)
    allowed_commands = list(DEFAULT_ALLOWED_COMMANDS)
    command_timeout = DEFAULT_COMMAND_TIMEOUT

    # 若存在 policy.json 或 workspace_config.json，则作为默认 allow/deny
    cfg_path = run_dir / "policy.json"
    if not cfg_path.exists():
        cfg_path = run_dir / "workspace_config.json"
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            allow_write = cfg.get("allow_write", allow_write) or allow_write
            deny_write = cfg.get("deny_write", deny_write) or deny_write
            allowed_commands = cfg.get("allowed_commands", allowed_commands) or allowed_commands
            command_timeout = int(cfg.get("command_timeout", command_timeout) or command_timeout)
        except Exception:
            pass
    if "outputs" not in deny_write:
        deny_write.append("outputs")
    profile = ensure_profile(root, workspace_path)
    effective_hard = profile.get("effective_hard") or {}
    allow_write = effective_hard.get("allow_write", allow_write) or allow_write
    deny_write = effective_hard.get("deny_write", deny_write) or deny_write
    allowed_commands = effective_hard.get("allowed_commands", allowed_commands) or allowed_commands
    command_timeout = int(effective_hard.get("command_timeout", command_timeout) or command_timeout)

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
    checks_block = json.dumps(checks, ensure_ascii=False, indent=2) if checks else "[]"
    tmpl = (root / "prompts" / "subagent_fix.txt").read_text(encoding="utf-8")
    related_files_block = "none"
    graph = _load_code_graph(root, run_dir)
    if graph:
        seed_paths = []
        seed_paths.extend(_extract_paths_from_checks(checks))
        if rework and isinstance(rework.get("why_failed"), list):
            seed_paths.extend(_extract_paths_from_reasons(rework.get("why_failed", [])))
        if rework and isinstance(rework.get("suspected_related_files"), list):
            seed_paths.extend([p for p in rework.get("suspected_related_files", []) if isinstance(p, str)])
        normalized = [graph.normalize_path(p) for p in seed_paths]
        normalized = [p for p in normalized if p]
        if normalized:
            related_files_block = _summarize_related_files(graph, normalized)
    hard_block = json.dumps(
        {
            "allow_write": allow_write,
            "deny_write": deny_write,
            "allowed_commands": allowed_commands,
            "command_timeout": command_timeout,
            "max_concurrency": effective_hard.get("max_concurrency"),
            "path_rules": default_path_rules(),
        },
        ensure_ascii=False,
        indent=2,
    )
    soft_approved = profile.get("soft_approved")
    soft_block = json.dumps(soft_approved, ensure_ascii=False, indent=2) if soft_approved else "none"
    prompt = tmpl.format(
        task_id=task_id,
        run_name=run_dir.name,
        acceptance_block=acceptance_block,
        checks_block=checks_block,
        why_failed=why_failed,
        prev_stdout=prev_stdout,
        snap_json=json.dumps(snap, ensure_ascii=False),
        related_files_block=related_files_block,
        workspace=str(workspace_path),
        hard_block=hard_block,
        soft_block=soft_block,
    )

    raw = run_codex(prompt, root).strip()
    plan = json.loads(raw)
    writes = plan.get("writes", [])
    cleaned_writes, write_reasons = validate_writes(writes, allow_write, deny_write)
    produced_paths, skipped_writes = apply_writes(run_dir, workspace_path, cleaned_writes, allow_write, deny_write)

    cmd_logs = []
    cmds = plan.get("commands", [])
    cleaned_cmds, command_reasons = validate_commands(cmds, allowed_commands, command_timeout)
    if cleaned_cmds:
        cmd_logs, cmds_ok = run_commands(workspace_path, cleaned_cmds, timeout_default=command_timeout, allowed_prefix=tuple(allowed_commands))
    else:
        cmds_ok = True

    stdout_lines = []
    stdout_lines.append("Codex applied writes: " + ", ".join(produced_paths or ["<none>"]))
    if skipped_writes:
        for s in skipped_writes:
            stdout_lines.append(f"[skip_write] {s.get('path')} reason={s.get('reason')}")
    if write_reasons or command_reasons:
        for r in write_reasons + command_reasons:
            stdout_lines.append(f"[validation] {json.dumps(r, ensure_ascii=False)}")
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
        "validation_reasons": write_reasons + command_reasons,
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
