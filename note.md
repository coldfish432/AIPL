
# AI 长任务拆解-执行-验收流水线开发日志

> 项目目标：构建一个可自动拆解长任务、执行子任务、验证结果，并支持失败自动修复与完整审计的 AI 工作流水线，实现“布置任务 → 自动运行 → 可验证结果”。

---

## 一、整体设计思路

本项目采用 **“规划 → 执行 → 验收 → 修复”** 的流水线式结构，将 AI（Codex）严格限制在“推理与生成”角色中，而把 **状态管理、调度、验证、审计** 全部交由本地确定性代码完成。

核心原则包括：

- **LLM 不直接决定任务是否成功**
- **所有执行结果必须可验证**
- **所有行为必须可回放、可审计**
- **失败原因必须结构化并可被再次利用**

---

## 二、已完成模块与功能

### 1. 长任务拆解（Planning）

**对应模块：**
- `plan_and_run.py`
- `schemas/plan.schema.json`
- `artifacts/plans/`

**已实现功能：**

- 支持输入一个自然语言形式的“长任务”
- 通过 Codex + JSON Schema 约束，将长任务拆解为多个子任务
- 每个子任务包含：
  - task_id
  - 依赖关系（dependencies）
  - 验收标准（acceptance_criteria / checks）
- 拆解结果写入：
  - `artifacts/plans/<plan_id>.json`
  - `artifacts/plans/<plan_id>.tasks.jsonl`
- 子任务自动追加到 `backlog.json`，无需人工手写

---

### 2. 全局任务状态管理（Backlog）

**对应模块：**
- `backlog.json`

**已实现功能：**

- `backlog.json` 作为全局唯一任务状态源
- 每个任务支持状态流转：
  - `todo → doing → done / failed`
- 支持字段：
  - `plan_id`
  - `dependencies`
  - `priority`
  - `acceptance_criteria`
  - `checks`
  - `last_run`
  - `last_reasons`（结构化失败原因）
- 支持按 `plan_id` 过滤与清理

---

### 3. 调度与执行（Controller）

**对应模块：**
- `controller.py`

**已实现功能：**

- 从 `backlog.json` 中挑选：
  - 状态为 `todo`
  - 依赖已完成
  - 类型为 `time_for_certainty` 的任务
- 为每个任务创建独立运行目录：
```

artifacts/runs/<run_id>/

````
- 自动记录：
- `meta.json`
- `events.jsonl`
- `index.md`
- 支持多轮执行（round）：
- round-0：首次尝试
- round-n：基于失败原因自动修复
- 执行结束后自动回写任务状态到 backlog

---

### 4. 子代理执行与修复（Sub-Agent）

**对应模块：**
- `scripts/subagent_shim.py`
- `schemas/codex_writes.schema.json`

**已实现功能：**

- 子代理只在 **run workspace 内部** 工作，防止越权
- 支持读取：
- 当前任务规格
- 验收标准
- 上一轮的 `rework_request.json`
- 将以下信息注入 Codex Prompt：
- 任务上下文
- 验收标准
- verifier 的结构化失败原因
- 当前 outputs 快照
- Codex 输出必须符合 JSON Schema：
```json
{
  "writes": [
    {"path": "outputs/xxx", "content": "..."}
  ]
}
````

* 系统自动解析并安全写入文件
* 所有行为均记录为：

  * `shape_response.json`
  * `stdout.txt / stderr.txt`
  * events 日志

---

### 5. 验收与验证（Verifier）

**对应模块：**

* `verifier.py`

**已实现功能：**

* verifier 是 **完全确定性的模块**
* 优先使用 backlog 中定义的 `checks`：

  * `file_exists`
  * `file_contains`
  * `command`（支持 timeout）
* 若无 checks，则 fallback 到 legacy 规则（T001/T002/T003）
* 每次验证返回：

  * `passed: true / false`
  * `reasons: []`（结构化失败原因）
* 验证结果写入：

  ```
  steps/<step_id>/round-<n>/verification.json
  ```
* 失败原因会被直接用于下一轮修复 prompt

---

### 6. 自动返工闭环（Failure → Repair）

**已实现机制：**

* verifier 失败 → 生成 `rework_request.json`
* 内容包括：

  * why_failed（结构化 reasons）
  * 下一轮修复指令
* subagent 在下一轮 **必须读取并响应失败原因**
* 形成完整闭环：

  ```
  generate → verify → fail → explain → repair → verify
  ```

---

### 7. 审计与可回放性（Audit）

**已实现功能：**

* 每一次 run 都是不可变的审计单元
* 每个 run 目录包含：

  * 输入（task / plan）
  * 过程（events.jsonl）
  * 输出（outputs）
  * 验证（verification.json）
  * 修复请求（rework_request.json）
* 任意一次执行都可以：

  * 回放
  * 对比
  * 定位责任
* 支持按 plan_id 清理 backlog，并在 plan 文件中写入 cleanup_snapshot

---

## 三、当前系统状态总结

截至目前，系统已经具备：

* ✅ 长任务自动拆解
* ✅ 子任务依赖调度
* ✅ 多轮自动修复
* ✅ 确定性验收
* ✅ LLM 行为受控
* ✅ 完整审计与回放能力

系统已形成一个**可实际运行、可复现实验结果的 AI 自动执行流水线原型**。
//-12.18.2025-//

# AI 长任务拆解-执行-验收流水线开发日志

> 项目目标：构建一个可自动拆解长任务、执行子任务、验证结果，并支持失败自动修复与完整审计的 AI 工作流水线，实现“布置任务 → 自动运行 → 可验证结果”。

---

## 一、整体设计思路

本项目采用 **“规划 → 执行 → 验收 → 修复”** 的流水线式结构，将 AI（Codex）严格限制在“推理与生成”角色中，而把 **状态管理、调度、验证、审计** 全部交由本地确定性代码完成。

核心原则包括：

* **LLM 不直接决定任务是否成功**
* **所有执行结果必须可验证**
* **所有行为必须可回放、可审计**
* **失败原因必须结构化并可被再次利用**

---

## 二、已完成模块与功能

### （一）长任务拆解（Planning）

**对应模块：**

* `plan_and_run.py`
* `schemas/plan.schema.json`
* `artifacts/plans/`

**已实现功能：**

* 支持输入一个自然语言形式的“长任务”
* 通过 Codex + JSON Schema 约束，将长任务拆解为多个子任务
* 每个子任务包含：

  * task_id
  * 依赖关系（dependencies）
  * 验收标准（acceptance_criteria / checks）
* 拆解结果写入：

  * `artifacts/plans/<plan_id>.json`
  * `artifacts/plans/<plan_id>.tasks.jsonl`
* 子任务自动追加到 `backlog.json`，无需人工手写

---

### （二）全局任务状态管理（Backlog）

**对应模块：**

* `backlog.json`

**已实现功能：**

* `backlog.json` 作为全局唯一任务状态源
* 每个任务支持状态流转：

  ```
  todo → doing → done / failed
  ```
* 支持字段：

  * `plan_id`
  * `dependencies`
  * `priority`
  * `acceptance_criteria`
  * `checks`
  * `last_run`
  * `last_reasons`（结构化失败原因）
* 支持按 `plan_id` 过滤与清理

---

### （三）调度与执行（Controller）

**对应模块：**

* `controller.py`

**已实现功能：**

* 从 `backlog.json` 中挑选：

  * 状态为 `todo`
  * 依赖已完成
  * 类型为 `time_for_certainty` 的任务
* 为每个任务创建独立运行目录：

```
artifacts/runs/<run_id>/
```

* 自动记录：

  * `meta.json`
  * `events.jsonl`
  * `index.md`
* 支持多轮执行（round）：

  * round-0：首次尝试
  * round-n：基于失败原因自动修复
* 执行结束后自动回写任务状态到 backlog

---

### （四）子代理执行与修复（Sub-Agent）

**对应模块：**

* `scripts/subagent_shim.py`
* `schemas/codex_writes.schema.json`

**已实现功能：**

* 子代理只在 **run workspace 内部** 工作，防止越权
* 支持读取：

  * 当前任务规格
  * 验收标准
  * 上一轮的 `rework_request.json`
* 将以下信息注入 Codex Prompt：

  * 任务上下文
  * 验收标准
  * verifier 的结构化失败原因
  * 当前 outputs 快照
* Codex 输出必须符合 JSON Schema：

```json
{
  "writes": [
    { "path": "outputs/xxx", "content": "..." }
  ]
}
```

* 系统自动解析并安全写入文件
* 所有行为均记录为：

  * `shape_response.json`
  * `stdout.txt / stderr.txt`
  * events 日志

---

### （五）验收与验证（Verifier）

**对应模块：**

* `verifier.py`

**已实现功能：**

* verifier 是 **完全确定性的模块**
* 优先使用 backlog 中定义的 `checks`：

  * `file_exists`
  * `file_contains`
  * `command`（支持 timeout）
* 若无 checks，则 fallback 到 legacy 规则（T001 / T002 / T003）
* 每次验证返回：

  * `passed: true / false`
  * `reasons: []`（结构化失败原因）
* 验证结果写入：

```
steps/<step_id>/round-<n>/verification.json
```

* 失败原因会被直接用于下一轮修复 prompt

---

### （六）自动返工闭环（Failure → Repair）

**已实现机制：**

* verifier 失败 → 生成 `rework_request.json`
* 内容包括：

  * why_failed（结构化 reasons）
  * 下一轮修复指令
* subagent 在下一轮 **必须读取并响应失败原因**
* 形成完整闭环：

```
generate → verify → fail → explain → repair → verify
```

---

### （七）审计与可回放性（Audit）

**已实现功能：**

* 每一次 run 都是不可变的审计单元
* 每个 run 目录包含：

  * 输入（task / plan）
  * 过程（events.jsonl）
  * 输出（outputs）
  * 验证（verification.json）
  * 修复请求（rework_request.json）
* 任意一次执行都可以：

  * 回放
  * 对比
  * 定位责任
* 支持按 `plan_id` 清理 backlog，并在 plan 文件中写入 `cleanup_snapshot`

---

## 三、当前系统状态总结

截至目前，系统已经具备：

* ✅ 长任务自动拆解
* ✅ 子任务依赖调度
* ✅ 多轮自动修复
* ✅ 确定性验收
* ✅ LLM 行为受控
* ✅ 完整审计与回放能力

系统已形成一个 **可实际运行、可复现实验结果的 AI 自动执行流水线原型**。

---

`// 2025.12.20 //`

