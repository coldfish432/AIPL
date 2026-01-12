/**
 * Assistant 相关 API
 */

import { request } from "../client";
import type {
  ChatMessage,
  AssistantChatResponse,
  AssistantPlanResponse,
  AssistantConfirmResponse,
} from "../types";

/**
 * 发送聊天消息
 */
export async function assistantChat(payload: {
  messages: ChatMessage[];
  workspace?: string;
}): Promise<AssistantChatResponse> {
  return request("/api/assistant/chat", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * 创建任务计划
 */
export async function assistantPlan(payload: {
  messages: ChatMessage[];
  workspace?: string;
  planId?: string;
}): Promise<AssistantPlanResponse> {
  return request("/api/assistant/plan", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * 确认并执行计划
 */
export async function assistantConfirm(payload: {
  planId: string;
  workspace?: string;
  mode?: string;
}): Promise<AssistantConfirmResponse> {
  return request("/api/assistant/confirm", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
