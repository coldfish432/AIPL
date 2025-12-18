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
    """
    Non-interactive codex exec that returns a JSON response matching our schema.
    """
    schema_path = root_dir / "schemas" / "codex_writes.schema.json"

    cmd = [
        "codex", "exec",
        "--full-auto",
        "--sandbox", "workspace-write",
        "-C", str(root_dir),
        "--skip-git-repo-check",
        "--output-schema", str(schema_path),
        "--color", "never"
    ]

    result = subprocess.run(
        cmd,
        input=prompt,  # stdin prompt
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
    # 从 backlog.json 读取对应任务规格
    backlog = json.loads((root / "backlog.json").read_text(encoding="utf-8"))
    for t in backlog.get("tasks", []):
        if t.get("id") == task_id:
            return t
    return {}

def load_rework(run_dir: Path, step_id: str, round_id: int):
    # 读取上一轮的 rework 请求（若存在）
    if round_id <= 0:
        return None
    prev = run_dir / "steps" / step_id / f"round-{round_id-1}" / "rework_request.json"
    if prev.exists():
        return json.loads(prev.read_text(encoding="utf-8"))
    return None

def snapshot_outputs(outputs_dir: Path, max_chars_per_file: int = 4000) -> dict:
    # 收集 outputs/ 下文件文本内容（逐个截断至指定长度）
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
    # 只允许写入 outputs/ 路径，并返回生成的相对路径
    produced = []
    for w in writes:
        path = w.get("path", "")
        content = w.get("content", "")
        # 安全：只允许写 outputs/ 下
        if not path.startswith("outputs/"):
            continue
        out_path = run_dir / path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        produced.append(path)
    return produced

def main():
    """
    Usage:
      python scripts/subagent_shim.py <run_dir> <task_id> <step_id> <round_id> <mode>
    """
    # 解析 CLI 参数
    run_dir = Path(sys.argv[1])
    task_id = sys.argv[2]
    step_id = sys.argv[3]
    round_id_str = sys.argv[4]
    round_id = int(round_id_str)
    mode = sys.argv[5]

    # 准备本轮目录与输出目录
    round_dir = run_dir / "steps" / step_id / f"round-{round_id_str}"

    outputs_dir = run_dir / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    # 加载任务规格与验收标准
    root = Path(__file__).resolve().parent.parent  # 项目根目录
    task_spec = load_task_spec(root, task_id)
    acceptance = task_spec.get("acceptance_criteria", [])

    # 读取上一轮失败原因（若有）
    rework = load_rework(run_dir, step_id, round_id)
    why_failed = ""
    if rework and "why_failed" in rework:
        why_failed = "\n".join(rework["why_failed"])


    # 构造请求并记录开始事件
    req = {
        "task_id": task_id,
        "step": step_id,
        "round": round_id,
        "mode": mode,
        "ts": time.time()
    }

    write_json(round_dir / "create_request.json", req)
    append_jsonl(run_dir / "events.jsonl", {"type": "subagent_start", **req})

    stdout = ""

    if task_id == "T001":
        # 简单处理：写出 result.txt，区分好坏模式
        p = outputs_dir / "result.txt"
        if mode == "bad":
            p.write_text("WRONG OUTPUT\n", encoding="utf-8")
            stdout = "Wrote WRONG output"
        else:
            p.write_text("OK: deliverable generated\n", encoding="utf-8")
            stdout = "Wrote OK output"
    elif task_id == "T002":
        if mode == "bad":
            (outputs_dir / "summary.md").write_text("hello\n", encoding="utf-8")
            stdout = "Wrote incomplete summary"
        else:
            # T002 验收标准简单，直接本地写入，避免依赖外部 Codex
            summary = outputs_dir / "summary.md"
            summary.write_text(
                f"Task: {task_id}\nRun: {run_dir.name}\n\nSummary: auto-generated.\n",
                encoding="utf-8",
            )
            stdout = "Wrote local summary"

    elif task_id == "T003":
        # T003 è¦æ±‚åœ¨è·¯å¾„æ ¹ç”Ÿæˆ index.md æ»¡è¶³éªŒæ”¶
        idx = run_dir / "index.md"
        if mode == "bad":
            idx.write_text("# Wrong\n", encoding="utf-8")
            stdout = "Wrote wrong index"
        else:
            idx.write_text(
                "# Run Report\n\n## Evidence\n- meta.json\n- events.jsonl\n- outputs/\n",
                encoding="utf-8",
            )
            stdout = "Wrote correct index"

    elif mode == "good":
        # 通用修复器：根据验收标准 + 失败原因，生成 outputs/ 下的文件
        snap = snapshot_outputs(outputs_dir)

        # 向 Codex 请求 JSON 写入计划
        prompt = textwrap.dedent(f"""
        You are an automated fixing agent. Your job is to make the verifier pass.

        Context:
        - Task ID: {task_id}
        - Run: {run_dir.name}

        Acceptance criteria:
        {chr(10).join("- " + c for c in acceptance)}

        Verifier feedback (why_failed):
        {why_failed}

        Current outputs snapshot (path -> content, truncated):
        {json.dumps(snap, ensure_ascii=False)}

        Produce a JSON object with this exact schema:
        {{
          "writes": [
            {{"path": "outputs/<file>", "content": "<full file content>"}}
          ]
        }}

        Rules:
        - Return ONLY valid JSON. No markdown. No code fences. No commentary.
        - Only write under outputs/.
        - If a file must exist, include it in writes.
        - 文件内如需注释/提示语，优先使用简洁中文。
        """).strip()

        raw = run_codex(prompt, root).strip()

        # 解析 JSON（Codex 偶尔会输出前后空白，这里 trim 了）
        plan = json.loads(raw)
        writes = plan.get("writes", [])
        produced_paths = apply_writes(run_dir, writes)

        stdout = "Codex applied writes: " + ", ".join(produced_paths or ["<none>"])
    else:
        # 未匹配到处理逻辑的兜底
        stdout = f"No handler for task_id={task_id}"


    # 落盘本轮响应与日志
    write_json(round_dir / "shape_response.json", {
        "ok": True,
        "produced": [str(p.relative_to(run_dir)) for p in outputs_dir.glob("*")],
        "stdout_summary": stdout
    })

    (round_dir / "stdout.txt").write_text(stdout + "\n", encoding="utf-8")
    (round_dir / "stderr.txt").write_text("", encoding="utf-8")

    # 记录结束事件
    append_jsonl(run_dir / "events.jsonl", {
        "type": "subagent_done",
        "task_id": task_id,
        "step": step_id,
        "round": round_id,
        "mode": mode,
        "ts": time.time()
    })

if __name__ == "__main__":
    main()
