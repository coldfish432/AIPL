/**
 * 事件处理工具函数
 */

import type { RunEvent } from "@/apis/types";

// ============================================================
// Types
// ============================================================

export type StreamState = "connecting" | "connected" | "disconnected";

// ============================================================
// Event Extraction
// ============================================================

/**
 * 从响应中提取事件列表
 */
export function extractEvents(payload: unknown): RunEvent[] {
  if (!payload || typeof payload !== "object") return [];

  const obj = payload as Record<string, unknown>;

  // 直接是数组
  if (Array.isArray(payload)) {
    return payload.filter(isValidEvent);
  }

  // 从 events 字段提取
  if (Array.isArray(obj.events)) {
    return obj.events.filter(isValidEvent);
  }

  // 从 data 字段提取
  if (obj.data && typeof obj.data === "object") {
    return extractEvents(obj.data);
  }

  // 单个事件对象
  if (isValidEvent(obj)) {
    return [obj as RunEvent];
  }

  return [];
}

/**
 * 验证是否为有效事件
 */
function isValidEvent(item: unknown): boolean {
  if (!item || typeof item !== "object") return false;
  const evt = item as Record<string, unknown>;
  return Boolean(
    evt.type || evt.event || evt.name || evt.kind || evt.message || evt.ts
  );
}

// ============================================================
// Event Key & ID
// ============================================================

/**
 * 生成事件唯一键
 */
export function getEventKey(event: RunEvent): string {
  const id = event.event_id ?? "";
  const ts = event.ts ?? event.time ?? event.timestamp ?? event.created_at ?? "";
  const type = formatEventType(event);
  const step = event.step_id ?? event.stepId ?? event.step ?? "";
  const round = event.round ?? "";
  return `${id}-${ts}-${type}-${step}-${round}`;
}

/**
 * 获取事件步骤 ID
 */
export function getEventStepId(event: RunEvent): string | undefined {
  return event.step_id || event.stepId || event.step || undefined;
}

// ============================================================
// Event Type Formatting
// ============================================================

/**
 * 格式化事件类型
 */
export function formatEventType(event: RunEvent): string {
  const raw = event.type || event.event || event.name || event.kind || "";
  return String(raw).toLowerCase().replace(/-/g, "_");
}

/**
 * 获取事件显示类型
 */
export function getEventDisplayType(event: RunEvent): string {
  const type = formatEventType(event);
  return EVENT_TYPE_LABELS[type] || type;
}

/**
 * 获取事件级别
 */
export function getEventLevel(event: RunEvent): "info" | "warn" | "error" | "success" {
  const level = (event.level || event.severity || "").toLowerCase();
  
  if (level === "error" || level === "fatal") return "error";
  if (level === "warn" || level === "warning") return "warn";
  if (level === "success") return "success";
  
  const type = formatEventType(event);
  if (type.includes("failed") || type.includes("error")) return "error";
  if (type.includes("done") || type.includes("completed")) return "success";
  if (type.includes("timeout") || type.includes("retry")) return "warn";
  
  return "info";
}

// ============================================================
// Event Type Labels
// ============================================================

const EVENT_TYPE_LABELS: Record<string, string> = {
  run_init: "运行初始化",
  workspace_stage_ready: "工作区就绪",
  codex_start: "Codex 启动",
  codex_done: "Codex 完成",
  codex_failed: "Codex 失败",
  codex_timeout: "Codex 超时",
  subagent_start: "子代理启动",
  subagent_done: "子代理完成",
  step_round_start: "步骤轮次开始",
  step_round_verified: "步骤验证完成",
  patchset_ready: "补丁集就绪",
  awaiting_review: "等待审核",
  apply_start: "开始应用",
  apply_done: "应用完成",
  discard_done: "丢弃完成",
  run_done: "运行完成",
};

// ============================================================
// Event Timestamp
// ============================================================

/**
 * 获取事件时间戳
 */
export function getEventTimestamp(event: RunEvent): number {
  const ts = event.ts ?? event.time ?? event.timestamp ?? event.created_at;
  
  if (typeof ts === "number") return ts;
  if (typeof ts === "string") {
    const parsed = Date.parse(ts);
    return Number.isNaN(parsed) ? 0 : parsed;
  }
  
  return 0;
}

/**
 * 格式化事件时间
 */
export function formatEventTime(event: RunEvent): string {
  const ts = getEventTimestamp(event);
  if (!ts) return "-";
  
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return "-";
  
  return date.toLocaleTimeString();
}

// ============================================================
// Event Content
// ============================================================

/**
 * 获取事件消息内容
 */
export function getEventMessage(event: RunEvent): string {
  return (
    event.message ||
    event.detail ||
    event.summary ||
    event.task_title ||
    event.taskTitle ||
    event.title ||
    ""
  );
}

/**
 * 获取事件进度信息
 */
export function getEventProgress(event: RunEvent): {
  current: number;
  total: number;
} | null {
  const done =
    event.steps_done ?? event.done_steps ?? event.stepsDone ?? event.doneSteps;
  const total =
    event.step_total ?? event.total_steps ?? event.steps_total ?? event.stepTotal;

  if (typeof done === "number" && typeof total === "number" && total > 0) {
    return { current: done, total };
  }

  if (typeof event.progress === "number") {
    return { current: event.progress, total: 100 };
  }

  return null;
}
