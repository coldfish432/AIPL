/**
 * API 服务层
 * 统一管理所有 API 调用
 */

import { API_BASE_URL } from "@/config/settings";

const BASE_URL = API_BASE_URL || "http://127.0.0.1:18088";

// ============================================================
// Types
// ============================================================

export interface ApiError {
  error?: string;
  code?: string;
  message?: string;
}

export class AiplError extends Error {
  code: string;
  details?: Record<string, unknown>;

  constructor(message: string, code = "UNKNOWN", details?: Record<string, unknown>) {
    super(message);
    this.name = "AiplError";
    this.code = code;
    this.details = details;
  }
}

export type ChatMessage = {
  role: "user" | "assistant" | "system";
  content: string;
};

export type AssistantChatResponse = {
  reply?: string;
  message?: string;
  intent?: "task" | "question" | null;
  task_summary?: string;
  taskSummary?: string;
  task_files?: string[];
  taskFiles?: string[];
  task_operations?: string[];
  taskOperations?: string[];
};

export interface AssistantStreamEvent {
  type: "start" | "stderr" | "heartbeat" | "reply" | "error" | "log" | string;
  ts?: number;
  line?: string;
  message?: string;
  data?: AssistantChatResponse;
  idle?: number;
}

export type PlanSummary = {
  id?: string;
  plan_id?: string;
  planId?: string;
  tasks_count?: number;
  tasksCount?: number;
  updated_at?: string | number;
  updatedAt?: string | number;
  ts?: string | number;
  input_task?: string;
  inputTask?: string;
  task?: string;
};

export type RunSummary = {
  id?: string;
  run_id?: string;
  runId?: string;
  plan_id?: string;
  planId?: string;
  status?: string;
  state?: string;
  updated_at?: string | number;
  updatedAt?: string | number;
  ts?: string | number;
  task?: string;
  input_task?: string;
  progress?: number;
  mode?: string;
};

export type PlanTask = {
  id?: string;
  step_id?: string;
  task_id?: string;
  title?: string;
  description?: string;
  name?: string;
  status?: string;
  dependencies?: string[];
};

export type PlanInfo = {
  plan_id?: string;
  planId?: string;
  input_task?: string;
  inputTask?: string;
  raw_plan?: { tasks?: PlanTask[] };
  task_chain_text?: string;
};

export type PlanDetailResponse = {
  plan?: PlanInfo;
  snapshot?: { tasks?: PlanTask[] };
  task_chain_text?: string;
};

export type RunInfo = {
  run_id?: string;
  runId?: string;
  plan_id?: string;
  planId?: string;
  status?: string;
  state?: string;
  task?: string;
  input_task?: string;
  updated_at?: string | number;
  mode?: string;
  patchset_path?: string;
  changed_files_count?: number;
};

export type RunDetailResponse = {
  run?: RunInfo;
} & RunInfo;

export type RunEvent = {
  event_id?: number;
  ts?: number | string;
  type?: string;
  event?: string;
  name?: string;
  message?: string;
  detail?: string;
  task_title?: string;
  status?: string;
  level?: string;
  progress?: number;
  step_id?: string;
  step?: string;
  round?: number | string;
  task_id?: string;
};

export type RunEventsResponse = {
  run_id?: string;
  cursor?: number;
  events?: RunEvent[];
};

// ============================================================
// Request Utilities
// ============================================================

type ApiEnvelope<T> = {
  ok?: boolean;
  data?: T;
  error?: string;
};

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const hasBody = Boolean(options?.body);
  const headers: HeadersInit = {
    ...(hasBody ? { "Content-Type": "application/json" } : {}),
  };

  const res = await fetch(`${BASE_URL}${path}`, { headers, ...options });
  const body = (await res.json().catch(() => null)) as ApiEnvelope<T> | T | null;

  if (!res.ok) {
    if (body && typeof body === "object" && "error" in (body as ApiError)) {
      throw new AiplError((body as ApiError).error || `HTTP ${res.status}`, "API_ERROR");
    }
    throw new AiplError(`HTTP ${res.status}`, "HTTP_ERROR");
  }

  if (body && typeof body === "object" && "ok" in body && (body as ApiEnvelope<T>).ok === false) {
    throw new AiplError((body as ApiEnvelope<T>).error || "Request failed", "API_ERROR");
  }

  if (body && typeof body === "object" && "data" in (body as ApiEnvelope<T>)) {
    return (body as ApiEnvelope<T>).data as T;
  }

  return body as T;
}

function buildQueryString(params: Record<string, string | number | undefined>): string {
  const entries = Object.entries(params)
    .filter(([, v]) => v !== undefined)
    .map(([k, v]) => [k, String(v)]);
  if (entries.length === 0) return "";
  return "?" + new URLSearchParams(entries as [string, string][]).toString();
}

// ============================================================
// Workspace API
// ============================================================

export async function detectWorkspace(workspace: string): Promise<Record<string, unknown>> {
  const query = buildQueryString({ workspace });
  return request(`/api/workspace/detect${query}`);
}

export async function getWorkspaceInfo(workspace?: string): Promise<Record<string, unknown>> {
  const query = buildQueryString({ workspace });
  return request(`/api/workspace/info${query}`);
}

export type FileTreeNode = {
  name: string;
  type: "file" | "directory";
  path: string;
  children?: FileTreeNode[];
};

export async function getWorkspaceTree(
  workspace: string,
  depth: number = 3
): Promise<{ tree: FileTreeNode; workspace: string }> {
  const query = buildQueryString({ workspace, depth });
  return request(`/api/workspace/tree${query}`);
}

export async function readWorkspaceFile(
  workspace: string,
  path: string
): Promise<{ path: string; content: string; size: number; lines: number }> {
  const query = buildQueryString({ workspace, path });
  return request(`/api/workspace/read${query}`);
}

// ============================================================
// Plan API
// ============================================================

export async function listPlans(workspace?: string): Promise<PlanSummary[]> {
  const query = buildQueryString({ workspace });
  const data = await request<PlanSummary[]>(`/api/plans${query}`);
  return Array.isArray(data) ? data : [];
}

export async function getPlan(planId: string): Promise<PlanDetailResponse> {
  return request(`/api/plans/${encodeURIComponent(planId)}`);
}

export async function deletePlan(planId: string): Promise<void> {
  return request(`/api/plans/${encodeURIComponent(planId)}`, { method: "DELETE" });
}

export async function reworkPlan(planId: string): Promise<{ run_id?: string; runId?: string }> {
  return request(`/api/plans/${encodeURIComponent(planId)}/rework`, { method: "POST" });
}

export async function startRun(planId: string): Promise<{ run_id?: string; runId?: string }> {
  return request(`/api/plans/${encodeURIComponent(planId)}/run`, { method: "POST" });
}

// ============================================================
// Run API
// ============================================================

export async function listRuns(workspace?: string): Promise<RunSummary[]> {
  const query = buildQueryString({ workspace });
  const data = await request<RunSummary[]>(`/api/runs${query}`);
  return Array.isArray(data) ? data : [];
}

export async function getRun(runId: string, planId?: string): Promise<RunDetailResponse> {
  const query = buildQueryString({ planId });
  return request(`/api/runs/${encodeURIComponent(runId)}${query}`);
}

export async function getRunEvents(
  runId: string,
  planId?: string,
  cursor = 0,
  limit = 100
): Promise<RunEventsResponse> {
  const query = buildQueryString({ planId, cursor, limit });
  return request(`/api/runs/${encodeURIComponent(runId)}/events${query}`);
}

export function streamRunEvents(runId: string, planId?: string): EventSource {
  const query = buildQueryString({ planId });
  return new EventSource(`${BASE_URL}/api/runs/${encodeURIComponent(runId)}/events/stream${query}`);
}

export async function applyRun(runId: string, planId?: string): Promise<RunDetailResponse> {
  const query = buildQueryString({ planId });
  return request(`/api/runs/${encodeURIComponent(runId)}/apply${query}`, { method: "POST" });
}

export async function cancelRun(runId: string, planId?: string): Promise<RunDetailResponse> {
  const query = buildQueryString({ planId });
  return request(`/api/runs/${encodeURIComponent(runId)}/cancel${query}`, { method: "POST" });
}

export async function discardRun(runId: string, planId?: string): Promise<RunDetailResponse> {
  const query = buildQueryString({ planId });
  return request(`/api/runs/${encodeURIComponent(runId)}/discard${query}`, { method: "POST" });
}

export async function deleteRun(runId: string, planId?: string): Promise<void> {
  const query = buildQueryString({ planId });
  return request(`/api/runs/${encodeURIComponent(runId)}${query}`, { method: "DELETE" });
}

// ============================================================
// Assistant API
// ============================================================

export async function assistantChat(
    messages: ChatMessage[],
    workspace?: string
  ): Promise<AssistantChatResponse> {
    return request(`/api/assistant/chat`, {
      method: "POST",
      body: JSON.stringify({ messages, workspace }),
    });
  }

export async function assistantChatStream(
  messages: ChatMessage[],
  workspace: string | undefined,
  onEvent: (event: AssistantStreamEvent) => void
): Promise<AssistantChatResponse | null> {
  const res = await fetch(`${BASE_URL}/api/assistant/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify({ messages, workspace }),
  });
  if (!res.ok) {
    throw new AiplError(`Assistant stream failed: ${res.statusText || res.status}`, "STREAM_ERROR");
  }

  const reader = res.body?.getReader();
  if (!reader) {
    throw new AiplError("Stream not supported by this browser", "STREAM_ERROR");
  }

  const decoder = new TextDecoder();
  let buffer = "";
  let finalData: AssistantChatResponse | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed.startsWith("data:")) {
        continue;
      }
      const payload = trimmed.slice(5).trim();
      if (!payload) {
        continue;
      }

      let event: AssistantStreamEvent;
      try {
        event = JSON.parse(payload);
      } catch {
        continue;
      }

      if (event.type === "reply" && event.data) {
        finalData = event.data;
      }
      onEvent(event);
    }
  }

  if (buffer.trim().startsWith("data:")) {
    const payload = buffer.trim().slice(5).trim();
    if (payload) {
      try {
        const event: AssistantStreamEvent = JSON.parse(payload);
        if (event.type === "reply" && event.data) {
          finalData = event.data;
        }
        onEvent(event);
      } catch {
        // ignore
      }
    }
  }

  return finalData;
}

export async function assistantPlan(
    messages: ChatMessage[],
    workspace?: string
  ): Promise<{ plan_id?: string; planId?: string; tasks_count?: number; task_chain_text?: string }> {
    return request(`/api/assistant/plan`, {
      method: "POST",
      body: JSON.stringify({ messages, workspace }),
    });
  }

export async function assistantConfirm(
  planId: string,
  workspace?: string,
  mode?: string
): Promise<{ run_id?: string; runId?: string; plan_id?: string; planId?: string; status?: string }> {
  return request(`/api/assistant/confirm`, {
    method: "POST",
    body: JSON.stringify({
      planId,
      workspace,
      mode: mode || "autopilot",
    }),
  });
}

// ============================================================
// Profile API
// ============================================================

export async function getProfile(workspace?: string): Promise<Record<string, unknown>> {
  const query = buildQueryString({ workspace });
  return request(`/api/profile${query}`);
}

// ============================================================
// Pack API
// ============================================================

export async function listLanguagePacks(): Promise<Record<string, unknown>[]> {
  const data = await request<Record<string, unknown>[]>("/api/language-packs");
  return Array.isArray(data) ? data : [];
}

export async function listExperiencePacks(): Promise<Record<string, unknown>[]> {
  const data = await request<Record<string, unknown>[]>("/api/experience-packs");
  return Array.isArray(data) ? data : [];
}

export async function importLanguagePack(pack: Record<string, unknown>): Promise<{ id?: string }> {
  return request("/api/language-packs/import", {
    method: "POST",
    body: JSON.stringify({ pack }),
  });
}

export async function importExperiencePack(pack: Record<string, unknown>): Promise<{ id?: string }> {
  return request("/api/experience-packs/import", {
    method: "POST",
    body: JSON.stringify({ pack }),
  });
}

export async function deleteLanguagePack(id: string): Promise<void> {
  return request(`/api/language-packs/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export async function deleteExperiencePack(id: string): Promise<void> {
  return request(`/api/experience-packs/${encodeURIComponent(id)}`, { method: "DELETE" });
}

// ============================================================
// Workspace Memory API
// ============================================================

export async function getWorkspaceMemory(workspaceId: string): Promise<Record<string, unknown>> {
  return request(`/api/workspace/${encodeURIComponent(workspaceId)}/memory`);
}

export async function addWorkspaceRule(
  workspaceId: string,
  data: { content: string; scope?: string; category?: string }
): Promise<{ id?: string }> {
  return request(`/api/workspace/${encodeURIComponent(workspaceId)}/rules`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function deleteWorkspaceRule(workspaceId: string, ruleId: string): Promise<void> {
  return request(`/api/workspace/${encodeURIComponent(workspaceId)}/rules/${encodeURIComponent(ruleId)}`, {
    method: "DELETE",
  });
}

export async function addWorkspaceCheck(
  workspaceId: string,
  data: { check: Record<string, unknown>; scope?: string }
): Promise<{ id?: string }> {
  return request(`/api/workspace/${encodeURIComponent(workspaceId)}/checks`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function deleteWorkspaceCheck(workspaceId: string, checkId: string): Promise<void> {
  return request(`/api/workspace/${encodeURIComponent(workspaceId)}/checks/${encodeURIComponent(checkId)}`, {
    method: "DELETE",
  });
}

export async function updateProfile(
  workspace: string,
  userHard: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const query = buildQueryString({ workspace });
  return request(`/api/profile${query}`, {
    method: "PUT",
    body: JSON.stringify({ user_hard: userHard }),
  });
}
