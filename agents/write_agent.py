"""
文件写入 Sub Agent
负责将 Codex 生成的文件写入到 workspace 或 run 目录
"""
import json
from pathlib import Path
from typing import Any

from .base import BaseAgent, AgentResult, resolve_path_under, is_path_allowed


class WriteAgent(BaseAgent):
    """
    文件写入 Agent
    
    功能：
    - 验证写入路径
    - 应用文件写入
    - 记录跳过的写入
    """
    
    def __init__(
        self,
        root: Path,
        run_dir: Path,
        workspace: Path,
        allow_write: list[str] = None,
        deny_write: list[str] = None,
        enforce_policy: bool = True,
    ):
        super().__init__(root, run_dir)
        self.workspace = workspace
        self.allow_write = allow_write or []
        self.deny_write = deny_write or []
        self.enforce_policy = enforce_policy
    
    def run(self, writes: list[dict]) -> AgentResult:
        """
        执行文件写入
        
        Args:
            writes: 写入列表，每项包含 {target, path, content}
        
        Returns:
            AgentResult，data 中包含 produced 和 skipped 字段
        """
        produced = []
        skipped = []
        
        for w in writes:
            target = w.get("target", "run")
            rel_path = w.get("path", "")
            content = w.get("content", "")
            
            if target == "workspace":
                result = self._write_to_workspace(rel_path, content)
            else:
                result = self._write_to_run(rel_path, content)
            
            if result.get("ok"):
                produced.append(f"{target}:{rel_path}")
            else:
                skipped.append({"path": rel_path, "reason": result.get("reason")})
        
        return AgentResult(
            ok=True,
            data={
                "produced": produced,
                "skipped": skipped,
                "total_writes": len(writes),
                "success_count": len(produced),
                "skip_count": len(skipped),
            }
        )
    
    def _write_to_workspace(self, rel_path: str, content: str) -> dict:
        """写入到 workspace"""
        # 禁止写入 workspace 的 outputs 目录
        normalized = rel_path.replace('\\', '/')
        if normalized.startswith('outputs/') or normalized in ("outputs", "outputs/"):
            return {"ok": False, "reason": "workspace_outputs_disabled"}
        
        dest = resolve_path_under(self.workspace, rel_path)
        if not dest:
            return {"ok": False, "reason": "invalid_workspace_path"}
        
        if self.enforce_policy:
            try:
                rel_to_ws = dest.relative_to(self.workspace)
                if not is_path_allowed(rel_to_ws, self.allow_write, self.deny_write):
                    return {"ok": False, "reason": "not_allowed"}
            except Exception:
                return {"ok": False, "reason": "path_check_failed"}
        
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "reason": f"write_failed: {exc}"}
    
    def _write_to_run(self, rel_path: str, content: str) -> dict:
        """写入到 run 目录"""
        dest = resolve_path_under(self.run_dir, rel_path)
        if not dest:
            return {"ok": False, "reason": "invalid_run_path"}
        
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "reason": f"write_failed: {exc}"}


def snapshot_directory(directory: Path, max_chars_per_file: int = 4000) -> dict:
    """
    快照目录内容
    
    Args:
        directory: 目录路径
        max_chars_per_file: 每个文件最大字符数
    
    Returns:
        {relative_path: content} 的字典
    """
    snap = {}
    if not directory.exists():
        return snap
    
    for p in directory.glob("**/*"):
        if p.is_file():
            rel = p.as_posix()
            try:
                txt = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                txt = ""
            snap[rel] = txt[:max_chars_per_file]
    return snap


def apply_writes_simple(
    run_dir: Path,
    workspace: Path,
    writes: list[dict],
    allow_write: list[str] = None,
    deny_write: list[str] = None,
    enforce_policy: bool = True,
) -> tuple[list[str], list[dict]]:
    """
    简单的文件写入函数（兼容原有接口）
    
    Returns:
        (produced_paths, skipped_writes)
    """
    # 这里不需要 root，创建一个临时的
    agent = WriteAgent(
        root=run_dir.parent,
        run_dir=run_dir,
        workspace=workspace,
        allow_write=allow_write or [],
        deny_write=deny_write or [],
        enforce_policy=enforce_policy,
    )
    result = agent.run(writes)
    return result.data.get("produced", []), result.data.get("skipped", [])
