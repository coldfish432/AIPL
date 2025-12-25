# AIPL 长任务执行流水线（合并说明）

## 概览
- 可靠的执行流水线：plan -> run -> verify -> repair
- 组成：Python 执行引擎、Java Spring Boot API、Electron 控制台
- Hard policy 永久生效；soft profile 仅在批准后用于提示，不改变硬策略

## 架构与模块
- Planner：`plan_and_run.py` + `schemas/plan.schema.json`
- Backlog：`backlog/<plan_id>.json` 与 `backlog/adhoc.json`
- Controller：`controller.py` 选择可运行任务并负责多轮执行
- Sub-agent：`scripts/subagent_shim.py` + `schemas/codex_writes.schema.json`
- Verifier：`verifier.py` 执行 `checks` 并写入验证结果
- Audit：每次 run 形成不可变目录，包含事件与证据

## CLI
仅生成计划：
```
python engine_cli.py plan --task "<task>" --workspace <path>
```
计划并执行：
```
python engine_cli.py run --task "<task>" --workspace <path>
```
状态/事件/产物：
```
python engine_cli.py status --plan-id <plan_id> --run-id <run_id>
python engine_cli.py events --plan-id <plan_id> --run-id <run_id> --cursor 0 --limit 200
python engine_cli.py artifacts --plan-id <plan_id> --run-id <run_id>
python engine_cli.py cancel --plan-id <plan_id> --run-id <run_id>
```
Demo workspace：
```
python engine_cli.py run --task "Fix add() so tests pass" --workspace demo-workspaces/python-bugfix
```

## Server
```
cd server
mvn spring-boot:run
```
健康检查：
```
curl http://127.0.0.1:8088/health
```

## Electron 控制台
开发：
```
cd ui-electron
npm install
npm run dev
```
构建：
```
npm run dist
```
资源要求：
- Java server 放在 `ui-electron/resources/server.jar`。
- 可选：自带 JRE 在 `ui-electron/resources/jre`（保证 `resources/jre/bin/java.exe` 存在）。
行为：
- Electron 会自动启动 Java server（端口 `127.0.0.1:18088`）。
- 关闭 Electron 会停止 Java server。

## Hard/Soft Profiles
Hard policy 始终强制执行（写入范围、命令白名单、超时/并发等）。
Soft profile 仅在批准后注入提示，不改变硬策略、不自动执行额外命令。

Profile CLI：
```
python engine_cli.py profile --action get --workspace <path>
python engine_cli.py profile --action propose --workspace <path>
python engine_cli.py profile --action approve --workspace <path>
python engine_cli.py profile --action reject --workspace <path>
```

Profile API：
```
curl "http://127.0.0.1:8088/api/profile?workspace=<path>"
curl -X POST "http://127.0.0.1:8088/api/profile/propose" -H "Content-Type: application/json" -d "{\"workspace\":\"<path>\"}"
curl -X POST "http://127.0.0.1:8088/api/profile/approve" -H "Content-Type: application/json" -d "{\"workspace\":\"<path>\"}"
curl -X POST "http://127.0.0.1:8088/api/profile/reject" -H "Content-Type: application/json" -d "{\"workspace\":\"<path>\"}"
```

## Checks 示例
计划任务包含结构化 `checks`，Verifier 可直接执行。
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

## 产物与存储
- Plan 产物：`artifacts/executions/<plan_id>/plan.json`、`plan.tasks.jsonl`、`snapshot.json`
- Plan 运行：`artifacts/executions/<plan_id>/runs/<run_id>/`
- 非 plan 运行：`artifacts/runs/<run_id>/`
- Run 目录包含：`meta.json`、`events.jsonl`、`policy.json`、`steps/step-01/round-*/verification.json`、`verification_report.md`、`outputs/`
- Backlog：`backlog/adhoc.json` 与 `backlog/<plan_id>.json`

## 队列与快照
活跃任务存储在：
- `backlog/adhoc.json`（非 plan 任务；`todo`/`doing`/`failed`/`done`）
- `backlog/<plan_id>.json`（plan 任务；`todo`/`doing`/`failed`/`done`）

计划停止执行时会写入快照：
- `artifacts/executions/<plan_id>/snapshot.json`

任务陈旧检测默认值：
- `AIPL_STALE_SECONDS`（默认 3600；0 关闭）
- `AIPL_STALE_AUTO_RESET`（true/false；可通过 `--stale-auto-reset` / `--no-stale-auto-reset` 覆盖）
