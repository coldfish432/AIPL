from pathlib import Path

def verify_task(run_dir: Path, task_id: str):
    # 根据 task_id 校验 outputs/ 或 index.md 是否符合验收标准
    reasons = []

    if task_id == "T001":
        # 检查 deliverable 文件及内容
        result = run_dir / "outputs" / "result.txt"
        if not result.exists():
            reasons.append("Missing outputs/result.txt")
            return False, reasons
        content = result.read_text(encoding="utf-8").strip("\n")
        if content != "OK: deliverable generated":
            reasons.append(f"result.txt content mismatch: got={content!r}")
            return False, reasons
        return True, reasons

    if task_id == "T002":
        # 检查 summary.md 是否包含 Task/Run 字段
        summary = run_dir / "outputs" / "summary.md"
        if not summary.exists():
            reasons.append("Missing outputs/summary.md")
            return False, reasons
        text = summary.read_text(encoding="utf-8")
        if "Task:" not in text or "Run:" not in text:
            reasons.append("summary.md missing required fields: Task/Run")
            return False, reasons
        return True, reasons

    if task_id == "T003":
        # 检查 index.md 是否含 Evidence 段落
        idx = run_dir / "index.md"
        if not idx.exists():
            reasons.append("Missing index.md")
            return False, reasons
        text = idx.read_text(encoding="utf-8")
        if "## Evidence" not in text:
            reasons.append("index.md missing '## Evidence'")
            return False, reasons
        return True, reasons

    reasons.append(f"Unknown task_id: {task_id}")
    return False, reasons
