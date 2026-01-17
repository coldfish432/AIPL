"""
命令执行 Sub Agent
负责执行 Codex 生成的命令
"""
import subprocess
from pathlib import Path
from typing import Any

from .base import BaseAgent, AgentResult


DEFAULT_ALLOWED_COMMANDS = [
    "python",
    "pytest",
    "mvn",
    "gradle",
    "npm",
    "node",
    "pnpm",
    "yarn",
]


class CommandAgent(BaseAgent):
    """
    命令执行 Agent
    
    功能：
    - 验证命令是否允许
    - 执行命令
    - 记录执行结果
    """
    
    def __init__(
        self,
        root: Path,
        run_dir: Path,
        workspace: Path,
        allowed_commands: list[str] = None,
        default_timeout: int = 300,
        enforce_policy: bool = True,
    ):
        super().__init__(root, run_dir)
        self.workspace = workspace
        self.allowed_commands = tuple(allowed_commands or DEFAULT_ALLOWED_COMMANDS)
        self.default_timeout = default_timeout
        self.enforce_policy = enforce_policy
    
    def run(self, commands: list) -> AgentResult:
        """
        执行命令列表
        
        Args:
            commands: 命令列表，每项可以是字符串或 {cmd, timeout} 字典
        
        Returns:
            AgentResult，data 中包含 logs 和 all_passed 字段
        """
        if not isinstance(commands, list):
            return AgentResult(ok=True, data={"logs": [], "all_passed": True})
        
        logs = []
        all_passed = True
        
        for cmd_item in commands:
            result = self._run_single_command(cmd_item)
            logs.append(result)
            if not result.get("success", False):
                all_passed = False
        
        return AgentResult(
            ok=True,
            data={
                "logs": logs,
                "all_passed": all_passed,
                "total_commands": len(commands),
                "success_count": sum(1 for log in logs if log.get("success", False)),
            }
        )
    
    def _run_single_command(self, cmd_item: Any) -> dict:
        """执行单个命令"""
        # 解析命令
        if isinstance(cmd_item, dict):
            cmd_str = cmd_item.get("cmd", "").strip()
            timeout = int(cmd_item.get("timeout", self.default_timeout) or self.default_timeout)
        else:
            cmd_str = str(cmd_item).strip()
            timeout = self.default_timeout
        
        if not cmd_str:
            return {"cmd": "", "status": "skipped", "reason": "empty_command", "success": True}
        
        # 检查是否允许
        allowed = cmd_str.startswith(self.allowed_commands)
        if self.enforce_policy and not allowed:
            return {
                "cmd": cmd_str,
                "status": "skipped",
                "reason": "not_allowed_prefix",
                "success": False,
                "policy_allowed": False,
            }
        
        # 执行命令
        try:
            result = subprocess.run(
                cmd_str,
                cwd=self.workspace,
                shell=True,
                timeout=timeout,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            
            return {
                "cmd": cmd_str,
                "returncode": result.returncode,
                "stdout": (result.stdout or "")[:2000],
                "stderr": (result.stderr or "")[:2000],
                "policy_allowed": allowed,
                "success": result.returncode == 0,
                "status": "ok" if result.returncode == 0 else "failed",
            }
            
        except subprocess.TimeoutExpired as e:
            return {
                "cmd": cmd_str,
                "status": "timeout",
                "detail": str(e),
                "success": False,
                "policy_allowed": allowed,
            }
        except Exception as e:
            return {
                "cmd": cmd_str,
                "status": "error",
                "detail": str(e),
                "success": False,
                "policy_allowed": allowed,
            }


def run_commands_simple(
    workspace: Path,
    commands: list,
    timeout_default: int = 300,
    allowed_prefix: tuple[str, ...] = None,
    enforce_policy: bool = True,
) -> tuple[list[dict], bool]:
    """
    简单的命令执行函数（兼容原有接口）
    
    Returns:
        (logs, all_passed)
    """
    if allowed_prefix is None:
        allowed_prefix = tuple(DEFAULT_ALLOWED_COMMANDS)
    
    agent = CommandAgent(
        root=workspace.parent,
        run_dir=workspace.parent,
        workspace=workspace,
        allowed_commands=list(allowed_prefix),
        default_timeout=timeout_default,
        enforce_policy=enforce_policy,
    )
    result = agent.run(commands)
    return result.data.get("logs", []), result.data.get("all_passed", True)
