/**
 * Profile 相关 API
 */

import { request, unwrapEngineEnvelope } from "../client";
import { AiplError } from "../client";
import type { ProfileData } from "../types";

/**
 * 获取配置
 */
export async function getProfile(workspace: string): Promise<ProfileData> {
  const data = await request<ProfileData>(
    `/api/profile?workspace=${encodeURIComponent(workspace)}`
  );
  return unwrapEngineEnvelope(data);
}

/**
 * 更新配置
 */
export async function updateProfile(
  workspace: string,
  userHard: Record<string, unknown> | null
): Promise<ProfileData> {
  const payload = JSON.stringify({ workspace, user_hard: userHard });

  try {
    const data = await request<ProfileData>("/api/profile", {
      method: "PATCH",
      body: payload,
    });
    return unwrapEngineEnvelope(data);
  } catch (err) {
    // 兼容不支持 PATCH 的情况
    const isMethodNotAllowed =
      (err instanceof AiplError && err.details?.status === 405) ||
      (err instanceof Error && err.message.toLowerCase().includes("not supported"));

    if (!isMethodNotAllowed) {
      throw err;
    }
  }

  // Fallback to POST
  const fallback = await request<ProfileData>("/api/profile", {
    method: "POST",
    body: payload,
  });
  return unwrapEngineEnvelope(fallback);
}
