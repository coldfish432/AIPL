"""
修复任务 Sub Agent
组合其他 Agent 完成代码修复任务
这是重构后的 subagent_shim.py 主要功能
"""
import argparse
import json
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
from .write_agent import WriteAgent, snapshot_directory
from .command_agent import CommandAgent
from .context_agent import ContextAgent, load_task_spec, load_rework


class FixAgent(BaseAgent):
    """
    修复任务 Agent
    
    组合功能：
    1. 收集上下文（ContextAgent）
    2. 调用 Codex 生成修复计划（CodexAgent）
    3. 应用文件写入（WriteAgent）
    4. 执行命令（CommandAgent）
    """
    
    def __init__(
        self,
        root: Path,
        run_dir: Path,
        workspace: Path,
        workspace_main: Path = None,
        allow_write: list[str] = None,
        deny_write: list[str] = None,
        allowed_commands: list[str] = None,
        command_timeout: int = 300,
        enforce_policy: bool = True,
    ):
        super().__init__(root, run_dir)
        self.workspace = workspace
        self.workspace_main = workspace_main or workspace
        self.allow_write = allow_write or []
        self.deny_write = deny_write or []
        self.allowed_commands = allowed_commands or []
        self.command_timeout = command_timeout
        self.enforce_policy = enforce_policy
        
        # 子 Agent
        self.context_agent = ContextAgent(root, run_dir, workspace)
        self.codex_agent = CodexAgent(root, run_dir)
        self.write_agent = WriteAgent(
            root, run_dir, workspace,
            allow_write, deny_write, enforce_policy
        )
        self.command_agent = CommandAgent(
            root, run_dir, workspace,
            allowed_commands, command_timeout, enforce_policy
        )
    
    def run(
        self,
        task_id: str,
        step_id: str,
        round_id: int,
        mode: str,
        acceptance: list[str] = None,
        checks: list[dict] = None,
    ) -> AgentResult:
        """
        执行修复任务
        
        Args:
            task_id: 任务 ID
            step_id: 步骤 ID
            round_id: 轮次 ID
            mode: 执行模式
            acceptance: 验收标准
            checks: 检查项
        
        Returns:
            AgentResult
        """
        round_dir = self.run_dir / "steps" / step_id / f"round-{round_id}"
        outputs_dir = self.run_dir / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        
        # 记录请求
        req = {
            "task_id": task_id,
            "step": step_id,
            "round": round_id,
            "mode": mode,
            "ts": time.time(),
            "workspace": str(self.workspace),
        }
        write_json_file(round_dir / "create_request.json", req)
        append_event(self.run_dir, {"type": "subagent_start", **req})
        
        # 1. 加载返工信息
        rework = load_rework(self.run_dir, step_id, round_id)
        why_failed = ""
        prev_stdout = ""
        if rework:
            prev = rework.get("why_failed", "")
            if isinstance(prev, list):
                try:
                    why_failed = json.dumps(prev, ensure_ascii=False, indent=2)
                except Exception:
                    why_failed = str(prev)
            else:
                why_failed = str(prev)
            prev_stdout = rework.get("prev_stdout", "")
        
        # 2. 收集上下文
        context_result = self.context_agent.run(checks=checks, rework=rework)
        context = context_result.data
        
        # 3. 构建提示词
        prompt = self._build_prompt(
            task_id=task_id,
            round_id=round_id,
            mode=mode,
            acceptance=acceptance or [],
            checks=checks or [],
            context=context,
            why_failed=why_failed,
            prev_stdout=prev_stdout,
            outputs_dir=outputs_dir,
        )
        
        # 4. 调用 Codex
        codex_result = self.codex_agent.run(prompt, round_dir)
        if not codex_result.ok:
            return AgentResult(ok=False, error=f"Codex failed: {codex_result.error}")
        
        # 5. 解析响应
        try:
            plan = json.loads(codex_result.data["response"])
        except json.JSONDecodeError as e:
            return AgentResult(ok=False, error=f"Invalid JSON response: {e}")
        
        # 6. 验证和应用写入
        writes = plan.get("writes", [])
        from policy_validator import validate_writes
        cleaned_writes, write_reasons = validate_writes(
            writes, self.allow_write, self.deny_write,
            enforce_policy=self.enforce_policy
        )
        write_result = self.write_agent.run(cleaned_writes)
        
        # 7. 验证和执行命令
        cmds = plan.get("commands", [])
        from policy_validator import validate_commands
        cleaned_cmds, command_reasons = validate_commands(
            cmds, self.allowed_commands, self.command_timeout,
            enforce_policy=self.enforce_policy
        )
        cmd_result = self.command_agent.run(cleaned_cmds)
        
        # 8. 构建输出
        stdout_lines = self._build_stdout(
            write_result.data,
            cmd_result.data,
            write_reasons,
            command_reasons,
        )
        stdout = "\n".join(stdout_lines)
        
        # 9. 保存结果
        write_json_file(round_dir / "shape_response.json", {
            "ok": True,
            "produced": [str(p.relative_to(self.run_dir)) for p in outputs_dir.glob("*")],
            "stdout_summary": stdout,
            "commands": cmd_result.data.get("logs", []),
            "skipped_writes": write_result.data.get("skipped", []),
            "validation_reasons": write_reasons + command_reasons,
        })
        (round_dir / "stdout.txt").write_text(stdout + "\n", encoding="utf-8")
        (round_dir / "stderr.txt").write_text("", encoding="utf-8")
        
        append_event(self.run_dir, {
            "type": "subagent_done",
            "task_id": task_id,
            "step": step_id,
            "round": round_id,
            "mode": mode,
            "ts": time.time(),
        })
        
        return AgentResult(ok=True, data={
            "produced": write_result.data.get("produced", []),
            "commands": cmd_result.data.get("logs", []),
            "all_passed": cmd_result.data.get("all_passed", True),
        })
    
    def _build_prompt(
        self,
        task_id: str,
        round_id: int,
        mode: str,
        acceptance: list[str],
        checks: list[dict],
        context: dict,
        why_failed: str,
        prev_stdout: str,
        outputs_dir: Path,
    ) -> str:
        """构建提示词"""
        from policy_validator import default_path_rules
        
        # 格式化各个块
        acceptance_block = "\n".join("- " + c for c in acceptance) if acceptance else "- (none provided)"
        checks_block = json.dumps(checks, ensure_ascii=False, indent=2) if checks else "[]"
        
        related_files_block = self.context_agent.format_related_files(context.get("related_files", []))
        missing_suggestions_block = self.context_agent.format_missing_suggestions(context.get("missing_suggestions", []))
        hints_block = self.context_agent.format_hints(context.get("hints", []))
        lessons_block = self.context_agent.format_lessons(context.get("lessons", []))
        
        hard_block = json.dumps({
            "allow_write": self.allow_write,
            "deny_write": self.deny_write,
            "allowed_commands": self.allowed_commands,
            "command_timeout": self.command_timeout,
            "path_rules": default_path_rules(),
        }, ensure_ascii=False, indent=2)
        
        # 加载规则
        policy_data = load_json_file(self.run_dir / "policy.json", default={})
        rules = policy_data.get("workspace_rules", [])
        rule_sources = policy_data.get("workspace_rule_sources", {})
        if rules:
            rules_block = "\n".join(f"- {rule} ({rule_sources.get(rule, 'workspace')})" for rule in rules)
        else:
            rules_block = "- (none provided)"
        
        # 快照 outputs
        snap = snapshot_directory(outputs_dir)
        
        # 读取模板
        tmpl = (self.root / "prompts" / "fix.txt").read_text(encoding="utf-8")
        
        return tmpl.format(
            task_id=task_id,
            run_name=self.run_dir.name,
            round_id=round_id,
            workspace=str(self.workspace),
            mode=mode,
            hard_block=hard_block,
            rules_block=rules_block,
            hints_block=hints_block,
            lessons_block=lessons_block,
            related_files_block=related_files_block,
            missing_suggestions_block=missing_suggestions_block,
            acceptance_block=acceptance_block,
            checks_block=checks_block,
            why_failed=why_failed,
            prev_stdout=prev_stdout,
            snap_json=json.dumps(snap, ensure_ascii=False),
        )
    
    def _build_stdout(
        self,
        write_data: dict,
        cmd_data: dict,
        write_reasons: list,
        command_reasons: list,
    ) -> list[str]:
        """构建 stdout 输出"""
        lines = []
        
        produced = write_data.get("produced", [])
        lines.append("Codex applied writes: " + ", ".join(produced or ["<none>"]))
        
        for s in write_data.get("skipped", []):
            lines.append(f"[skip_write] {s.get('path')} reason={s.get('reason')}")
        
        for r in write_reasons + command_reasons:
            lines.append(f"[validation] {json.dumps(r, ensure_ascii=False)}")
        
        for log in cmd_data.get("logs", []):
            status = "ok" if log.get("returncode", 0) == 0 else log.get("status", "failed")
            lines.append(f"[cmd] {log.get('cmd')} status={status} rc={log.get('returncode', '')}")
        
        return lines


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description="Fix Agent - 代码修复 Sub Agent")
    parser.add_argument("--root", required=True, help="引擎根目录")
    parser.add_argument("run_dir", help="运行目录")
    parser.add_argument("task_id", help="任务 ID")
    parser.add_argument("step_id", help="步骤 ID")
    parser.add_argument("round_id", help="轮次 ID")
    parser.add_argument("mode", help="执行模式")
    parser.add_argument("--workspace", help="目标 workspace 路径")
    parser.add_argument("--workspace-main", help="主 workspace 路径（用于 profile/策略）")
    
    args = parser.parse_args()
    
    # 初始化
    root = init_root()
    
    # 加载配置
    from infra.path_guard import is_workspace_unsafe
    from services.profile_service import ensure_profile, DEFAULT_ALLOWED_COMMANDS, DEFAULT_COMMAND_TIMEOUT, DEFAULT_DENY_WRITE
    from config import POLICY_ENFORCED
    
    run_dir = Path(args.run_dir)
    task_id = args.task_id
    step_id = args.step_id
    round_id = int(args.round_id)
    mode = args.mode
    
    # 获取 workspace
    task_spec = load_task_spec(root, task_id)
    acceptance = task_spec.get("acceptance_criteria", [])
    checks = task_spec.get("checks", [])
    
    workspace_path = Path(args.workspace) if args.workspace else None
    workspace_main_path = Path(args.workspace_main) if args.workspace_main else None
    
    if not workspace_path and isinstance(task_spec.get("workspace"), dict):
        wpath = task_spec["workspace"].get("path")
        if wpath:
            workspace_path = Path(wpath)
    
    if not workspace_path:
        raise RuntimeError("workspace path is required")
    
    workspace_path = workspace_path.resolve()
    if not workspace_main_path:
        workspace_main_path = workspace_path
    workspace_main_path = workspace_main_path.resolve()
    
    if is_workspace_unsafe(root, workspace_main_path):
        raise RuntimeError(f"workspace path {workspace_main_path} includes engine root {root}")
    
    # 加载策略配置
    allow_write = []
    deny_write = list(DEFAULT_DENY_WRITE)
    allowed_commands = list(DEFAULT_ALLOWED_COMMANDS)
    command_timeout = DEFAULT_COMMAND_TIMEOUT
    
    cfg_path = run_dir / "policy.json"
    if not cfg_path.exists():
        cfg_path = run_dir / "workspace_config.json"
    if cfg_path.exists():
        cfg = load_json_file(cfg_path, default={})
        allow_write = cfg.get("allow_write", allow_write) or allow_write
        deny_write = cfg.get("deny_write", deny_write) or deny_write
        allowed_commands = cfg.get("allowed_commands", allowed_commands) or allowed_commands
        command_timeout = int(cfg.get("command_timeout", command_timeout) or command_timeout)
    
    if "outputs" not in deny_write:
        deny_write.append("outputs")
    
    profile = ensure_profile(root, workspace_main_path)
    effective_hard = profile.get("effective_hard") or {}
    allow_write = effective_hard.get("allow_write", allow_write) or allow_write
    deny_write = effective_hard.get("deny_write", deny_write) or deny_write
    allowed_commands = effective_hard.get("allowed_commands", allowed_commands) or allowed_commands
    command_timeout = int(effective_hard.get("command_timeout", command_timeout) or command_timeout)
    
    # 创建并运行 Agent
    agent = FixAgent(
        root=root,
        run_dir=run_dir,
        workspace=workspace_path,
        workspace_main=workspace_main_path,
        allow_write=allow_write,
        deny_write=deny_write,
        allowed_commands=allowed_commands,
        command_timeout=command_timeout,
        enforce_policy=POLICY_ENFORCED,
    )
    
    result = agent.run(
        task_id=task_id,
        step_id=step_id,
        round_id=round_id,
        mode=mode,
        acceptance=acceptance,
        checks=checks,
    )
    
    print(result.to_json())


if __name__ == "__main__":
    main()
