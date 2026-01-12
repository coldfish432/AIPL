/**
 * Plan 相关 API
 */

import { request, unwrapEngineEnvelope, buildQueryString } from "../client";
import type { PlanSummary, PlanDetailResponse, CreatePlanResponse } from "../types";

/**
 * 获取计划列表
 */
export async function listPlans(workspace?: string): Promise<PlanSummary[]> {
  const query = buildQueryString({ workspace });
  const data = await request<PlanSummary[]>(`/api/plans${query}`);
  return unwrapEngineEnvelope(data);
}

/**
 * 获取计划详情
 */
export async function getPlan(planId: string): Promise<PlanDetailResponse> {
  return request(`/api/plans/${encodeURIComponent(planId)}`);
}

/**
 * 创建计划
 */
export async function createPlan(payload: {
  task: string;
  workspace?: string;
}): Promise<CreatePlanResponse> {
  return request("/api/plans", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * 删除计划
 */
export async function deletePlan(planId: string): Promise<void> {
  return request(`/api/plans/${encodeURIComponent(planId)}`, {
    method: "DELETE",
  });
}

/**
 * 运行计划
 */
export async function runPlan(
  planId: string,
  payload?: { mode?: string; workspace?: string }
): Promise<{ run_id?: string; runId?: string }> {
  return request(`/api/plans/${encodeURIComponent(planId)}/run`, {
    method: "POST",
    body: payload ? JSON.stringify(payload) : undefined,
  });
}
