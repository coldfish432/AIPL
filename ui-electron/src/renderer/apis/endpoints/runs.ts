/**
 * Run 相关 API
 */

import { request, unwrapEngineEnvelope, buildQueryString, createEventSource, getBaseUrl } from "../client";
import type {
  RunSummary,
  RunDetailResponse,
  RunEventsResponse,
  ArtifactsResponse,
  CreateRunResponse,
  RetryOptions,
} from "../types";

/**
 * 获取运行列表
 */
export async function listRuns(workspace?: string): Promise<RunSummary[]> {
  const query = buildQueryString({ workspace });
  const data = await request<RunSummary[]>(`/api/runs${query}`);
  return unwrapEngineEnvelope(data);
}

/**
 * 获取运行详情
 */
export async function getRun(runId: string, planId?: string): Promise<RunDetailResponse> {
  const query = buildQueryString({ planId });
  return request(`/api/runs/${encodeURIComponent(runId)}${query}`);
}

/**
 * 获取运行事件列表
 */
export async function getRunEvents(
  runId: string,
  planId?: string,
  cursor = 0,
  limit = 100
): Promise<RunEventsResponse> {
  const query = buildQueryString({
    planId,
    cursor,
    limit,
  });
  return request(`/api/runs/${encodeURIComponent(runId)}/events${query}`);
}

/**
 * 创建运行事件流连接
 */
export function streamRunEvents(runId: string, planId?: string): EventSource {
  const query = buildQueryString({ planId });
  return createEventSource(`/api/runs/${encodeURIComponent(runId)}/events/stream${query}`);
}

/**
 * 获取运行产物列表
 */
export async function getRunArtifacts(runId: string, planId?: string): Promise<ArtifactsResponse> {
  const query = buildQueryString({ planId });
  return request(`/api/runs/${encodeURIComponent(runId)}/artifacts${query}`);
}

/**
 * 下载产物文本内容
 */
export async function downloadArtifactText(
  runId: string,
  artifactPath: string,
  planId?: string
): Promise<string> {
  const params = new URLSearchParams({ path: artifactPath });
  if (planId) params.append("planId", planId);

  const res = await fetch(
    `${getBaseUrl()}/api/runs/${encodeURIComponent(runId)}/artifacts/download?${params}`
  );
  
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  
  return res.text();
}

/**
 * 应用运行变更
 */
export async function applyRun(runId: string, planId?: string): Promise<RunDetailResponse> {
  const query = buildQueryString({ planId });
  return request(`/api/runs/${encodeURIComponent(runId)}/apply${query}`, {
    method: "POST",
  });
}

/**
 * 取消运行
 */
export async function cancelRun(runId: string, planId?: string): Promise<RunDetailResponse> {
  const query = buildQueryString({ planId });
  return request(`/api/runs/${encodeURIComponent(runId)}/cancel${query}`, {
    method: "POST",
  });
}

/**
 * 重试运行
 */
export async function retryRun(
  runId: string,
  options?: RetryOptions,
  planId?: string
): Promise<CreateRunResponse> {
  const query = buildQueryString({ planId });
  return request(`/api/runs/${encodeURIComponent(runId)}/retry${query}`, {
    method: "POST",
    body: options ? JSON.stringify(options) : undefined,
  });
}

/**
 * 返工运行
 */
export async function reworkRun(
  runId: string,
  payload: { stepId?: string; feedback?: string; scope?: string },
  planId?: string
): Promise<RunDetailResponse> {
  const query = buildQueryString({ planId });
  return request(`/api/runs/${encodeURIComponent(runId)}/rework${query}`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * 丢弃运行变更
 */
export async function discardRun(runId: string, planId?: string): Promise<RunDetailResponse> {
  const query = buildQueryString({ planId });
  return request(`/api/runs/${encodeURIComponent(runId)}/discard${query}`, {
    method: "POST",
  });
}

/**
 * 删除运行
 */
export async function deleteRun(runId: string, planId?: string): Promise<void> {
  const query = buildQueryString({ planId });
  return request(`/api/runs/${encodeURIComponent(runId)}${query}`, {
    method: "DELETE",
  });
}

/**
 * 打开运行相关文件
 */
export async function openRunFile(
  runId: string,
  filePath: string,
  planId?: string
): Promise<{ opened?: boolean; path?: string }> {
  const query = buildQueryString({ planId });
  return request(`/api/runs/${encodeURIComponent(runId)}/open-file${query}`, {
    method: "POST",
    body: JSON.stringify({ path: filePath }),
  });
}
