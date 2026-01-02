# 队列链式执行与分段审核设计方案 v3

## 一、需求概述

### 1.1 核心目标

1. 实现多任务链（Plan）的自动顺序执行，支持动态缓存继承和人类分段审核
2. **统一 Pilot 队列状态和 Dashboard 运行状态，解决状态冲突**

### 1.2 关键特性

| 特性 | 描述 |
|------|------|
| **持续执行** | 队列持续执行，不管前一个任务是否完成都继续下一个 |
| **动态缓存继承** | 只继承最近一个**已完成**任务的缓存，跳过未完成的 |
| **独立审核** | 每个完成的任务有独立 patchset，人类可任意时刻审核 |
| **无缓存任务** | 未完成（失败/取消）的任务不维护缓存，不影响后续任务 |
| **状态统一** | Pilot 和 Dashboard 使用统一的状态定义和推导逻辑 |

### 1.3 流程示意

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      动态缓存继承执行流程                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  场景：Plan A 完成，Plan B 失败，Plan C 继续执行                              │
│                                                                             │
│  ┌─────────┐     ┌─────────┐     ┌─────────┐                               │
│  │ Plan A  │ ──► │ Plan B  │ ──► │ Plan C  │                               │
│  │ 完成 ✓  │     │ 失败 ✗  │     │ 执行中  │                               │
│  └────┬────┘     └────┬────┘     └────┬────┘                               │
│       │               │               │                                     │
│       ▼               ▼               │                                     │
│   Patch A         (无缓存)            │                                     │
│   (待审核)         跳过               │                                     │
│       │                               │                                     │
│       └───────────────────────────────┘                                     │
│                       │                                                     │
│                       ▼                                                     │
│              C 继承 A 的缓存执行                                             │
│              (跳过 B，因为 B 未完成)                                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、现状问题分析

### 2.1 状态冲突问题

当前 Pilot 和 Dashboard 存在以下冲突：

```
┌─────────────────────────────────────────────────────────────────┐
│                      当前状态冲突                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  后端返回状态:                                                   │
│  running, awaiting_review, done, failed, canceled, doing, todo  │
│                                                                 │
│         ┌─────────────────┐     ┌─────────────────┐            │
│         │     Pilot       │     │   Dashboard     │            │
│         │   useQueue.ts   │     │  RunDetail.tsx  │            │
│         └────────┬────────┘     └────────┬────────┘            │
│                  │                       │                      │
│                  ▼                       ▼                      │
│  ┌───────────────────────┐  ┌───────────────────────┐          │
│  │ normalizeRunStatus()  │  │ taskDerivedStatus()   │          │
│  │                       │  │                       │          │
│  │ • todo → "starting"   │  │ • todo → "running"    │ ← 冲突！ │
│  │ • [todo,done] →       │  │ • [todo,done] →       │          │
│  │   "queued"            │  │   "running"           │ ← 冲突！ │
│  └───────────────────────┘  └───────────────────────┘          │
│                                                                 │
│  结果：同一个 Run 在两处显示不同状态                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 冲突代码位置

**Pilot.tsx (第47-61行):**
```typescript
function resolveSnapshotStatus(tasks): QueueStatus | null {
  if (first === "todo") return "starting";   // ← 问题1
  if (states.some((s) => s === "todo")) return "queued";  // ← 问题2
}
```

**RunDetail.tsx (第201-209行):**
```typescript
const taskDerivedStatus = useMemo(() => {
  if (states.some((state) => state === "todo")) return "running";  // ← 不同逻辑
}, [planTasks]);
```

---

## 三、架构设计

### 3.1 状态统一层

新增 `lib/status.ts` 作为**唯一的状态处理模块**：

```
┌─────────────────────────────────────────────────────────────────┐
│                      状态统一架构                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  后端返回 (各种格式):                                            │
│  running, awaiting_review, done, failed, doing, todo, stale...  │
│                                                                 │
│                          │                                      │
│                          ▼                                      │
│              ┌───────────────────────┐                          │
│              │    lib/status.ts      │  ← 统一状态模块           │
│              │                       │                          │
│              │ • normalizeStatus()   │  标准化后端状态           │
│              │ • deriveFromTasks()   │  从任务推导状态           │
│              │ • getDisplayText()    │  获取显示文本             │
│              └───────────┬───────────┘                          │
│                          │                                      │
│           ┌──────────────┼──────────────┐                       │
│           │              │              │                       │
│           ▼              ▼              ▼                       │
│    ┌───────────┐  ┌───────────┐  ┌───────────┐                 │
│    │  Pilot    │  │ Dashboard │  │ RunDetail │                 │
│    │           │  │           │  │           │                 │
│    │ 统一状态  │  │ 统一状态  │  │ 统一状态  │  ← 一致！        │
│    └───────────┘  └───────────┘  └───────────┘                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 统一状态定义

```typescript
/** 执行状态 */
ExecutionStatus:
  | "queued"      // 排队中
  | "starting"    // 启动中
  | "running"     // 执行中
  | "completed"   // 已完成
  | "failed"      // 失败
  | "canceled"    // 已取消
  | "discarded"   // 已丢弃

/** 审核状态（仅 completed 有效） */
ReviewStatus:
  | "pending"     // 待审核 (原 awaiting_review)
  | "approved"    // 已通过
  | "applied"     // 已应用 (原 done)
  | "rejected"    // 已拒绝
  | "reworking"   // 返工中
```

### 3.3 状态映射规则

| 后端状态 | ExecutionStatus | ReviewStatus | UI 显示 |
|---------|----------------|--------------|---------|
| `todo` | `queued` | - | 排队中 |
| `doing` | `running` | - | 执行中 |
| `running` | `running` | - | 执行中 |
| `stale` | `running` | - | 执行中 |
| `awaiting_review` | `completed` | `pending` | 待审核 |
| `done` | `completed` | `applied` | 已应用 |
| `success` | `completed` | `applied` | 已应用 |
| `failed` | `failed` | - | 失败 |
| `canceled` | `canceled` | - | 已取消 |
| `discarded` | `discarded` | - | 已丢弃 |

### 3.4 任务推导规则（统一）

```typescript
// 从 plan tasks 推导状态的统一逻辑
function deriveStatusFromTasks(tasks): ExecutionStatus | null {
  const states = tasks.map(t => t.status?.toLowerCase() || "todo");
  
  if (states.every(s => s === "done")) return "completed";
  if (states.some(s => s === "failed")) return "failed";
  if (states.some(s => s === "canceled")) return "canceled";
  
  // 统一：有任何 doing/todo/stale → running
  // 不再区分 starting/queued
  if (states.some(s => ["doing", "todo", "stale"].includes(s))) {
    return "running";
  }
  
  return null;
}
```

---

## 四、详细设计

### 4.1 统一状态模块

**文件：** `lib/status.ts`

```typescript
// lib/status.ts - 统一状态处理模块

// ============================================================
// 类型定义
// ============================================================

export type ExecutionStatus =
  | "queued" | "starting" | "running" | "completed"
  | "failed" | "canceled" | "discarded";

export type ReviewStatus =
  | "pending" | "approved" | "applied" | "rejected" | "reworking";

export interface UnifiedStatus {
  execution: ExecutionStatus;
  review: ReviewStatus | null;
}

// ============================================================
// 状态标准化
// ============================================================

const STATUS_MAP: Record<string, UnifiedStatus> = {
  // 排队/待办
  "todo": { execution: "queued", review: null },
  "queued": { execution: "queued", review: null },
  
  // 启动中
  "starting": { execution: "starting", review: null },
  
  // 执行中
  "doing": { execution: "running", review: null },
  "running": { execution: "running", review: null },
  "stale": { execution: "running", review: null },
  
  // 完成 - 待审核
  "awaiting_review": { execution: "completed", review: "pending" },
  "awaitingreview": { execution: "completed", review: "pending" },
  
  // 完成 - 已应用
  "done": { execution: "completed", review: "applied" },
  "success": { execution: "completed", review: "applied" },
  "completed": { execution: "completed", review: "applied" },
  
  // 失败
  "failed": { execution: "failed", review: null },
  "error": { execution: "failed", review: null },
  
  // 取消
  "canceled": { execution: "canceled", review: null },
  "cancelled": { execution: "canceled", review: null },
  
  // 丢弃
  "discarded": { execution: "discarded", review: null },
};

export function normalizeBackendStatus(raw: string | undefined | null): UnifiedStatus {
  if (!raw) return { execution: "running", review: null };
  
  const normalized = String(raw).trim().toLowerCase().replace(/-/g, "_");
  return STATUS_MAP[normalized] || { execution: "running", review: null };
}

// ============================================================
// 从任务列表推导状态
// ============================================================

export function deriveStatusFromTasks(
  tasks: Array<{ status?: string }> | null | undefined
): ExecutionStatus | null {
  if (!Array.isArray(tasks) || tasks.length === 0) return null;
  
  const states = tasks.map((t) => String(t?.status || "todo").toLowerCase());
  
  if (states.every((s) => s === "done")) return "completed";
  if (states.some((s) => s === "failed")) return "failed";
  if (states.some((s) => s === "canceled")) return "canceled";
  
  // 统一：有 doing/todo/stale → running
  if (states.some((s) => ["doing", "todo", "stale", "running"].includes(s))) {
    return "running";
  }
  
  return null;
}

export function resolveStatus(
  backendStatus: string | undefined | null,
  tasks?: Array<{ status?: string }> | null
): UnifiedStatus {
  const backend = normalizeBackendStatus(backendStatus);
  
  // awaiting_review 优先保留
  if (backend.review === "pending") return backend;
  
  // 尝试从任务推导
  const derived = deriveStatusFromTasks(tasks);
  if (derived) {
    if (derived === "completed") {
      return { execution: "completed", review: backend.review || "pending" };
    }
    return { execution: derived, review: null };
  }
  
  return backend;
}

// ============================================================
// UI 显示
// ============================================================

export const EXECUTION_STATUS_LABELS: Record<ExecutionStatus, string> = {
  queued: "排队中",
  starting: "启动中",
  running: "执行中",
  completed: "已完成",
  failed: "失败",
  canceled: "已取消",
  discarded: "已丢弃",
};

export const REVIEW_STATUS_LABELS: Record<ReviewStatus, string> = {
  pending: "待审核",
  approved: "已通过",
  applied: "已应用",
  rejected: "已拒绝",
  reworking: "返工中",
};

export function getStatusDisplayText(status: UnifiedStatus): string {
  if (status.execution === "completed" && status.review) {
    return REVIEW_STATUS_LABELS[status.review];
  }
  return EXECUTION_STATUS_LABELS[status.execution];
}

export function getStatusClassName(status: UnifiedStatus): string {
  if (status.execution === "completed" && status.review) {
    return `status-${status.review}`;
  }
  return `status-${status.execution}`;
}

// ============================================================
// 队列控制逻辑
// ============================================================

export function isFinished(status: ExecutionStatus): boolean {
  return ["completed", "failed", "canceled", "discarded"].includes(status);
}

export function hasCache(status: ExecutionStatus): boolean {
  return status === "completed";
}

export function needsReview(status: UnifiedStatus): boolean {
  return status.execution === "completed" && status.review === "pending";
}
```

### 4.2 ChainWorkspaceManager

**文件：** `services/chain_workspace.py`

```python
# services/chain_workspace.py

class ChainWorkspaceManager:
    """管理批次执行的链式工作区（动态缓存继承）"""

    def __init__(self, root: Path):
        self._root = root
        self._chains_dir = root / "artifacts" / "chains"

    def create_chain(self, batch_id: str, main_root: Path) -> dict:
        """创建新的链式工作区"""
        chain_dir = self._chains_dir / batch_id
        workspace_dir = chain_dir / "workspace"
        
        # 从 main_root 复制初始状态
        shutil.copytree(main_root, workspace_dir, ignore=...)
        
        # 创建初始快照
        initial_snapshot = chain_dir / "initial_snapshot.tar.gz"
        self._create_snapshot(workspace_dir, initial_snapshot)
        
        meta = {
            "batch_id": batch_id,
            "main_root": str(main_root),
            "latest_completed_run": None,
            "latest_snapshot": str(initial_snapshot),
        }
        write_json(chain_dir / "meta.json", meta)
        return meta

    def get_inherit_source(self, batch_id: str) -> dict:
        """获取缓存继承来源（最新 completed 的快照）"""
        chain_meta = read_json(self._chains_dir / batch_id / "meta.json")
        latest_run = chain_meta.get("latest_completed_run")
        latest_snapshot = chain_meta.get("latest_snapshot")
        
        return {
            "source": f"run_{latest_run}" if latest_run else "initial",
            "snapshot_path": latest_snapshot,
            "inherited_from_run": latest_run,
        }

    def create_run_stage(self, batch_id: str, run_id: str, ...) -> dict:
        """为 run 创建执行环境（从最新快照恢复）"""
        inherit_info = self.get_inherit_source(batch_id)
        snapshot_path = Path(inherit_info["snapshot_path"])
        
        # 从快照恢复到 stage
        self._restore_snapshot(snapshot_path, stage_dir)
        
        return {
            "stage_root": str(stage_dir),
            "inherited_from": inherit_info["inherited_from_run"],
        }

    def complete_run(self, batch_id: str, run_id: str) -> dict:
        """标记完成，生成快照，更新链"""
        # 1. 生成 patchset
        # 2. 生成快照
        # 3. 更新 latest_completed_run 和 latest_snapshot
        ...

    def fail_run(self, batch_id: str, run_id: str, error: str = "") -> dict:
        """标记失败（不产出缓存，不更新链）"""
        ...
```

### 4.3 前端组件修改

**Pilot.tsx:**
```typescript
import { resolveStatus, isFinished } from "../lib/status";

const pollQueue = useCallback(async () => {
  for (const item of activeItems) {
    const res = await getRun(item.runId, item.planId);
    const tasks = (await getPlan(item.planId))?.snapshot?.tasks || [];
    
    // 使用统一状态模块
    const unified = resolveStatus(res.status, tasks);
    
    updateItem(item.id, (q) => ({
      ...q,
      status: unified.execution,
      reviewStatus: unified.review || undefined,
    }));
  }
  
  // 继续执行下一个（不管成功失败）
  if (!pausedRef.current && !hasActive) {
    void startNextQueued();
  }
}, [...]);
```

**RunDetail.tsx:**
```typescript
import { resolveStatus, getStatusDisplayText } from "../lib/status";

const unifiedStatus = useMemo(() => {
  return resolveStatus(runInfo?.status, planTasks);
}, [runInfo, planTasks]);

const statusText = getStatusDisplayText(unifiedStatus);
```

**Dashboard.tsx:**
```typescript
import { normalizeBackendStatus, getStatusDisplayText } from "../lib/status";

const unified = normalizeBackendStatus(run.status);
const statusText = getStatusDisplayText(unified);
```

---

## 五、数据流图

```
┌────────────────────────────────────────────────────────────────────────────┐
│                        统一状态处理流程                                      │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  后端 API 响应: { "status": "awaiting_review", "tasks": [...] }            │
│                                                                            │
│                          │                                                 │
│                          ▼                                                 │
│              ┌───────────────────────┐                                     │
│              │    lib/status.ts      │                                     │
│              │                       │                                     │
│              │  resolveStatus() ──►  │                                     │
│              │  {                    │                                     │
│              │    execution: "completed",                                  │
│              │    review: "pending"  │                                     │
│              │  }                    │                                     │
│              └───────────┬───────────┘                                     │
│                          │                                                 │
│           ┌──────────────┼──────────────┐                                  │
│           ▼              ▼              ▼                                  │
│    ┌───────────┐  ┌───────────┐  ┌───────────┐                            │
│    │  Pilot    │  │ Dashboard │  │ RunDetail │                            │
│    │ "待审核"  │  │ "待审核"  │  │ "待审核"  │  ← 一致！                   │
│    └───────────┘  └───────────┘  └───────────┘                            │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 六、状态对照表

| 后端原始 | ExecutionStatus | ReviewStatus | UI 显示 | 产出缓存 | 阻塞队列 |
|---------|----------------|--------------|---------|---------|---------|
| `todo` | `queued` | - | 排队中 | - | 否 |
| `doing` | `running` | - | 执行中 | - | 是 |
| `running` | `running` | - | 执行中 | - | 是 |
| `awaiting_review` | `completed` | `pending` | 待审核 | ✓ | 否 |
| `done` | `completed` | `applied` | 已应用 | ✓ | 否 |
| `failed` | `failed` | - | 失败 | ✗ | 否 |
| `canceled` | `canceled` | - | 已取消 | ✗ | 否 |

---

## 七、实施计划

| 阶段 | 任务 | 文件 | 优先级 |
|------|------|------|-------|
| **1** | 新增统一状态模块 | `lib/status.ts` | P0 |
| **2** | 修改 Pilot | `Pilot.tsx` | P0 |
| **3** | 修改 RunDetail | `RunDetail.tsx` | P0 |
| **4** | 修改 Dashboard | `Dashboard.tsx` | P0 |
| **5** | 修改 useQueue | `useQueue.ts` | P1 |
| **6** | 实现 ChainWorkspaceManager | `chain_workspace.py` | P1 |
| **7** | 添加 CLI 命令 | `engine_cli.py` | P1 |
| **8** | 添加 API 端点 | Java 服务层 | P2 |
| **9** | 重构 QueuePanel | `QueuePanel.tsx` | P2 |

---

## 八、变更文件清单

| 操作 | 文件路径 | 描述 |
|------|---------|------|
| **新增** | `src/lib/status.ts` | 统一状态处理模块 |
| **新增** | `services/chain_workspace.py` | 链式工作区管理器 |
| **修改** | `src/hooks/useQueue.ts` | 使用统一状态类型 |
| **修改** | `src/pages/Pilot.tsx` | 使用 `resolveStatus()` |
| **修改** | `src/pages/RunDetail.tsx` | 使用 `resolveStatus()` |
| **修改** | `src/pages/Dashboard.tsx` | 使用 `normalizeBackendStatus()` |
| **修改** | `src/components/QueuePanel.tsx` | 使用统一状态显示 |
| **修改** | `engine_cli.py` | 添加链式工作区命令 |

---

## 九、测试要点

### 9.1 状态一致性测试

- [ ] 同一 Run 在 Pilot 和 Dashboard 显示相同状态
- [ ] `awaiting_review` 统一显示为 "待审核"
- [ ] `done` 统一显示为 "已应用"
- [ ] 任务推导逻辑在两处结果一致

### 9.2 队列执行测试

- [ ] 多任务链顺序执行
- [ ] `completed` 状态不阻塞队列
- [ ] `failed` 状态不阻塞队列
- [ ] 缓存正确继承最新 completed

### 9.3 审核流程测试

- [ ] 独立审核各任务
- [ ] 应用到主库正确
- [ ] 返工不影响其他任务
