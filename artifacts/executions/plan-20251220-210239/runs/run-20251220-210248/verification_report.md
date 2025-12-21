# Verification Report
- task_id: plan-20251220-210239-1
- plan_id: plan-20251220-210239
- run_dir: D:\AIPL\artifacts\executions\plan-20251220-210239\runs\run-20251220-210248
- workspace: D:\AIPL\demo-workspaces\python-bugfix
- passed: False

## Checks
- command: python -m pytest -q timeout=300

## How To Verify
- run: python -m pytest -q

## Failure Reasons
- {"type": "command_failed", "cmd": "python -m pytest -q", "expected": "exit code 0", "actual": "exit code 1", "hint": "log: verification/cmd-0.stdout.txt / cmd-0.stderr.txt"}
