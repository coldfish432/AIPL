# AIPL 执行引擎

## 概览
- Python 执行内核（规划 → 控制器 → 验证器）
- Java Spring Boot 网关（`server/`）
- 工作区 Profile：硬策略（强制）+ 软 Profile（建议，需审批）

## 架构与流程
引擎采用可回放、可审计的确定性流水线，将 LLM 输出严格收束在受控范围内：

1. **目标接收与规划**：`engine_cli.py`、`plan_and_run.py` 接收目标，基于 `prompts/plan.txt` 拆出带依赖与验收 `checks` 的结构化计划，保存到 `backlog/<plan_id>.json` 与 `artifacts/plans/` 便于审计。
2. **任务调度**：`controller.py` 读取 backlog，按依赖创建隔离的运行目录 `artifacts/executions/<plan_id>/runs/<run_id>/`，并将状态流转写入 `artifacts/state/events.jsonl`。
3. **受限执行**：`scripts/subagent_shim.py` 包裹子代理，只允许在运行工作区内写入。它使用如 `prompts/subagent_fix.txt` 的提示，并输出符合 `schemas/codex_writes.schema.json` 的文件改动。
4. **验证与反馈**：`verifier.py` 依据任务自带的 `checks`（结构见 `schemas/plan.schema.json`）及 `prompts/verifier.txt` 进行确定性校验（文件、命令、Schema 等），结果写入 `verification.json`；失败则生成 `rework_request.json` 推动下一轮修复。
5. **策略管控**：`config.py`、`policy_validator.py`、`profile.py` 定义工作区硬策略（写入范围、命令白名单、超时等），`profile_store.py` 持久化软 Profile。软建议永不覆盖硬策略，仅在审批后用于提示词。

流程会在任务通过验证或耗尽重试前反复执行，沉淀完整的输入、输出与失败原因审计轨迹，可随时回放定位问题。

## 项目结构
- `engine_cli.py`、`plan_and_run.py`：端到端执行与 Profile 管理的 CLI 入口。
- `controller.py`：从 backlog 中挑选可执行任务并编排运行目录。
- `verifier.py`：执行任务定义的检查，输出结构化成功/失败原因。
- `scripts/subagent_shim.py`：对子代理进行沙箱隔离，严格限制写入范围。
- `schemas/`：任务计划与写入操作的 JSON Schema。
- `prompts/`：规划、子代理、验证器的提示模板。
- `artifacts/`：运行时生成的计划、执行记录、快照与审计日志。
- `server/`：对外暴露 Profile 与目标执行 HTTP API 的 Spring Boot 网关。
- `demo-workspaces/`：本地演示用的示例工作区。

## 启动 Server
```
cd server
mvn spring-boot:run
```

健康检查：
```
curl http://127.0.0.1:8088/health
```

## Demo 工作区
```
python engine_cli.py run --goal "Fix add() so tests pass" --workspace demo-workspaces/python-bugfix
```

## 硬/软 Profile
硬策略始终强制（写入范围 + 命令白名单 + 超时/并发限制）。即便缺少用户策略，也会套用系统默认硬策略。
软 Profile 仅提供建议，审批后才会注入提示词，从不修改硬策略或执行额外命令。

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
计划中的任务应包含可直接由验证器执行的结构化 `checks`：
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

## 验证器示例流程
1) 运行一个在 checks 中写出非法路径（如 `outputs/test-fail.log{}`）的计划。
2) 验证器会拒绝该路径（非法字符），并记录结构化失败原因。
3) 审批软 Profile 后，规划/子代理提示会使用已审批的建议（硬策略仍然生效）。

## 运行产物
执行产物存放在：
```
artifacts/executions/<plan_id>/runs/<run_id>/
```

## 活跃队列与快照
活跃任务存放在：
- `backlog/adhoc.json`（即席或非计划任务；状态 `todo`/`doing`/`stale`）
- `backlog/<plan_id>.json`（对应计划的活跃任务；状态 `todo`/`doing`/`stale`）

计划结束时会写入快照：
- `artifacts/executions/<plan_id>/snapshot.json`（计划任务的完整快照）

状态流转记录在：
- `artifacts/state/events.jsonl`

默认的过期检测：
- `AIPL_STALE_SECONDS`（默认 3600，0 表示关闭）
- `AIPL_STALE_AUTO_RESET`（true/false，可通过 `--stale-auto-reset` / `--no-stale-auto-reset` 覆盖）
