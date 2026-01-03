import { API_BASE_URL } from "./config/settings";
import { AiplError, ApiError } from "./lib/errors";

const BASE_URL = API_BASE_URL;

type ApiEnvelope<T> = {
  ok?: boolean;
  data?: T;
  error?: string;
};

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
  policy?: string;
  changed_files_count?: number;
  patchset_path?: string;
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
  capabilities?: string[];
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
  updatedAt?: string | number;
  ts?: string | number;
  mode?: string;
  policy?: string;
  patchset_path?: string;
  changed_files_count?: number;
  workspace_main_root?: string;
  workspace_stage_root?: string;
};

export type RunDetailResponse = {
  run?: RunInfo;
} & RunInfo;

export type RunEvent = {
  event_id?: number;
  ts?: number | string;
  time?: number | string;
  timestamp?: number | string;
  created_at?: number | string;
  type?: string;
  event?: string;
  name?: string;
  kind?: string;
  message?: string;
  detail?: string;
  summary?: string;
  task_title?: string;
  taskTitle?: string;
  title?: string;
  status?: string;
  level?: string;
  severity?: string;
  progress?: number;
  step?: string;
  step_id?: string;
  stepId?: string;
  step_total?: number;
  total_steps?: number;
  steps_total?: number;
  steps_done?: number;
  done_steps?: number;
  stepTotal?: number;
  stepsDone?: number;
  doneSteps?: number;
  data?: unknown;
  payload?: unknown;
};

export type RunEventsResponse = {
  run_id?: string;
  cursor?: number;
  next_cursor?: number;
  cursor_type?: string;
  total?: number;
  events?: RunEvent[];
};

export type ArtifactItem = {
  path: string;
  size: number;
  sha256: string;
  updated_at: number;
};

export type ArtifactsResponse = {
  plan_id?: string;
  run_id?: string;
  artifacts_root?: string;
  items?: ArtifactItem[];
  runs?: Array<{ run_id: string; run_dir: string }>;
};

export type AssistantChatResponse = {
  reply?: string;
  message?: string;
  [key: string]: unknown;
};

export type AssistantConfirmResponse = {
  run_id?: string;
  runId?: string;
  plan_id?: string;
  planId?: string;
  status?: string;
  [key: string]: unknown;
};

export type AssistantPlanResponse = {
  plan_id?: string;
  planId?: string;
  tasks_count?: number;
  [key: string]: unknown;
};

export type ChatMessage = {
  role: "user" | "assistant" | "system";
  content: string;
};

export type ProfileData = Record<string, unknown>;

export type CreatePlanResponse = {
  plan_id?: string;
  planId?: string;
  [key: string]: unknown;
};

export type CreateRunResponse = {
  run_id?: string;
  runId?: string;
  plan_id?: string;
  planId?: string;
  [key: string]: unknown;
};

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options
  });
  const body = (await res.json().catch(() => null)) as ApiEnvelope<T> | T | null;
  if (!res.ok) {
    if (body && typeof body === "object" && "error" in (body as ApiError)) {
      throw AiplError.fromApiError(body as ApiError);
    }
    throw new AiplError(`HTTP ${res.status}`, "HTTP_ERROR", { status: res.status });
  }
  if (body && typeof body === "object" && "ok" in body && (body as ApiEnvelope<T>).ok === false) {
    const envelope = body as ApiEnvelope<T>;
    const error = envelope.error || "Request failed";
    throw new AiplError(error, "API_ERROR");
  }
  if (body && typeof body === "object" && "data" in (body as ApiEnvelope<T>)) {
    return (body as ApiEnvelope<T>).data as T;
  }
  return body as T;
}

function normalizeList<T>(data: unknown, keys: string[]): T[] {
  if (!data) return [];
  if (Array.isArray(data)) return data as T[];
  if (typeof data !== "object") return [];
  const record = data as Record<string, unknown>;
  for (const key of keys) {
    const value = record[key];
    if (Array.isArray(value)) return value as T[];
  }
  return [];
}

export async function listPlans(): Promise<PlanSummary[]> {
  const data = await request<unknown>("/api/plans");
  return normalizeList<PlanSummary>(data, ["items", "data", "plans"]);
}

export async function listRuns(): Promise<RunSummary[]> {
  const data = await request<unknown>("/api/runs");
  return normalizeList<RunSummary>(data, ["items", "data", "runs"]);
}

export async function createPlan(payload: { task: string; planId?: string; workspace?: string }): Promise<CreatePlanResponse> {
  return request<CreatePlanResponse>(`/api/plans`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function createRun(payload: { task: string; planId?: string; workspace?: string; mode?: string; policy?: string }): Promise<CreateRunResponse> {
  return request<CreateRunResponse>(`/api/runs`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function deleteRun(runId: string, planId?: string): Promise<RunDetailResponse> {
  const q = planId ? `?planId=${encodeURIComponent(planId)}` : "";
  return request<RunDetailResponse>(`/api/runs/${encodeURIComponent(runId)}${q}`, { method: "DELETE" });
}

export async function cancelRun(runId: string, planId?: string): Promise<RunDetailResponse> {
  const q = planId ? `?planId=${encodeURIComponent(planId)}` : "";
  return request<RunDetailResponse>(`/api/runs/${encodeURIComponent(runId)}/cancel${q}`, { method: "POST" });
}

export type RetryOptions = {
  force?: boolean;
  retryDeps?: boolean;
  retryIdSuffix?: string;
  reuseTaskId?: boolean;
};

export async function retryRun(
  runId: string,
  options?: RetryOptions,
  planId?: string
): Promise<RunDetailResponse> {
  const params = new URLSearchParams();
  if (planId) params.set("planId", planId);
  if (options?.force) params.set("force", "true");
  if (options?.retryDeps) params.set("retryDeps", "true");
  if (options?.retryIdSuffix) params.set("retryIdSuffix", options.retryIdSuffix);
  if (options?.reuseTaskId) params.set("reuseTaskId", "true");
  const q = params.toString() ? `?${params}` : "";
  return request<RunDetailResponse>(`/api/runs/${encodeURIComponent(runId)}/retry${q}`, { method: "POST" });
}

export async function deletePlan(planId: string): Promise<CreatePlanResponse> {
  return request<CreatePlanResponse>(`/api/plans/${encodeURIComponent(planId)}`, { method: "DELETE" });
}

export async function getPlan(planId: string): Promise<PlanDetailResponse> {
  return request<PlanDetailResponse>(`/api/plans/${encodeURIComponent(planId)}`);
}

export async function getRun(runId: string, planId?: string): Promise<RunDetailResponse> {
  const q = planId ? `?planId=${encodeURIComponent(planId)}` : "";
  return request<RunDetailResponse>(`/api/runs/${encodeURIComponent(runId)}${q}`);
}

export async function getRunEvents(runId: string, planId?: string, cursor = 0, limit = 200): Promise<RunEventsResponse> {
  const params = new URLSearchParams();
  if (planId) params.set("planId", planId);
  params.set("cursor", String(cursor));
  params.set("limit", String(limit));
  const q = params.toString() ? `?${params}` : "";
  return request<RunEventsResponse>(`/api/runs/${encodeURIComponent(runId)}/events${q}`);
}

export function streamRunEvents(runId: string, planId?: string): EventSource {
  const q = planId ? `?planId=${encodeURIComponent(planId)}` : "";
  return new EventSource(`${BASE_URL}/api/runs/${encodeURIComponent(runId)}/events/stream${q}`);
}

export async function applyRun(runId: string, planId?: string): Promise<RunDetailResponse> {
  const q = planId ? `?planId=${encodeURIComponent(planId)}` : "";
  return request<RunDetailResponse>(`/api/runs/${encodeURIComponent(runId)}/apply${q}`, { method: "POST" });
}

export async function discardRun(runId: string, planId?: string): Promise<RunDetailResponse> {
  const q = planId ? `?planId=${encodeURIComponent(planId)}` : "";
  return request<RunDetailResponse>(`/api/runs/${encodeURIComponent(runId)}/discard${q}`, { method: "POST" });
}

export async function openRunFile(runId: string, filePath: string, planId?: string): Promise<{ opened?: boolean; path?: string }> {
  const q = planId ? `?planId=${encodeURIComponent(planId)}` : "";
  return request<{ opened?: boolean; path?: string }>(`/api/runs/${encodeURIComponent(runId)}/open-file${q}`, {
    method: "POST",
    body: JSON.stringify({ path: filePath })
  });
}

export async function getRunArtifacts(runId: string, planId?: string): Promise<ArtifactsResponse> {
  const q = planId ? `?planId=${encodeURIComponent(planId)}` : "";
  return request<ArtifactsResponse>(`/api/runs/${encodeURIComponent(runId)}/artifacts${q}`);
}

export async function downloadArtifactText(runId: string, artifactPath: string, planId?: string): Promise<string> {
  const q = planId ? `&planId=${encodeURIComponent(planId)}` : "";
  const res = await fetch(`${BASE_URL}/api/runs/${encodeURIComponent(runId)}/artifacts/download?path=${encodeURIComponent(artifactPath)}${q}`);
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  return res.text();
}

export async function reworkRun(runId: string, payload: { stepId?: string; feedback?: string; scope?: string }, planId?: string): Promise<RunDetailResponse> {
  const q = planId ? `?planId=${encodeURIComponent(planId)}` : "";
  return request<RunDetailResponse>(`/api/runs/${encodeURIComponent(runId)}/rework${q}`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function assistantChat(payload: { messages: ChatMessage[]; workspace?: string; policy?: string }): Promise<AssistantChatResponse> {
  return request<AssistantChatResponse>("/api/assistant/chat", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function assistantPlan(payload: { messages: ChatMessage[]; workspace?: string; planId?: string }): Promise<AssistantPlanResponse> {
  return request<AssistantPlanResponse>("/api/assistant/plan", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function assistantConfirm(payload: { planId: string; workspace?: string; mode?: string; policy?: string }): Promise<AssistantConfirmResponse> {
  return request<AssistantConfirmResponse>("/api/assistant/confirm", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function getProfile(workspace: string): Promise<ProfileData> {
  return request<ProfileData>(`/api/profile?workspace=${encodeURIComponent(workspace)}`);
}

export async function proposeProfile(workspace: string): Promise<ProfileData> {
  return request<ProfileData>(`/api/profile/propose`, {
    method: "POST",
    body: JSON.stringify({ workspace })
  });
}

export async function approveProfile(workspace: string): Promise<ProfileData> {
  return request<ProfileData>(`/api/profile/approve`, {
    method: "POST",
    body: JSON.stringify({ workspace })
  });
}

export async function rejectProfile(workspace: string): Promise<ProfileData> {
  return request<ProfileData>(`/api/profile/reject`, {
    method: "POST",
    body: JSON.stringify({ workspace })
  });
}
