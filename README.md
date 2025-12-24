# AIPL Execution Engine

## Overview
- Python execution kernel (plan -> controller -> verifier)
- Java Spring Boot gateway (server/)
- Workspace Profile: hard policy (enforced) + soft profile (advisory, approved only)

## Server
```
cd server
mvn spring-boot:run
```

Health check:
```
curl http://127.0.0.1:8088/health
```

## Demo Workspace
```
python engine_cli.py run --goal "Fix add() so tests pass" --workspace demo-workspaces/python-bugfix
```

## Hard/Soft Profiles
Hard policy is always enforced (write scope + command allowlist + timeout/concurrency). If user policy is missing, the system hard defaults still apply.
Soft profile is advisory and only used in prompts after approval. It never changes hard policy or executes extra commands.

Profile CLI:
```
python engine_cli.py profile --action get --workspace <path>
python engine_cli.py profile --action propose --workspace <path>
python engine_cli.py profile --action approve --workspace <path>
python engine_cli.py profile --action reject --workspace <path>
```

Profile API:
```
curl "http://127.0.0.1:8088/api/profile?workspace=<path>"
curl -X POST "http://127.0.0.1:8088/api/profile/propose" -H "Content-Type: application/json" -d "{\"workspace\":\"<path>\"}"
curl -X POST "http://127.0.0.1:8088/api/profile/approve" -H "Content-Type: application/json" -d "{\"workspace\":\"<path>\"}"
curl -X POST "http://127.0.0.1:8088/api/profile/reject" -H "Content-Type: application/json" -d "{\"workspace\":\"<path>\"}"
```

## Checks Examples
Plan tasks should include structured `checks` that the verifier can execute directly.
```json
{
  "checks": [
    { "type": "file_exists", "path": "outputs/result.txt" },
    { "type": "file_contains", "path": "outputs/result.txt", "needle": "OK" },
    { "type": "command", "cmd": "python -m pytest -q", "timeout": 300, "expect_exit_code": 0 },
    { "type": "command_contains", "cmd": "python -m pytest -q", "needle": "passed" },
    { "type": "json_schema", "path": "outputs/report.json", "schema": { "type": "object", "required": ["ok"] } },
    { "type": "http_check", "url": "http://127.0.0.1:8088/health", "expected_status": 200, "contains": "ok" }
  ]
}
```

## Validator Demo
1) Run a plan that emits a bad path (e.g. `outputs/test-fail.log{}`) in checks.
2) The validator rejects the path (non-allowed characters) and records structured reasons.
3) After approving a soft profile, the planner/subagent prompts use the approved suggestions (but hard policy still applies).

## Artifacts
Execution artifacts are stored under:
```
artifacts/executions/<plan_id>/runs/<run_id>/
```

## Active Queue + Snapshots
Active tasks are stored in:
- `backlog/adhoc.json` (ad-hoc or non-plan tasks; `todo`/`doing`/`stale`)
- `backlog/<plan_id>.json` (active tasks for each plan; `todo`/`doing`/`stale`)

Plan snapshots are written when a plan stops executing:
- `artifacts/executions/<plan_id>/snapshot.json` (full task snapshot for the plan)

Status transitions are recorded in:
- `artifacts/state/events.jsonl`

Stale detection defaults:
- `AIPL_STALE_SECONDS` (default 3600; 0 disables)
- `AIPL_STALE_AUTO_RESET` (true/false; can be overridden via `--stale-auto-reset` / `--no-stale-auto-reset`)
