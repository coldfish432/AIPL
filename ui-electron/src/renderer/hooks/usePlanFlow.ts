import { useState } from "react";
import { assistantConfirm, assistantPlan, ChatMessage, getPlan } from "../apiClient";

type PlanFlowResult = {
  planId: string | null;
  planText: string;
};

export function usePlanFlow() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const createPlan = async (messages: ChatMessage[], workspace?: string): Promise<PlanFlowResult | null> => {
    if (!messages || messages.length === 0) {
      setError("请先输入任务描述。");
      return null;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await assistantPlan({ messages, workspace });
      const planId = res.plan_id || res.planId || null;
      let planText = "";
      if (planId) {
        const detail = await getPlan(planId);
        const tasks = detail?.snapshot?.tasks || detail?.plan?.raw_plan?.tasks || [];
        const lines = tasks.map((task, idx) => {
          const stepId = task.step_id || task.id || `task-${idx + 1}`;
          const title = task.title || `任务 ${idx + 1}`;
          return `${idx + 1}. ${title} [${stepId}]`;
        });
        planText = detail?.task_chain_text || detail?.plan?.task_chain_text || ["任务链：", ...lines].join("\n");
      }
      return { planId, planText };
    } catch (err) {
      const message = err instanceof Error ? err.message : "生成计划失败";
      setError(message || "生成计划失败");
      return null;
    } finally {
      setLoading(false);
    }
  };

  const confirmPlan = async (planId: string, workspace?: string, policy?: string) => {
    setLoading(true);
    setError(null);
    try {
      return await assistantConfirm({ planId, workspace, mode: "autopilot", policy });
    } catch (err) {
      const message = err instanceof Error ? err.message : "启动执行失败";
      setError(message || "启动执行失败");
      return null;
    } finally {
      setLoading(false);
    }
  };

  return {
    loading,
    error,
    setError,
    createPlan,
    confirmPlan
  };
}
