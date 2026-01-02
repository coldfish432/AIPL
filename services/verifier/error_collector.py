from __future__ import annotations

from pathlib import Path

from .config import EXECUTION_CHECK_TYPES
from .types import ExecutionError, ExecutionErrors
from .utils import extract_key_error_lines


def _build_error_summary(errors: list[ExecutionError]) -> str:
    lines = []
    for err in errors:
        cmd = err.cmd or "(unknown)"
        status = err.status or "failed"
        lines.append(f"{cmd} -> {status} (exit={err.exit_code})")
        if err.key_errors:
            lines.append(err.key_errors)
    return "\n".join(lines)


def collect_execution_errors(check_results: list[dict], log_dir: Path) -> ExecutionErrors:
    errors = ExecutionErrors()
    for result in check_results:
        if result.get("type") not in EXECUTION_CHECK_TYPES:
            continue
        if result.get("ok") is True:
            continue
        errors.has_errors = True
        idx = result.get("index", 0)
        stdout = ""
        stderr = ""
        stdout_path = log_dir / f"cmd-{idx}.stdout.txt"
        stderr_path = log_dir / f"cmd-{idx}.stderr.txt"
        if stdout_path.exists():
            stdout = stdout_path.read_text(encoding="utf-8", errors="replace")
        if stderr_path.exists():
            stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
        key_errors = extract_key_error_lines(stderr + "\n" + stdout)
        errors.failed_commands.append(
            ExecutionError(
                cmd=result.get("cmd"),
                exit_code=result.get("exit_code"),
                status=result.get("status"),
                stdout=stdout[-3000:],
                stderr=stderr[-3000:],
                key_errors=key_errors,
            )
        )
    errors.error_summary = _build_error_summary(errors.failed_commands)
    return errors


def generate_fix_guidance(reasons: list[dict], errors: ExecutionErrors) -> str:
    guidance = []
    if errors.has_errors:
        guidance.append("## 代码执行失败")
        guidance.append("")
        guidance.append("请分析以下错误信息并修复代码：")
        guidance.append("")
        guidance.append("```")
        guidance.append(errors.error_summary[:2000])
        guidance.append("```")
        guidance.append("")
        guidance.append("### 修复建议")
        guidance.append("1. 检查语法错误")
        guidance.append("2. 确保变量/函数名正确")
        guidance.append("3. 验证导入的模块存在")
        guidance.append("4. 检查函数参数类型和数量")
    elif reasons:
        guidance.append("## 验证失败")
        guidance.append("")
        guidance.append("请根据验证原因修复后重试。")
    return "\n".join(guidance)
