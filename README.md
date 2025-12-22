# AIPL Execution Engine

## Overview
- Python execution kernel (plan -> controller -> verifier)
- Java Spring Boot gateway (server/)

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

## Artifacts
Execution artifacts are stored under:
```
artifacts/executions/<plan_id>/runs/<run_id>/
```
