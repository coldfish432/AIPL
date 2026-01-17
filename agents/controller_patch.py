"""
controller.py 补丁说明
======================

在 controller/controller.py 中添加以下修改来集成 failure_report_agent

1. 在文件开头添加辅助函数
2. 在失败处理部分调用 sub agent
"""

# ============================================================
# 1. 在文件开头（约第 30 行之后）添加以下函数
# ============================================================

def _run_failure_report_agent(
    root: Path,
    run_dir: Path,
    task_id: str,
    failure_context: dict,
    timeout: int = 60,
) -> dict | None:
    """
    调用 failure_report_agent sub agent 生成失败报告
    
    Args:
        root: 引擎根目录
        run_dir: 运行目录
        task_id: 任务 ID
        failure_context: 失败上下文
        timeout: 超时时间（秒）
    
    Returns:
        包含 failure_reason, failure_details 等字段的字典，失败时返回 None
    """
    agent_path = root / "failure_report_agent.py"
    if not agent_path.exists():
        print(f"[WARN] Failure report agent not found: {agent_path}")
        return None
    
    # 准备临时文件
    report_dir = run_dir / "failure_report"
    report_dir.mkdir(parents=True, exist_ok=True)
    context_file = report_dir / "failure_context.json"
    
    write_json(context_file, failure_context)
    
    cmd = [
        "python", str(agent_path),
        "--root", str(root),
        "--run-dir", str(run_dir),
        "--task-id", task_id,
        "--failure-context-file", str(context_file),
        "--timeout", str(timeout),
    ]
    
    try:
        result = subprocess.run(
            cmd,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=timeout + 30,  # 额外的缓冲时间
            encoding="utf-8",
            errors="replace",
        )
        
        if result.returncode != 0:
            print(f"[WARN] Failure report agent failed (rc={result.returncode}): {result.stderr[:500]}")
            return None
        
        # 解析 stdout 中的 JSON
        try:
            output = json.loads(result.stdout.strip())
            if output.get("ok") and output.get("meta"):
                return output["meta"]
        except json.JSONDecodeError:
            print(f"[WARN] Failed to parse agent output: {result.stdout[:200]}")
        
        return None
            
    except subprocess.TimeoutExpired:
        print(f"[WARN] Failure report agent timeout after {timeout}s")
        return None
    except Exception as exc:
        print(f"[WARN] Failure report agent error: {exc}")
        return None


# ============================================================
# 2. 修改失败处理部分（约第 562-565 行）
# ============================================================

# 原代码:
"""
        else:
            final_status = "failed"
            _append_event(run_dir, {"type": "run_done", "run_id": run_id, "plan_id": plan_id_for_run, "passed": False, "status": final_status, "ts": time.time()})
            _write_meta(meta_path, {"status": final_status})
"""

# 修改为:
"""
        else:
            final_status = "failed"
            _append_event(run_dir, {"type": "run_done", "run_id": run_id, "plan_id": plan_id_for_run, "passed": False, "status": final_status, "ts": time.time()})
            
            # 调用 failure_report_agent 生成人类可读的失败报告
            failure_meta = {"status": final_status}
            if last_failure_context:
                report_meta = _run_failure_report_agent(
                    root=root,
                    run_dir=run_dir,
                    task_id=task_id,
                    failure_context=last_failure_context,
                    timeout=60,
                )
                
                if report_meta:
                    # Sub agent 成功，使用生成的报告
                    failure_meta.update(report_meta)
                else:
                    # Sub agent 失败，使用原始信息
                    failure_meta["failure_reason"] = last_failure_context.get("error_summary", "")
                    failure_meta["failure_details"] = last_failure_context.get("why_failed", [])
                    failure_meta["failure_round"] = last_failure_round
            
            _write_meta(meta_path, failure_meta)
"""


# ============================================================
# 完整的修改后的代码段（可直接替换）
# ============================================================

MODIFIED_FAILURE_HANDLING = '''
        else:
            final_status = "failed"
            _append_event(run_dir, {"type": "run_done", "run_id": run_id, "plan_id": plan_id_for_run, "passed": False, "status": final_status, "ts": time.time()})
            
            # 调用 failure_report_agent 生成人类可读的失败报告
            failure_meta = {"status": final_status}
            if last_failure_context:
                report_meta = _run_failure_report_agent(
                    root=root,
                    run_dir=run_dir,
                    task_id=task_id,
                    failure_context=last_failure_context,
                    timeout=60,
                )
                
                if report_meta:
                    # Sub agent 成功，使用生成的报告
                    failure_meta.update(report_meta)
                else:
                    # Sub agent 失败，使用原始信息
                    failure_meta["failure_reason"] = last_failure_context.get("error_summary", "")
                    failure_meta["failure_details"] = last_failure_context.get("why_failed", [])
                    failure_meta["failure_round"] = last_failure_round
            
            _write_meta(meta_path, failure_meta)
        if final_status in {"done", "failed", "canceled"}:
'''
