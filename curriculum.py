import time
from pathlib import Path

def suggest_next_task(goal: str, backlog: dict):
    """
    Rule-based mini curriculum (no LLM yet).
    It only appends tasks that are 'time_for_certainty' and objectively verifiable.
    """
    # 按课程梯度挑选出尚未存在于待办列表中的下一项任务
    tasks = backlog.get("tasks", [])
    existing_ids = {t["id"] for t in tasks}

    # 预设的递进式任务梯队，约定依赖与验收标准
    ladder = [
        {
            "id": "T001",
            "title": "Generate deliverable file",
            "deps": [],
            "criteria": [
                "outputs/result.txt exists",
                "result.txt is exactly one line: OK: deliverable generated"
            ]
        },
        {
            "id": "T002",
            "title": "Create a human-readable summary",
            "deps": ["T001"],
            "criteria": [
                "outputs/summary.md exists",
                "summary.md contains Task and Run"
            ]
        },
        {
            "id": "T003",
            "title": "Produce a run report index",
            "deps": ["T002"],
            "criteria": [
                "index.md exists",
                "index.md contains Evidence section"
            ]
        }
    ]

    # 从梯队中寻找第一个缺失的任务并构造返回结构
    for item in ladder:
        if item["id"] in existing_ids:
            continue
        return {
            "id": item["id"],
            "title": item["title"],
            "type": "time_for_certainty",
            "priority": 50,
            "estimated_minutes": 20,
            "status": "todo",
            "dependencies": item["deps"],
            "acceptance_criteria": item["criteria"],
            "created_from_goal": goal.strip(),
            "created_ts": time.time()
        }

    # 若所有梯队任务均已存在，则返回空
    return None
