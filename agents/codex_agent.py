"""
Codex 调用 Sub Agent
负责调用 Codex CLI 并处理响应
"""
import json
import time
from pathlib import Path

from .base import BaseAgent, AgentResult, append_event


class CodexAgent(BaseAgent):
    """
    Codex 调用 Agent
    
    功能：
    - 调用 Codex CLI 执行提示词
    - 处理超时和错误
    - 记录执行过程
    """
    
    def __init__(
        self,
        root: Path,
        run_dir: Path,
        idle_timeout: int = 120,
        hard_timeout: int = 1800,
    ):
        super().__init__(root, run_dir)
        self.idle_timeout = idle_timeout
        self.hard_timeout = hard_timeout
        
        # 延迟导入，确保 sys.path 已设置
        from infra.codex_runner import (
            CodexHardTimeout,
            CodexIdleTimeout,
            run_codex_with_files,
        )
        self._CodexHardTimeout = CodexHardTimeout
        self._CodexIdleTimeout = CodexIdleTimeout
        self._run_codex_with_files = run_codex_with_files
    
    def run(
        self,
        prompt: str,
        round_dir: Path,
        schema_name: str = "codex_writes.schema.json",
        sandbox: str = "workspace-write",
    ) -> AgentResult:
        """
        执行 Codex 调用
        
        Args:
            prompt: 提示词
            round_dir: 轮次目录
            schema_name: schema 文件名
            sandbox: 沙箱模式
        
        Returns:
            AgentResult，data 中包含 response 字段
        """
        schema_path = self.root / "schemas" / schema_name
        io_root = self.root / ".tmp_custom" / "codex_io"
        
        append_event(self.run_dir, {
            "type": "codex_start",
            "ts": time.time(),
            "round_dir": str(round_dir),
        })
        
        round_dir.mkdir(parents=True, exist_ok=True)
        status_path = round_dir / "codex_status.txt"
        heartbeat_path = round_dir / "codex_heartbeat.txt"
        heartbeat_path.write_text(str(time.time()), encoding="utf-8")
        
        # 保存提示词用于调试
        (round_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
        
        last_stderr_ts = [0.0]
        
        def on_stderr(line: str):
            if not line or not line.strip():
                return
            now = time.time()
            if now - last_stderr_ts[0] < 0.5:
                return
            last_stderr_ts[0] = now
            append_event(self.run_dir, {
                "type": "codex_output",
                "ts": now,
                "round_dir": str(round_dir),
                "message": line[:500],
            })
        
        def on_activity(ts: float):
            heartbeat_path.write_text(str(ts), encoding="utf-8")
        
        try:
            response = self._run_codex_with_files(
                prompt,
                self.root,
                schema_path,
                io_dir=io_root,
                work_dir=self.root,
                sandbox=sandbox,
                idle_timeout=self.idle_timeout,
                hard_timeout=self.hard_timeout,
                on_stderr=on_stderr,
                on_activity=on_activity,
            )
            
            append_event(self.run_dir, {
                "type": "codex_done",
                "ts": time.time(),
                "round_dir": str(round_dir),
            })
            status_path.write_text("Codex done\n", encoding="utf-8")
            
            # 保存响应
            (round_dir / "codex_response.txt").write_text(response, encoding="utf-8")
            
            return AgentResult(ok=True, data={"response": response.strip()})
            
        except self._CodexIdleTimeout as exc:
            append_event(self.run_dir, {
                "type": "codex_stale",
                "ts": time.time(),
                "round_dir": str(round_dir),
                "error": "codex_idle_timeout",
                "detail": str(exc),
            })
            status_path.write_text(f"Codex stale: {exc}\n", encoding="utf-8")
            return AgentResult(ok=False, error=f"Codex idle timeout: {exc}")
            
        except self._CodexHardTimeout as exc:
            append_event(self.run_dir, {
                "type": "codex_timeout",
                "ts": time.time(),
                "round_dir": str(round_dir),
                "error": "codex_hard_timeout",
                "detail": str(exc),
            })
            status_path.write_text(f"Codex timeout: {exc}\n", encoding="utf-8")
            return AgentResult(ok=False, error=f"Codex hard timeout: {exc}")
            
        except Exception as exc:
            append_event(self.run_dir, {
                "type": "codex_failed",
                "ts": time.time(),
                "round_dir": str(round_dir),
                "error": "codex_failed",
                "detail": str(exc),
            })
            status_path.write_text(f"Codex failed: {exc}\n", encoding="utf-8")
            return AgentResult(ok=False, error=str(exc))


def run_codex_simple(
    root: Path,
    run_dir: Path,
    prompt: str,
    round_dir: Path,
    idle_timeout: int = 120,
    hard_timeout: int = 1800,
) -> str:
    """
    简单的 Codex 调用函数
    
    Returns:
        Codex 响应文本，失败时抛出异常
    """
    agent = CodexAgent(root, run_dir, idle_timeout, hard_timeout)
    result = agent.run(prompt, round_dir)
    if not result.ok:
        raise RuntimeError(result.error)
    return result.data.get("response", "")
