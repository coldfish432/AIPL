"""
上下文收集 Sub Agent
负责收集任务执行所需的上下文信息
"""
import json
from pathlib import Path
from typing import Any

from .base import BaseAgent, AgentResult, load_json_file


class ContextAgent(BaseAgent):
    """
    上下文收集 Agent
    
    功能：
    - 收集 graph seeds（相关文件路径）
    - 获取 related files（代码图分析）
    - 获取 hints 和 lessons（学习存储）
    - 加载 rework 信息
    """
    
    def __init__(self, root: Path, run_dir: Path, workspace: Path = None):
        super().__init__(root, run_dir)
        self.workspace = workspace
        
        # 延迟导入
        self._graph_service = None
        self._learning_storage = None
    
    def _get_graph_service(self):
        """懒加载代码图服务"""
        if self._graph_service is None:
            from services.code_graph_service import CodeGraphService
            self._graph_service = CodeGraphService(cache_root=self.root)
        return self._graph_service
    
    def _get_learning_storage(self):
        """懒加载学习存储"""
        if self._learning_storage is None and self.workspace:
            from engine.learning.storage import LearningStorage
            self._learning_storage = LearningStorage(self.workspace)
        return self._learning_storage
    
    def run(
        self,
        checks: list[dict] = None,
        rework: dict = None,
        include_graph: bool = True,
        include_learning: bool = True,
    ) -> AgentResult:
        """
        收集上下文信息
        
        Args:
            checks: 检查项列表
            rework: 返工信息
            include_graph: 是否包含代码图信息
            include_learning: 是否包含学习信息
        
        Returns:
            AgentResult，data 中包含收集的上下文
        """
        context = {
            "graph_seeds": [],
            "related_files": [],
            "missing_suggestions": [],
            "hints": [],
            "lessons": [],
        }
        
        # 收集 graph seeds
        seeds = self._collect_graph_seeds(checks or [], rework)
        context["graph_seeds"] = seeds
        
        # 获取代码图信息
        if include_graph and self.workspace and seeds:
            graph_service = self._get_graph_service()
            context["related_files"] = graph_service.get_related_files(
                self.workspace,
                seeds,
                include_co_changes=True,
            )
            
            # 获取缺失文件建议
            modified_files = []
            if rework and isinstance(rework.get("produced_files"), list):
                modified_files = [p for p in rework["produced_files"] if isinstance(p, str)]
            
            if rework and isinstance(rework.get("missing_suggestions"), list):
                context["missing_suggestions"] = rework["missing_suggestions"]
            else:
                context["missing_suggestions"] = graph_service.suggest_missing_files(
                    self.workspace,
                    modified_files=modified_files,
                    min_confidence=0.7,
                )
        
        # 获取学习信息
        if include_learning and self.workspace and self.workspace.exists():
            storage = self._get_learning_storage()
            if storage:
                context["hints"] = storage.get_hints(scope="fix")
                context["lessons"] = storage.get_lessons(limit=5)
        
        return AgentResult(ok=True, data=context)
    
    def _collect_graph_seeds(self, checks: list[dict], rework: dict = None) -> list[str]:
        """收集代码图种子路径"""
        seeds = []
        
        # 从检查项提取路径
        seeds.extend(self._extract_paths_from_checks(checks))
        
        if rework:
            # 从失败原因提取路径
            if isinstance(rework.get("why_failed"), list):
                seeds.extend(self._extract_paths_from_reasons(rework["why_failed"]))
            
            # 从可疑相关文件提取
            suspected = rework.get("suspected_related_files")
            if isinstance(suspected, list):
                for item in suspected:
                    if isinstance(item, str) and item.strip():
                        seeds.append(item.strip())
        
        return [s for s in seeds if s]
    
    def _extract_paths_from_checks(self, checks: list[dict]) -> list[str]:
        """从检查项提取路径"""
        paths = []
        for check in checks or []:
            if not isinstance(check, dict):
                continue
            value = check.get("path")
            if isinstance(value, str) and value.strip():
                paths.append(value.strip())
        return paths
    
    def _extract_paths_from_reasons(self, reasons: list) -> list[str]:
        """从失败原因提取路径"""
        paths = []
        for reason in reasons or []:
            if not isinstance(reason, dict):
                continue
            for key in ("file", "path"):
                value = reason.get(key)
                if isinstance(value, str) and value.strip():
                    paths.append(value.strip())
        return paths
    
    def format_related_files(self, related: list[dict]) -> str:
        """格式化相关文件列表"""
        if not related:
            return "- (none)"
        lines = []
        for item in related:
            file_path = item.get("file")
            if not file_path:
                continue
            relation = item.get("relation", "related")
            confidence = item.get("confidence")
            if isinstance(confidence, (int, float)):
                lines.append(f"- {file_path} ({relation}, confidence: {confidence:.2f})")
            else:
                lines.append(f"- {file_path} ({relation})")
        return "\n".join(lines) if lines else "- (none)"
    
    def format_missing_suggestions(self, suggestions: list[dict]) -> str:
        """格式化缺失文件建议"""
        if not suggestions:
            return "- (none)"
        lines = []
        for item in suggestions:
            file_path = item.get("file")
            if not file_path:
                continue
            confidence = item.get("confidence")
            reason = item.get("reason", "co_change")
            if isinstance(confidence, (int, float)):
                lines.append(f"- {file_path} (confidence: {confidence:.2f}, reason: {reason})")
            else:
                lines.append(f"- {file_path} (reason: {reason})")
        return "\n".join(lines) if lines else "- (none)"
    
    def format_hints(self, hints: list[dict]) -> str:
        """格式化提示列表"""
        if not hints:
            return "- (none yet)"
        return "\n".join(
            f"- {h.get('hint')} (trigger: {h.get('trigger_signature')})"
            for h in hints
        )
    
    def format_lessons(self, lessons: list[dict]) -> str:
        """格式化经验列表"""
        if not lessons:
            return "- (none yet)"
        return "\n".join(
            f"- {l.get('content')}"
            for l in lessons
            if l.get("content")
        )


def load_task_spec(root: Path, task_id: str) -> dict:
    """
    加载任务规格
    
    Args:
        root: 引擎根目录
        task_id: 任务 ID
    
    Returns:
        任务规格字典
    """
    backlog_dir = root / "backlog"
    if not backlog_dir.exists():
        return {}
    
    for path in sorted(backlog_dir.glob("*.json")):
        data = load_json_file(path, default={})
        for t in data.get("tasks", []):
            if t.get("id") == task_id:
                return t
    return {}


def load_rework(run_dir: Path, step_id: str, round_id: int) -> dict | None:
    """
    加载返工请求
    
    Args:
        run_dir: 运行目录
        step_id: 步骤 ID
        round_id: 轮次 ID
    
    Returns:
        返工请求字典，如果不存在返回 None
    """
    if round_id <= 0:
        return None
    prev = run_dir / "steps" / step_id / f"round-{round_id-1}" / "rework_request.json"
    if prev.exists():
        return load_json_file(prev, default=None)
    return None
