# AIPL Execution Engine

## Overview
- Python execution kernel (plan -> controller -> verifier)
- Java Spring Boot gateway (server/)
- Workspace Profile: hard policy (enforced) + soft profile (advisory, approved only)

## Architecture and Flow
The engine follows a deterministic pipeline that keeps LLM output tightly controlled:

1. **Goal intake & planning** – `engine_cli.py` and `plan_and_run.py` accept a goal and use the prompt in `prompts/plan.txt` to generate a structured plan with tasks, dependencies, and checks. Plans are saved under `backlog/<plan_id>.json` and `artifacts/plans/` for auditability.
2. **Task scheduling** – `controller.py` reads active backlog entries and creates isolated run directories under `artifacts/executions/<plan_id>/runs/<run_id>/`, tracking status transitions in `artifacts/state/events.jsonl`.
3. **Scoped execution** – `scripts/subagent_shim.py` wraps the sub-agent to ensure it only writes inside the run workspace. It consumes prompts like `prompts/subagent_fix.txt` and emits filesystem changes validated by `schemas/codex_writes.schema.json`.
4. **Verification and feedback** – `verifier.py` uses the checks embedded in each task (see `schemas/plan.schema.json` for structure) together with `prompts/verifier.txt` to run deterministic validations (file existence, commands, schema checks). Results are written to `verification.json`; failures produce `rework_request.json` to trigger another iteration.
5. **Policy enforcement** – Workspace policies defined in `config.py`, `policy_validator.py`, and `profile.py` combine mandatory hard rules (write scope, allowed commands, timeouts) with optional soft profiles stored via `profile_store.py`. Soft suggestions never override hard policy but can guide prompts after approval.

This loop repeats until tasks pass verification or exhaust retries, creating a full audit trail (inputs, outputs, and failure reasons) that can be replayed for debugging.

## Project Structure
- `engine_cli.py`, `plan_and_run.py`: CLI entrypoints for running end-to-end flows or managing profiles.
- `controller.py`: Picks runnable tasks from backlogs and orchestrates run directories.
- `verifier.py`: Executes checks defined in tasks and reports structured success/failure reasons.
- `scripts/subagent_shim.py`: Sandboxes the sub-agent and enforces write scopes.
- `schemas/`: JSON Schemas for task plans and write operations.
- `prompts/`: Prompt templates for planner, sub-agent, and verifier.
- `artifacts/`: Generated plans, runs, snapshots, and audit logs (created at runtime).
- `server/`: Spring Boot gateway exposing HTTP APIs for profiles and goal execution.
- `demo-workspaces/`: Example workspaces for local demos.

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
