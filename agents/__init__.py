"""
Sub Agents 模块
将原来的 subagent_shim.py 拆分成多个独立的 Agent

模块结构：
- base.py        : 基础类和工具函数
- codex_agent.py : Codex 调用 Agent
- write_agent.py : 文件写入 Agent
- command_agent.py : 命令执行 Agent
- context_agent.py : 上下文收集 Agent
- fix_agent.py   : 修复任务 Agent（组合以上 Agent）
- report_agent.py: 失败报告 Agent

使用示例：

    from agents import FixAgent, ReportAgent
    
    # 执行修复任务
    fix_agent = FixAgent(root, run_dir, workspace)
    result = fix_agent.run(task_id, step_id, round_id, mode)
    
    # 生成失败报告
    report_agent = ReportAgent(root, run_dir)
    result = report_agent.run(task_id, checks, reasons)
"""

from .base import (
    BaseAgent,
    AgentResult,
    init_root,
    extract_root_arg,
    load_json_file,
    write_json_file,
    append_event,
    resolve_path_under,
    is_path_allowed,
)

from .codex_agent import CodexAgent, run_codex_simple
from .write_agent import WriteAgent, snapshot_directory, apply_writes_simple
from .command_agent import CommandAgent, run_commands_simple, DEFAULT_ALLOWED_COMMANDS
from .context_agent import ContextAgent, load_task_spec, load_rework
from .fix_agent import FixAgent
from .report_agent import ReportAgent, ERROR_TYPE_MAPPING


__all__ = [
    # 基础
    "BaseAgent",
    "AgentResult",
    "init_root",
    "extract_root_arg",
    "load_json_file",
    "write_json_file",
    "append_event",
    "resolve_path_under",
    "is_path_allowed",
    # Codex
    "CodexAgent",
    "run_codex_simple",
    # Write
    "WriteAgent",
    "snapshot_directory",
    "apply_writes_simple",
    # Command
    "CommandAgent",
    "run_commands_simple",
    "DEFAULT_ALLOWED_COMMANDS",
    # Context
    "ContextAgent",
    "load_task_spec",
    "load_rework",
    # Fix
    "FixAgent",
    # Report
    "ReportAgent",
    "ERROR_TYPE_MAPPING",
]
