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

## Artifacts
Execution artifacts are stored under:
```
artifacts/executions/<plan_id>/runs/<run_id>/
```
