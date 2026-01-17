import json
from pathlib import Path
controller = Path('services/controller/controller.py').read_text()
testshim = Path('tests/test_subagent_shim.py').read_text()
final = {
    "analysis": {
        "understood_problem": "Controller mirrored runs before task_title was initialized and the subagent tests still exercised the real Codex runner because they mocked subprocess.run instead of the new helper.",
        "planned_fix": "Initialize task_title before mirror_run and adjust the tests to mock run_codex_with_files so no actual Codex process is spawned.",
        "related_files_considered": [
            "services/controller/controller.py",
            "infra/codex_runner.py",
            "scripts/subagent_shim.py",
            "tests/test_subagent_shim.py",
            "tests/integration/test_plan_execution_flow.py"
        ],
        "missing_files_addressed": []
    },
    "writes": [
        {
            "target": "workspace",
            "path": "services/controller/controller.py",
            "content": controller,
            "reason": "Initialize task_title before mirror_run to avoid UnboundLocalError."
        },
        {
            "target": "workspace",
            "path": "tests/test_subagent_shim.py",
            "content": testshim,
            "reason": "Mock run_codex_with_files so the unit tests no longer invoke the real Codex binary."
        }
    ],
    "commands": [
        {
            "cmd": "python -m pytest",
            "timeout": 300,
            "purpose": "verify tests after the fixes"
        }
    ],
    "expectations": {
        "likely_to_succeed": True,
        "potential_issues": [],
        "fallback_plan": ""
    }
}
print(json.dumps(final, ensure_ascii=False))
