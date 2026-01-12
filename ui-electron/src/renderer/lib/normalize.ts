/**
 * 数据标准化工具函数
 */

import type { PlanSummary, RunSummary } from "@/apis/types";

// ============================================================
// Normalized Types
// ============================================================

export interface NormalizedPlan {
  id: string;
  tasksCount: number;
  updatedAt: string | number;
  inputTask: string;
  workspacePath?: string;
}

export interface NormalizedRun {
  id: string;
  planId?: string;
  status: string;
  updatedAt: string | number;
  task: string;
  progress?: number;
  mode?: string;
  workspaceMainRoot?: string;
  workspaceStageRoot?: string;
}

// ============================================================
// Plan Normalization
// ============================================================

/**
 * 标准化 Plan 数据
 */
export function normalizePlan(plan: Record<string, unknown>): NormalizedPlan {
  return {
    id: String(plan.id ?? plan.plan_id ?? plan.planId ?? ""),
    tasksCount: Number(plan.tasks_count ?? plan.tasksCount ?? 0),
    updatedAt: (plan.updated_at ?? plan.updatedAt ?? plan.ts ?? "") as string | number,
    inputTask: String(plan.input_task ?? plan.inputTask ?? plan.task ?? ""),
    workspacePath: plan.workspace_path
      ? String(plan.workspace_path)
      : plan.workspacePath
        ? String(plan.workspacePath)
        : undefined,
  };
}

// ============================================================
// Run Normalization
// ============================================================

/**
 * 标准化 Run 数据
 */
export function normalizeRun(run: Record<string, unknown>): NormalizedRun {
  return {
    id: String(run.id ?? run.run_id ?? run.runId ?? ""),
    planId: run.plan_id
      ? String(run.plan_id)
      : run.planId
        ? String(run.planId)
        : undefined,
    status: String(run.status ?? run.state ?? "unknown"),
    updatedAt: (run.updated_at ?? run.updatedAt ?? run.ts ?? "") as string | number,
    task: String(run.task ?? run.input_task ?? ""),
    progress: typeof run.progress === "number" ? run.progress : undefined,
    mode: run.mode ? String(run.mode) : undefined,
    workspaceMainRoot: run.workspace_main_root
      ? String(run.workspace_main_root)
      : run.workspaceMainRoot
        ? String(run.workspaceMainRoot)
        : undefined,
    workspaceStageRoot: run.workspace_stage_root
      ? String(run.workspace_stage_root)
      : run.workspaceStageRoot
        ? String(run.workspaceStageRoot)
        : undefined,
  };
}

// ============================================================
// Timestamp Formatting
// ============================================================

/**
 * 格式化时间戳
 */
export function formatTimestamp(value: unknown): string {
  if (!value) return "-";

  let date: Date;

  if (typeof value === "number") {
    date = new Date(value);
  } else if (typeof value === "string") {
    const parsed = Date.parse(value);
    if (Number.isNaN(parsed)) return "-";
    date = new Date(parsed);
  } else {
    return "-";
  }

  if (Number.isNaN(date.getTime())) return "-";

  return date.toLocaleString();
}

/**
 * 格式化相对时间
 */
export function formatRelativeTime(value: unknown): string {
  if (!value) return "-";

  let timestamp: number;

  if (typeof value === "number") {
    timestamp = value;
  } else if (typeof value === "string") {
    timestamp = Date.parse(value);
    if (Number.isNaN(timestamp)) return "-";
  } else {
    return "-";
  }

  const now = Date.now();
  const diff = now - timestamp;

  if (diff < 0) return "刚刚";

  const seconds = Math.floor(diff / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (days > 0) return `${days}天前`;
  if (hours > 0) return `${hours}小时前`;
  if (minutes > 0) return `${minutes}分钟前`;
  if (seconds > 10) return `${seconds}秒前`;

  return "刚刚";
}

// ============================================================
// Path Normalization
// ============================================================

/**
 * 标准化工作区路径
 */
export function normalizeWorkspacePath(value: string): string {
  return value.replace(/\\/g, "/").trim().toLowerCase();
}

/**
 * 检查路径是否匹配工作区
 */
export function matchesWorkspace(path: string, workspace: string): boolean {
  if (!path || !workspace) return false;
  const normalizedPath = normalizeWorkspacePath(path);
  const normalizedWorkspace = normalizeWorkspacePath(workspace);
  return normalizedPath.startsWith(normalizedWorkspace);
}
