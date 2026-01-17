"""
失败报告 Sub Agent
在任务失败后调用 Codex 生成人类可读的中文失败报告
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

from .base import (
    BaseAgent,
    AgentResult,
    init_root,
    load_json_file,
    write_json_file,
    append_event,
)
from .codex_agent import CodexAgent


# 错误类型中文映射
ERROR_TYPE_MAPPING = {
    "verification_failed": "验证失败",
    "check_failed": "检查未通过",
    "test_failed": "测试失败",
    "syntax_error": "语法错误",
    "runtime_error": "运行时错误",
    "timeout": "执行超时",
    "dependency_error": "依赖错误",
    "file_not_found": "文件未找到",
    "permission_denied": "权限不足",
    "command_failed": "命令执行失败",
    "output_mismatch": "输出不匹配",
    "assertion_error": "断言失败",
    "import_error": "导入错误",
    "type_error": "类型错误",
    "value_error": "值错误",
}


class ReportAgent(BaseAgent):
    """
    失败报告 Agent
    
    功能：
    - 调用 Codex 生成中文失败摘要
    - 提供降级方案（规则生成）
    - 格式化输出供前端显示
    """
    
    def __init__(self, root: Path, run_dir: Path, timeout: int = 60):
        super().__init__(root, run_dir)
        self.timeout = timeout
    
    def run(
        self,
        task_id: str,
        checks: list[dict] = None,
        reasons: list[dict] = None,
        round_id: int = 0,
        error_summary: str = "",
    ) -> AgentResult:
        """
        生成失败报告
        
        Args:
            task_id: 任务 ID
            checks: 检查项列表
            reasons: 失败原因列表
            round_id: 失败轮次
            error_summary: 错误摘要
        
        Returns:
            AgentResult，data 中包含 report 和 meta 字段
        """
        checks = checks or []
        reasons = reasons or []
        
        report_dir = self.run_dir / "failure_report"
        report_dir.mkdir(parents=True, exist_ok=True)
        
        # 记录请求
        write_json_file(report_dir / "request.json", {
            "task_id": task_id,
            "round_id": round_id,
            "error_summary": error_summary,
            "checks": checks,
            "reasons": reasons,
            "ts": time.time(),
        })
        
        # 尝试调用 Codex 生成报告
        report = self._generate_with_codex(task_id, checks, reasons, report_dir)
        
        if not report:
            # Codex 失败，使用降级方案
            report = self._generate_fallback(task_id, checks, reasons)
            report["source"] = "fallback"
        else:
            report["source"] = "codex"
        
        # 保存报告
        write_json_file(report_dir / "report.json", report)
        
        # 格式化供 meta.json 使用
        meta = self._format_for_meta(report, reasons, round_id)
        
        return AgentResult(ok=True, data={"report": report, "meta": meta})
    
    def _generate_with_codex(
        self,
        task_id: str,
        checks: list[dict],
        reasons: list[dict],
        report_dir: Path,
    ) -> dict | None:
        """使用 Codex 生成报告"""
        tmpl_path = self.root / "prompts" / "failure_summary.txt"
        if not tmpl_path.exists():
            return None
        
        tmpl = tmpl_path.read_text(encoding="utf-8")
        prompt = tmpl.format(
            task_id=task_id,
            checks_json=json.dumps(checks, ensure_ascii=False, indent=2),
            reasons_json=json.dumps(reasons, ensure_ascii=False, indent=2),
        )
        
        (report_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
        
        try:
            codex_agent = CodexAgent(
                self.root, self.run_dir,
                idle_timeout=self.timeout,
                hard_timeout=self.timeout * 2,
            )
            result = codex_agent.run(
                prompt, report_dir,
                schema_name="codex_writes.schema.json",
                sandbox="none",
            )
            
            if not result.ok:
                return None
            
            response = result.data.get("response", "")
            (report_dir / "raw_response.txt").write_text(response, encoding="utf-8")
            
            return self._extract_json(response)
            
        except Exception as exc:
            (report_dir / "error.txt").write_text(str(exc), encoding="utf-8")
            return None
    
    def _extract_json(self, text: str) -> dict | None:
        """从响应中提取 JSON"""
        if not text:
            return None
        
        # 直接解析
        try:
            result = json.loads(text)
            if "summary_zh" in result:
                return result
        except json.JSONDecodeError:
            pass
        
        # 移除 markdown 代码块
        text = re.sub(r'^```json\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'^```\s*$', '', text, flags=re.MULTILINE)
        
        # 匹配包含 summary_zh 的 JSON
        match = re.search(r'\{[^{}]*"summary_zh"[^{}]*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        
        return None
    
    def _generate_fallback(
        self,
        task_id: str,
        checks: list[dict],
        reasons: list[dict],
    ) -> dict:
        """降级方案：使用规则生成报告"""
        if not reasons:
            return {
                "summary_zh": "任务执行失败，未能获取详细原因",
                "details_zh": "请查看执行日志获取更多信息",
            }
        
        # 提取第一个原因作为摘要
        first = reasons[0] if reasons else {}
        r_type = first.get("type", "")
        r_text = first.get("reason", "") or first.get("detail", "") or first.get("message", "")
        
        type_zh = ERROR_TYPE_MAPPING.get(r_type.lower(), r_type or "未知错误")
        
        summary = f"{type_zh}"
        if r_text:
            if len(r_text) > 80:
                r_text = r_text[:80] + "..."
            summary += f"：{r_text}"
        
        # 生成详细信息
        details_lines = []
        for i, r in enumerate(reasons[:5], 1):
            r_type = r.get("type", "unknown")
            r_text = r.get("reason", "") or r.get("detail", "") or r.get("message", "")
            r_path = r.get("path", "") or r.get("file", "")
            
            type_zh = ERROR_TYPE_MAPPING.get(r_type.lower(), r_type)
            line = f"{i}. [{type_zh}] {r_text}"
            if r_path:
                line += f"\n   文件: {r_path}"
            details_lines.append(line)
        
        if checks:
            details_lines.append("\n相关检查项：")
            for check in checks[:3]:
                check_type = check.get("type", "check")
                check_cmd = check.get("cmd", check.get("command", ""))
                if check_cmd:
                    details_lines.append(f"  - [{check_type}] {check_cmd}")
        
        return {
            "summary_zh": summary,
            "details_zh": "\n".join(details_lines) if details_lines else "请查看执行日志获取更多信息",
        }
    
    def _format_for_meta(
        self,
        report: dict,
        reasons: list[dict],
        round_id: int,
    ) -> dict:
        """格式化供 meta.json 使用"""
        failure_details = []
        for reason in reasons:
            if isinstance(reason, dict):
                failure_details.append({
                    "type": reason.get("type", ""),
                    "reason": (
                        reason.get("reason", "") or
                        reason.get("detail", "") or
                        reason.get("message", "")
                    ),
                    "path": reason.get("path", "") or reason.get("file", ""),
                })
        
        return {
            "failure_reason": report.get("summary_zh", ""),
            "failure_reason_detail": report.get("details_zh", ""),
            "failure_details": failure_details,
            "failure_round": round_id,
        }


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description="Report Agent - 失败报告 Sub Agent")
    parser.add_argument("--root", required=True, help="引擎根目录")
    parser.add_argument("--run-dir", required=True, help="运行目录")
    parser.add_argument("--task-id", required=True, help="任务 ID")
    parser.add_argument("--failure-context-file", help="失败上下文 JSON 文件路径")
    parser.add_argument("--checks-file", help="检查项 JSON 文件路径")
    parser.add_argument("--reasons-file", help="失败原因 JSON 文件路径")
    parser.add_argument("--round-id", type=int, default=0, help="失败轮次")
    parser.add_argument("--error-summary", default="", help="错误摘要")
    parser.add_argument("--timeout", type=int, default=60, help="超时时间（秒）")
    
    args = parser.parse_args()
    root = init_root()
    run_dir = Path(args.run_dir).resolve()
    
    # 加载数据
    checks = []
    reasons = []
    error_summary = args.error_summary
    round_id = args.round_id
    
    if args.failure_context_file and Path(args.failure_context_file).exists():
        ctx = load_json_file(Path(args.failure_context_file), default={})
        checks = ctx.get("checks", [])
        reasons = ctx.get("why_failed", [])
        error_summary = error_summary or ctx.get("error_summary", "")
        round_id = round_id or ctx.get("round", 0)
    
    if args.checks_file and Path(args.checks_file).exists():
        checks = load_json_file(Path(args.checks_file), default=[])
    
    if args.reasons_file and Path(args.reasons_file).exists():
        reasons = load_json_file(Path(args.reasons_file), default=[])
    
    # 运行 Agent
    agent = ReportAgent(root, run_dir, timeout=args.timeout)
    result = agent.run(
        task_id=args.task_id,
        checks=checks,
        reasons=reasons,
        round_id=round_id,
        error_summary=error_summary,
    )
    
    print(result.to_json())


if __name__ == "__main__":
    main()
