/**
 * Language Pack & Experience Pack 相关 API
 */

import { request, unwrapEngineEnvelope, buildQueryString } from "../client";
import type { PackRecord } from "../types";

// ============================================================
// Language Pack APIs
// ============================================================

/**
 * 获取语言包列表
 */
export async function listLanguagePacks(workspace?: string): Promise<PackRecord> {
  const query = buildQueryString({ workspace });
  const data = await request<PackRecord>(`/api/language-packs${query}`);
  return unwrapEngineEnvelope(data);
}

/**
 * 获取语言包详情
 */
export async function getLanguagePack(packId: string): Promise<PackRecord> {
  const data = await request<PackRecord>(
    `/api/language-packs/${encodeURIComponent(packId)}`
  );
  return unwrapEngineEnvelope(data);
}

/**
 * 导入语言包
 */
export async function importLanguagePack(pack: PackRecord): Promise<PackRecord> {
  const data = await request<PackRecord>("/api/language-packs/import", {
    method: "POST",
    body: JSON.stringify({ pack }),
  });
  return unwrapEngineEnvelope(data);
}

/**
 * 导出语言包
 */
export async function exportLanguagePack(packId: string): Promise<PackRecord> {
  const data = await request<PackRecord>(
    `/api/language-packs/${encodeURIComponent(packId)}/export`
  );
  return unwrapEngineEnvelope(data);
}

/**
 * 导出合并的语言包
 */
export async function exportMergedLanguagePack(
  packId: string,
  payload: { name?: string; description?: string }
): Promise<PackRecord> {
  const data = await request<PackRecord>(
    `/api/language-packs/${encodeURIComponent(packId)}/export-merged`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
  return unwrapEngineEnvelope(data);
}

/**
 * 导出学习的语言包
 */
export async function exportLearnedLanguagePack(payload: {
  name?: string;
  description?: string;
}): Promise<PackRecord> {
  const data = await request<PackRecord>("/api/language-packs/learned/export", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return unwrapEngineEnvelope(data);
}

/**
 * 更新语言包状态
 */
export async function updateLanguagePack(
  packId: string,
  enabled: boolean
): Promise<PackRecord> {
  const data = await request<PackRecord>(
    `/api/language-packs/${encodeURIComponent(packId)}`,
    {
      method: "PATCH",
      body: JSON.stringify({ enabled }),
    }
  );
  return unwrapEngineEnvelope(data);
}

/**
 * 删除语言包
 */
export async function deleteLanguagePack(packId: string): Promise<PackRecord> {
  const data = await request<PackRecord>(
    `/api/language-packs/${encodeURIComponent(packId)}`,
    { method: "DELETE" }
  );
  return unwrapEngineEnvelope(data);
}

/**
 * 清除学习的语言包
 */
export async function clearLearnedLanguagePack(): Promise<PackRecord> {
  const data = await request<PackRecord>("/api/language-packs/learned", {
    method: "DELETE",
  });
  return unwrapEngineEnvelope(data);
}

// ============================================================
// Experience Pack APIs
// ============================================================

/**
 * 获取经验包列表
 */
export async function listExperiencePacks(workspaceId: string): Promise<PackRecord[]> {
  const data = await request<PackRecord[]>(
    `/api/workspaces/${encodeURIComponent(workspaceId)}/experience-packs`
  );
  return unwrapEngineEnvelope(data);
}

/**
 * 获取经验包详情
 */
export async function getExperiencePack(
  workspaceId: string,
  packId: string
): Promise<PackRecord> {
  const data = await request<PackRecord>(
    `/api/workspaces/${encodeURIComponent(workspaceId)}/experience-packs/${encodeURIComponent(packId)}`
  );
  return unwrapEngineEnvelope(data);
}

/**
 * 导入经验包
 */
export async function importExperiencePack(
  workspaceId: string,
  pack: PackRecord
): Promise<PackRecord> {
  const data = await request<PackRecord>(
    `/api/workspaces/${encodeURIComponent(workspaceId)}/experience-packs/import`,
    {
      method: "POST",
      body: JSON.stringify({ pack }),
    }
  );
  return unwrapEngineEnvelope(data);
}

/**
 * 从其他工作区导入经验包
 */
export async function importExperiencePackFromWorkspace(
  workspaceId: string,
  payload: {
    fromWorkspaceId: string;
    includeRules?: boolean;
    includeChecks?: boolean;
    includeLessons?: boolean;
    includePatterns?: boolean;
  }
): Promise<PackRecord> {
  const data = await request<PackRecord>(
    `/api/workspaces/${encodeURIComponent(workspaceId)}/experience-packs/import-workspace`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
  return unwrapEngineEnvelope(data);
}

/**
 * 导出经验包
 */
export async function exportExperiencePack(
  workspaceId: string,
  payload: {
    name?: string;
    description?: string;
    includeRules?: boolean;
    includeChecks?: boolean;
    includeLessons?: boolean;
    includePatterns?: boolean;
  }
): Promise<PackRecord> {
  const data = await request<PackRecord>(
    `/api/workspaces/${encodeURIComponent(workspaceId)}/experience-packs/export`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
  return unwrapEngineEnvelope(data);
}

/**
 * 更新经验包状态
 */
export async function updateExperiencePack(
  workspaceId: string,
  packId: string,
  enabled: boolean
): Promise<PackRecord> {
  const data = await request<PackRecord>(
    `/api/workspaces/${encodeURIComponent(workspaceId)}/experience-packs/${encodeURIComponent(packId)}`,
    {
      method: "PATCH",
      body: JSON.stringify({ enabled }),
    }
  );
  return unwrapEngineEnvelope(data);
}

/**
 * 删除经验包
 */
export async function deleteExperiencePack(
  workspaceId: string,
  packId: string
): Promise<PackRecord> {
  const data = await request<PackRecord>(
    `/api/workspaces/${encodeURIComponent(workspaceId)}/experience-packs/${encodeURIComponent(packId)}`,
    { method: "DELETE" }
  );
  return unwrapEngineEnvelope(data);
}
