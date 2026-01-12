/**
 * Pilot Flow Hook
 * 管理 Pilot 工作流
 */

import { useCallback, useState } from "react";
import { assistantChat, assistantPlan, assistantConfirm } from "@/apis";
import { usePlanLock } from "@/hooks/usePlanLock";
import type { ChatMessage } from "@/apis/types";

// ============================================================
// Types
// ============================================================

export type FlowStage =
  | "idle"
  | "chatting"
  | "planning"
  | "confirming"
  | "running";

export interface PlanPreview {
  planId: string;
  tasksCount: number;
  rawResponse?: Record<string, unknown>;
}

export interface UsePilotFlowReturn {
  stage: FlowStage;
  loading: boolean;
  error: string | null;
  planPreview: PlanPreview | null;
  
  // Actions
  sendMessage: (messages: ChatMessage[]) => Promise<string>;
  generatePlan: (messages: ChatMessage[]) => Promise<void>;
  confirmPlan: () => Promise<string>;
  reset: () => void;
  clearError: () => void;
}

// ============================================================
// Hook
// ============================================================

export function usePilotFlow(workspace?: string): UsePilotFlowReturn {
  const [stage, setStage] = useState<FlowStage>("idle");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [planPreview, setPlanPreview] = useState<PlanPreview | null>(null);

  const { canStartNewPlan, lockForPlan, setActiveRunId } = usePlanLock();

  // 发送聊天消息
  const sendMessage = useCallback(
    async (messages: ChatMessage[]): Promise<string> => {
      setLoading(true);
      setError(null);
      setStage("chatting");

      try {
        const response = await assistantChat({ messages, workspace });
        const reply = response.reply || response.message || "";
        return reply;
      } catch (err) {
        const message = err instanceof Error ? err.message : "聊天失败";
        setError(message);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [workspace]
  );

  // 生成计划
  const generatePlan = useCallback(
    async (messages: ChatMessage[]): Promise<void> => {
      // 检查锁状态
      const { allowed, reason } = canStartNewPlan();
      if (!allowed) {
        setError(reason || "无法创建新计划");
        return;
      }

      setLoading(true);
      setError(null);
      setStage("planning");

      try {
        const response = await assistantPlan({ messages, workspace });
        const planId = response.plan_id || response.planId;

        if (!planId) {
          throw new Error("未返回 plan_id");
        }

        // 锁定 plan
        lockForPlan(planId);

        setPlanPreview({
          planId,
          tasksCount: response.tasks_count || 0,
          rawResponse: response as Record<string, unknown>,
        });

        setStage("confirming");
      } catch (err) {
        const message = err instanceof Error ? err.message : "生成计划失败";
        setError(message);
        setStage("idle");
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [workspace, canStartNewPlan, lockForPlan]
  );

  // 确认并执行计划
  const confirmPlan = useCallback(async (): Promise<string> => {
    if (!planPreview?.planId) {
      throw new Error("没有待确认的计划");
    }

    setLoading(true);
    setError(null);
    setStage("running");

    try {
      const response = await assistantConfirm({
        planId: planPreview.planId,
        workspace,
      });

      const runId = response.run_id || response.runId;
      if (!runId) {
        throw new Error("未返回 run_id");
      }

      setActiveRunId(runId);
      return runId;
    } catch (err) {
      const message = err instanceof Error ? err.message : "执行失败";
      setError(message);
      setStage("confirming");
      throw err;
    } finally {
      setLoading(false);
    }
  }, [planPreview, workspace, setActiveRunId]);

  // 重置状态
  const reset = useCallback(() => {
    setStage("idle");
    setLoading(false);
    setError(null);
    setPlanPreview(null);
  }, []);

  // 清除错误
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    stage,
    loading,
    error,
    planPreview,
    sendMessage,
    generatePlan,
    confirmPlan,
    reset,
    clearError,
  };
}
