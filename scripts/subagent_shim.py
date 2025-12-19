import json
import sys
import time
import subprocess
import textwrap
from pathlib import Path


def write_json(path: Path, obj):
    # 将对象序列化到 JSON 文件，确保父目录存在
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def append_jsonl(path: Path, obj):
    # 以 JSONL 形式追加单行事件
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def run_codex(prompt: str, root_dir: Path) -> str:
    # 调用 Codex，返回符合 schema 的 JSON 字符串
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


def apply_writes(run_dir: Path, writes: list[dict]) -> list[str]:
    # 写入 run_dir 内的指定路径，防止越界
    produced = []
    for w in writes:
        path = w.get("path", "")
        content = w.get("content", "")
        out_path = (run_dir / path).resolve()
        if not str(out_path).startswith(str(run_dir.resolve())):
            continue
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        produced.append(path)
    return produced


def run_commands(run_dir: Path, commands: list[str], timeout: int = 120) -> tuple[list[dict], bool]:
    """
    执行允许的命令，收集输出。返回 (logs, all_passed)
    仅允许前缀为 python 的命令（如 python -m pytest / python scripts/check.py / python -m pip check）。
    """
    logs = []
    all_passed = True
    for cmd in commands:
        cmd_str = cmd.strip()
        if not cmd_str:
            continue
        if not cmd_str.startswith("python"):
            logs.append({"cmd": cmd_str, "status": "skipped", "reason": "not in allowed prefix"})
            all_passed = False
            continue
        try:
            result = subprocess.run(
                cmd_str,
                cwd=run_dir,
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


def main():
    # CLI 参数：run_dir task_id step_id round_id mode
    run_dir = Path(sys.argv[1])
    task_id = sys.argv[2]
    step_id = sys.argv[3]
    round_id_str = sys.argv[4]
    round_id = int(round_id_str)
    mode = sys.argv[5]

    round_dir = run_dir / "steps" / step_id / f"round-{round_id_str}"
    outputs_dir = run_dir / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    root = Path(__file__).resolve().parent.parent
    task_spec = load_task_spec(root, task_id)
    acceptance = task_spec.get("acceptance_criteria", [])

    rework = load_rework(run_dir, step_id, round_id)
    why_failed = ""
    prev_stdout = ""
    if rework:
        prev = rework.get("why_failed", "")
        if isinstance(prev, list):
            try:
                why_failed = json.dumps(prev, ensure_ascii=False)
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
    )

    raw = run_codex(prompt, root).strip()
    plan = json.loads(raw)
    writes = plan.get("writes", [])
    produced_paths = apply_writes(run_dir, writes)

    cmd_logs = []
    cmds = plan.get("commands", [])
    if isinstance(cmds, list) and cmds:
        cmd_logs, cmds_ok = run_commands(run_dir, cmds)
    else:
        cmds_ok = True

    stdout_lines = []
    stdout_lines.append("Codex applied writes: " + ", ".join(produced_paths or ["<none>"]))
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
