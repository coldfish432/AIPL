"""
cli/utils.py 中 read_status 函数的补丁
=====================================

修改 read_status 函数，添加失败原因相关字段的返回
"""

# ============================================================
# 找到 read_status 函数的 return 语句（约在函数末尾）
# ============================================================

# 原代码:
"""
    return {
        "run_id": run_dir.name,
        "status": status,
        "current_task_id": meta.get("task_id"),
        "round": round_id,
        "passed": passed,
        "last_reasons": reasons,
        "progress": progress,
        "mode": meta.get("mode"),
        "workspace_main_root": meta.get("workspace_main_root"),
        "workspace_stage_root": meta.get("workspace_stage_root"),
        "patchset_path": meta.get("patchset_path"),
        "changed_files_count": meta.get("changed_files_count"),
    }
"""

# 修改为:
"""
    return {
        "run_id": run_dir.name,
        "status": status,
        "current_task_id": meta.get("task_id"),
        "round": round_id,
        "passed": passed,
        "last_reasons": reasons,
        "progress": progress,
        "mode": meta.get("mode"),
        "workspace_main_root": meta.get("workspace_main_root"),
        "workspace_stage_root": meta.get("workspace_stage_root"),
        "patchset_path": meta.get("patchset_path"),
        "changed_files_count": meta.get("changed_files_count"),
        # 新增：失败原因相关字段
        "failure_reason": meta.get("failure_reason"),
        "failure_reason_detail": meta.get("failure_reason_detail"),
        "failure_details": meta.get("failure_details"),
        "failure_round": meta.get("failure_round"),
    }
"""


# ============================================================
# 完整的修改后的 read_status 函数
# ============================================================

def read_status(run_dir):
    """
    读取 run 的状态信息
    
    修改版本：添加了 failure_reason 等失败原因相关字段
    """
    from pathlib import Path
    import json
    from infra.io_utils import read_json
    
    events_path = run_dir / "events.jsonl"
    status = "running"
    passed = None
    progress = None
    meta = {}
    meta_path = run_dir / "meta.json"
    if meta_path.exists():
        meta = read_json(meta_path, default={})
    if meta.get("status"):
        status = meta.get("status")
    if (run_dir / "cancel.flag").exists():
        status = "canceled"
    if events_path.exists():
        try:
            lines = events_path.read_text(encoding="utf-8").splitlines()
            mapping = {
                "run_init": 1,
                "workspace_stage_ready": 5,
                "step_round_start": 20,
                "step_round_verified": 70,
                "patchset_ready": 85,
                "awaiting_review": 90,
                "apply_start": 95,
                "apply_done": 98,
                "discard_done": 100,
                "run_done": 100,
            }
            for line in lines:
                for key, val in mapping.items():
                    if f'"type": "{key}"' in line:
                        progress = max(progress or 0, val)
            if not meta.get("status"):
                for line in reversed(lines):
                    if '"type": "run_done"' in line or '"type": "awaiting_review"' in line:
                        evt = json.loads(line)
                        if evt.get("type") == "awaiting_review":
                            status = "awaiting_review"
                            break
                        passed = evt.get("passed")
                        status = evt.get("status") or ("done" if passed else "failed")
                        break
        except Exception:
            pass
    if status in {"done", "failed", "discarded", "canceled"}:
        progress = 100
    if status == "awaiting_review":
        progress = max(progress or 0, 90)
    round_id = None
    reasons = []
    steps_dir = run_dir / "steps" / "step-01"
    if steps_dir.exists():
        rounds = [p for p in steps_dir.iterdir() if p.is_dir() and p.name.startswith("round-")]
        if rounds:
            rounds.sort(key=lambda p: p.name)
            latest = rounds[-1]
            round_id = latest.name.replace("round-", "")
            ver_path = latest / "verification.json"
            if ver_path.exists():
                try:
                    ver = read_json(ver_path, default={})
                    reasons = ver.get("reasons", [])
                except Exception:
                    reasons = []
    
    return {
        "run_id": run_dir.name,
        "status": status,
        "current_task_id": meta.get("task_id"),
        "round": round_id,
        "passed": passed,
        "last_reasons": reasons,
        "progress": progress,
        "mode": meta.get("mode"),
        "workspace_main_root": meta.get("workspace_main_root"),
        "workspace_stage_root": meta.get("workspace_stage_root"),
        "patchset_path": meta.get("patchset_path"),
        "changed_files_count": meta.get("changed_files_count"),
        # 新增：失败原因相关字段（从 meta.json 读取）
        "failure_reason": meta.get("failure_reason"),
        "failure_reason_detail": meta.get("failure_reason_detail"),
        "failure_details": meta.get("failure_details"),
        "failure_round": meta.get("failure_round"),
    }
