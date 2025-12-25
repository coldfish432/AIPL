const BASE_URL = import.meta.env.DEV ? "" : "http://127.0.0.1:18088";

type ApiEnvelope<T> = {
  ok?: boolean;
  data?: T;
  error?: string;
};

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options
  });
  const body = (await res.json().catch(() => null)) as ApiEnvelope<T> | T | null;
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  if (body && typeof body === "object" && "ok" in body && (body as ApiEnvelope<T>).ok === false) {
    throw new Error((body as ApiEnvelope<T>).error || "Request failed");
  }
  if (body && typeof body === "object" && "data" in (body as ApiEnvelope<T>)) {
    return (body as ApiEnvelope<T>).data as T;
  }
  return body as T;
}

function normalizeList(data: any): any[] {
  if (!data) return [];
  if (Array.isArray(data)) return data;
  if (Array.isArray(data.items)) return data.items;
  if (Array.isArray(data.data)) return data.data;
  if (Array.isArray(data.runs)) return data.runs;
  if (Array.isArray(data.plans)) return data.plans;
  return [];
}

export async function listPlans(): Promise<any[]> {
  const data = await request<any>("/api/plans");
  return normalizeList(data);
}

export async function listRuns(): Promise<any[]> {
  const data = await request<any>("/api/runs");
  return normalizeList(data);
}

export async function createPlan(payload: { task: string; planId?: string; workspace?: string }): Promise<any> {
  return request(`/api/plans`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function createRun(payload: { task: string; planId?: string; workspace?: string }): Promise<any> {
  return request(`/api/runs`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function getPlan(planId: string): Promise<any> {
  return request(`/api/plans/${encodeURIComponent(planId)}`);
}

export async function getRun(runId: string, planId?: string): Promise<any> {
  const q = planId ? `?planId=${encodeURIComponent(planId)}` : "";
  return request(`/api/runs/${encodeURIComponent(runId)}${q}`);
}

export function streamRunEvents(runId: string, planId?: string): EventSource {
  const q = planId ? `?planId=${encodeURIComponent(planId)}` : "";
  return new EventSource(`${BASE_URL}/api/runs/${encodeURIComponent(runId)}/events/stream${q}`);
}

export async function getProfile(workspace: string): Promise<any> {
  return request(`/api/profile?workspace=${encodeURIComponent(workspace)}`);
}

export async function proposeProfile(workspace: string): Promise<any> {
  return request(`/api/profile/propose`, {
    method: "POST",
    body: JSON.stringify({ workspace })
  });
}

export async function approveProfile(workspace: string): Promise<any> {
  return request(`/api/profile/approve`, {
    method: "POST",
    body: JSON.stringify({ workspace })
  });
}

export async function rejectProfile(workspace: string): Promise<any> {
  return request(`/api/profile/reject`, {
    method: "POST",
    body: JSON.stringify({ workspace })
  });
}
