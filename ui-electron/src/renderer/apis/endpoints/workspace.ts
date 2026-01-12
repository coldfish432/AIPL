/**
 * Workspace 相关 API
 */

import { request, unwrapEngineEnvelope, buildQueryString } from "../client";
import { AiplError } from "../client";
import type {
  WorkspaceInfo,
  MemoryRecord,
  PackRecord,
  WorkspaceRule,
  WorkspaceCustomCheck,
} from "../types";

/**
 * 获取工作区信息
 */
export async function getWorkspaceInfo(workspace: string): Promise<WorkspaceInfo> {
  if (!workspace) {
    throw new AiplError("workspace is required");
  }
  const query = buildQueryString({ workspace });
  return request<WorkspaceInfo>(`/api/workspace/info${query}`);
}

/**
 * 获取工作区记忆
 */
export async function getWorkspaceMemory(workspaceId: string): Promise<MemoryRecord> {
  const data = await request<MemoryRecord>(
    `/api/workspaces/${encodeURIComponent(workspaceId)}/memory`
  );
  return unwrapEngineEnvelope(data);
}

/**
 * 添加工作区规则
 */
export async function addWorkspaceRule(
  workspaceId: string,
  payload: { content: string; scope?: string; category?: string }
): Promise<PackRecord> {
  const data = await request<PackRecord>(
    `/api/workspaces/${encodeURIComponent(workspaceId)}/rules`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
  return unwrapEngineEnvelope(data);
}

/**
 * 删除工作区规则
 */
export async function deleteWorkspaceRule(
  workspaceId: string,
  ruleId: string
): Promise<PackRecord> {
  const data = await request<PackRecord>(
    `/api/workspaces/${encodeURIComponent(workspaceId)}/rules/${encodeURIComponent(ruleId)}`,
    { method: "DELETE" }
  );
  return unwrapEngineEnvelope(data);
}

/**
 * 添加工作区检查项
 */
export async function addWorkspaceCheck(
  workspaceId: string,
  payload: { check: Record<string, unknown>; scope?: string }
): Promise<PackRecord> {
  const data = await request<PackRecord>(
    `/api/workspaces/${encodeURIComponent(workspaceId)}/checks`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
  return unwrapEngineEnvelope(data);
}

/**
 * 删除工作区检查项
 */
export async function deleteWorkspaceCheck(
  workspaceId: string,
  checkId: string
): Promise<PackRecord> {
  const data = await request<PackRecord>(
    `/api/workspaces/${encodeURIComponent(workspaceId)}/checks/${encodeURIComponent(checkId)}`,
    { method: "DELETE" }
  );
  return unwrapEngineEnvelope(data);
}

/**
 * 删除工作区经验
 */
export async function deleteWorkspaceLesson(
  workspaceId: string,
  lessonId: string
): Promise<PackRecord> {
  const data = await request<PackRecord>(
    `/api/workspaces/${encodeURIComponent(workspaceId)}/lessons/${encodeURIComponent(lessonId)}`,
    { method: "DELETE" }
  );
  return unwrapEngineEnvelope(data);
}

/**
 * 清除工作区所有经验
 */
export async function clearWorkspaceLessons(workspaceId: string): Promise<PackRecord> {
  const data = await request<PackRecord>(
    `/api/workspaces/${encodeURIComponent(workspaceId)}/lessons`,
    { method: "DELETE" }
  );
  return unwrapEngineEnvelope(data);
}
