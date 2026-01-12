/**
 * 状态处理工具函数
 */

import type { ExecutionStatus, ReviewStatus, UnifiedStatus } from "@/apis/types";

// ============================================================
// Status Map
// ============================================================

const STATUS_MAP: Record<string, UnifiedStatus> = {
  todo: { execution: "queued", review: null },
  queued: { execution: "queued", review: null },
  starting: { execution: "starting", review: null },
  doing: { execution: "running", review: null },
  running: { execution: "running", review: null },
  retrying: { execution: "retrying", review: null },
  stale: { execution: "running", review: null },
  awaiting_review: { execution: "completed", review: "pending" },
  awaitingreview: { execution: "completed", review: "pending" },
  done: { execution: "completed", review: "applied" },
  success: { execution: "completed", review: "applied" },
  completed: { execution: "completed", review: "applied" },
  failed: { execution: "failed", review: null },
  error: { execution: "failed", review: null },
  canceled: { execution: "canceled", review: null },
  cancelled: { execution: "canceled", review: null },
  discarded: { execution: "discarded", review: null },
};

// ============================================================
// Status Labels
// ============================================================

export const EXECUTION_STATUS_LABELS: Record<ExecutionStatus, string> = {
  queued: "排队中",
  starting: "启动中",
  running: "执行中",
  retrying: "重试中",
  completed: "已完成",
  failed: "失败",
  canceled: "已取消",
  discarded: "已丢弃",
};

export const REVIEW_STATUS_LABELS: Record<ReviewStatus, string> = {
  none: "-",
  pending: "待审核",
  approved: "已通过",
  applied: "已应用",
  rejected: "已拒绝",
  reworking: "返工中",
};

// ============================================================
// Status Functions
// ============================================================

/**
 * 标准化后端状态
 */
export function normalizeBackendStatus(raw: string | null | undefined): UnifiedStatus {
  if (!raw) return { execution: "running", review: null };
  const normalized = String(raw).trim().toLowerCase().replace(/-/g, "_");
  return STATUS_MAP[normalized] || { execution: "running", review: null };
}

/**
 * 从任务列表推导状态
 */
export function deriveStatusFromTasks(
  tasks: Array<{ status?: string }> | null | undefined
): ExecutionStatus | null {
  if (!Array.isArray(tasks) || tasks.length === 0) return null;
  
  const states = tasks.map((t) => String(t?.status || "todo").toLowerCase());
  
  if (states.every((s) => s === "done")) return "completed";
  if (states.some((s) => s === "failed")) return "failed";
  if (states.some((s) => s === "canceled")) return "canceled";
  if (states.some((s) => ["doing", "todo", "stale", "running"].includes(s))) {
    return "running";
  }
  
  return null;
}

/**
 * 解析统一状态
 */
export function resolveStatus(
  backendStatus: string | null | undefined,
  tasks?: Array<{ status?: string }> | null
): UnifiedStatus {
  const backend = normalizeBackendStatus(backendStatus);
  
  if (backend.review === "pending") return backend;
  
  const derived = deriveStatusFromTasks(tasks);
  
  if (derived) {
    if (derived === "running" && ["failed", "canceled", "discarded"].includes(backend.execution)) {
      return { execution: "retrying", review: null };
    }
    if (derived === "completed") {
      return { execution: "completed", review: backend.review || "pending" };
    }
    return { execution: derived, review: null };
  }
  
  return backend;
}

/**
 * 获取状态显示文本
 */
export function getStatusDisplayText(status: UnifiedStatus): string {
  if (status.execution === "completed" && status.review) {
    return REVIEW_STATUS_LABELS[status.review];
  }
  return EXECUTION_STATUS_LABELS[status.execution];
}

/**
 * 获取状态 CSS 类名
 */
export function getStatusClassName(status: UnifiedStatus): string {
  if (status.execution === "completed" && status.review) {
    return `status-${status.review}`;
  }
  return `status-${status.execution}`;
}

/**
 * 判断是否已结束
 */
export function isFinished(status: ExecutionStatus): boolean {
  return ["completed", "failed", "canceled", "discarded"].includes(status);
}

/**
 * 判断是否需要审核
 */
export function needsReview(status: UnifiedStatus): boolean {
  return status.execution === "completed" && status.review === "pending";
}

/**
 * 判断是否正在运行
 */
export function isRunning(status: ExecutionStatus): boolean {
  return ["queued", "starting", "running", "retrying"].includes(status);
}

/**
 * 判断是否可以重试
 */
export function canRetry(status: ExecutionStatus): boolean {
  return ["failed", "canceled", "discarded"].includes(status);
}
