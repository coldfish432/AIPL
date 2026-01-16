from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Iterable, List

from .models import DiagnosisReport, ErrorSignature, FailureCategory, FixAttempt


class DiagnosisReporter:
    def __init__(self, root: Path) -> None:
        self.root = root

    def generate(
        self,
        run_dir: Path,
        task_id: str,
        round_id: int,
        failure_context: dict[str, Any],
    ) -> DiagnosisReport:
        round_history = self._load_round_history(run_dir)
        error_sig = self._build_signature(failure_context)
        fix_attempts = [
            FixAttempt(
                round_id=failure_context.get("round", round_id),
                action_type="verification",
                action_detail=failure_context.get("error_summary", ""),
                success=False,
                side_effects=[],
            )
        ]
        report = DiagnosisReport(
            task_id=task_id,
            run_id=run_dir.parent.name,
            round_id=round_id,
            timestamp=time.time(),
            error_signature=error_sig,
            root_cause_analysis=self._build_root_cause(failure_context, round_history),
            contributing_factors=self._build_contributing_factors(failure_context),
            fix_attempts=fix_attempts,
            successful_fix=self._truncate(failure_context.get("fix_guidance") or ""),
            suggested_prevention=self._truncate(failure_context.get("fix_guidance") or ""),
            learnable=True,
            confidence=0.5,
            generalizability="medium",
            affected_files=failure_context.get("produced_files") or [],
            related_commands=self._collect_failed_commands(failure_context),
            tags=[str(f.get("type")) for f in failure_context.get("why_failed", []) if isinstance(f, dict)],
        )
        self._save_reports(run_dir, round_id, report, round_history, failure_context)
        return report

    def _build_signature(self, failure_context: dict[str, Any]) -> ErrorSignature:
        reasons = failure_context.get("why_failed", []) or []
        error_type = ""
        error_message = failure_context.get("error_summary", "") or ""
        if reasons:
            first = reasons[0]
            error_type = first.get("type", "") or error_message
            error_message = first.get("message", error_message)
        category = self._deduce_category(error_type, failure_context)
        stack = failure_context.get("execution_errors", {}).get("error_summary", "")
        return ErrorSignature(
            category=category,
            error_type=error_type or "unknown",
            error_message=error_message or stack or "Unknown failure",
            file_path=self._infer_file_path(reasons),
            line_number=None,
            stack_trace_summary=stack,
        )

    def _deduce_category(self, error_type: str, failure_context: dict[str, Any]) -> FailureCategory:
        if "syntax" in error_type.lower():
            return FailureCategory.SYNTAX_ERROR
        if "import" in error_type.lower() or "module" in error_type.lower():
            return FailureCategory.DEPENDENCY_ERROR
        if "timeout" in error_type.lower():
            return FailureCategory.TIMEOUT_ERROR
        if "permission" in error_type.lower():
            return FailureCategory.PERMISSION_ERROR
        if failure_context.get("error_summary", "").lower().startswith("environment"):
            return FailureCategory.ENVIRONMENT_ERROR
        if "runtime" in error_type.lower() or "failed" in error_type.lower():
            return FailureCategory.RUNTIME_ERROR
        return FailureCategory.UNKNOWN

    def _infer_file_path(self, reasons: Iterable[dict[str, Any]]) -> str | None:
        for reason in reasons:
            candidate = reason.get("file") or reason.get("path")
            if isinstance(candidate, str) and candidate:
                return candidate
        return None

    def _build_root_cause(self, failure_context: dict[str, Any], history: list[dict[str, Any]]) -> str:
        lines = []
        reasons = failure_context.get("why_failed", []) or []
        for reason in reasons:
            desc = reason.get("reason") or reason.get("type")
            if desc:
                lines.append(str(desc))
        if not lines:
            lines.append(failure_context.get("error_summary", "No structured failure details"))
        return "; ".join(lines)

    def _build_contributing_factors(self, failure_context: dict[str, Any]) -> list[str]:
        return [str(r.get("type") or r.get("reason") or "unknown") for r in failure_context.get("why_failed", []) or []]

    def _collect_failed_commands(self, failure_context: dict[str, Any]) -> list[str]:
        errors = failure_context.get("execution_errors", {}).get("failed_commands", [])
        commands = []
        for err in errors:
            cmd = err.get("cmd")
            if isinstance(cmd, str) and cmd.strip():
                commands.append(cmd.strip())
        return commands

    def _truncate(self, value: str, max_len: int = 400) -> str:
        return value[:max_len] if value else ""

    def _save_reports(
        self,
        run_dir: Path,
        round_id: int,
        diagnosis: DiagnosisReport,
        round_history: list[dict[str, Any]],
        failure_context: dict[str, Any],
    ) -> None:
        round_dir = run_dir / "rounds" / str(round_id)
        round_dir.mkdir(parents=True, exist_ok=True)

        machine_report = {
            "task_id": diagnosis.task_id,
            "run_id": diagnosis.run_id,
            "round_id": diagnosis.round_id,
            "timestamp": diagnosis.timestamp,
            "error_signature": {
                "category": diagnosis.error_signature.category.value,
                "error_type": diagnosis.error_signature.error_type,
                "error_message": diagnosis.error_signature.error_message,
                "file_path": diagnosis.error_signature.file_path,
                "line_number": diagnosis.error_signature.line_number,
                "stack_trace_summary": diagnosis.error_signature.stack_trace_summary,
            },
            "root_cause_analysis": diagnosis.root_cause_analysis,
            "contributing_factors": diagnosis.contributing_factors,
            "fix_attempts": [
                {
                    "round_id": fa.round_id,
                    "action_type": fa.action_type,
                    "action_detail": fa.action_detail,
                    "success": fa.success,
                    "side_effects": fa.side_effects,
                }
                for fa in diagnosis.fix_attempts
            ],
            "successful_fix": diagnosis.successful_fix,
            "suggested_prevention": diagnosis.suggested_prevention,
            "learnable": diagnosis.learnable,
            "confidence": diagnosis.confidence,
            "generalizability": diagnosis.generalizability,
            "affected_files": diagnosis.affected_files,
            "related_commands": diagnosis.related_commands,
            "tags": diagnosis.tags,
        }

        (round_dir / "diagnosis.json").write_text(
            json.dumps(machine_report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        human_report = self._format_human_report(diagnosis, round_history, failure_context)
        (run_dir / "failure_report.json").write_text(
            json.dumps(human_report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _format_human_report(
        self,
        diagnosis: DiagnosisReport,
        round_history: list[dict[str, Any]],
        failure_context: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "summary": {
                "one_line": f"[{diagnosis.error_signature.category.value}] {diagnosis.error_signature.error_message[:120]}",
                "total_rounds": len(round_history) + 1,
                "error_type": diagnosis.error_signature.error_type,
                "severity": self._assess_severity(diagnosis),
            },
            "root_cause": diagnosis.root_cause_analysis,
            "contributing_factors": diagnosis.contributing_factors,
            "recommendations": {
                "prevention": diagnosis.suggested_prevention,
                "for_human": self._generate_human_recommendations(diagnosis),
            },
            "timeline": [
                {
                    "round": i + 1,
                    "action": rd.get("action_summary", ""),
                    "result": "success" if rd.get("passed") else "failed",
                }
                for i, rd in enumerate(round_history)
            ],
            "affected_files": diagnosis.affected_files,
            "tags": diagnosis.tags,
        }

    def _assess_severity(self, diagnosis: DiagnosisReport) -> str:
        category = diagnosis.error_signature.category
        if category in {FailureCategory.SYNTAX_ERROR, FailureCategory.DEPENDENCY_ERROR}:
            return "medium"
        if category in {FailureCategory.PERMISSION_ERROR, FailureCategory.ENVIRONMENT_ERROR, FailureCategory.UNKNOWN}:
            return "high"
        return "low"

    def _generate_human_recommendations(self, diagnosis: DiagnosisReport) -> List[str]:
        recommendations: List[str] = []
        if diagnosis.error_signature.category == FailureCategory.DEPENDENCY_ERROR:
            recommendations.append("检查依赖项是否安装并正确配置。")
        if diagnosis.error_signature.category == FailureCategory.ENVIRONMENT_ERROR:
            recommendations.append("确认执行环境与项目要求一致。")
        if diagnosis.error_signature.category == FailureCategory.PERMISSION_ERROR:
            recommendations.append("检查文件或目录的权限设置。")
        if diagnosis.generalizability == "low":
            recommendations.append("此问题较为特定，可能需要人工分析。")
        return recommendations or ["请参考执行日志排查错误。"]

    def _load_round_history(self, run_dir: Path) -> list[dict[str, Any]]:
        rounds_dir = run_dir / "rounds"
        if not rounds_dir.exists():
            return []
        history: list[dict[str, Any]] = []
        for round_dir in sorted(rounds_dir.iterdir()):
            if not round_dir.is_dir():
                continue
            entry: dict[str, Any] = {}
            response_file = round_dir / "response.json"
            if response_file.exists():
                try:
                    entry.update(json.loads(response_file.read_text(encoding="utf-8")))
                except Exception:
                    pass
            rework_file = round_dir / "rework_request.json"
            if rework_file.exists():
                try:
                    entry["rework"] = json.loads(rework_file.read_text(encoding="utf-8"))
                except Exception:
                    pass
            if entry:
                history.append(entry)
        return history
