import { useState } from "react";
import { assistantConfirm, assistantPlan, ChatMessage, getPlan } from "../apiClient";
import { useI18n } from "../lib/useI18n";

type PlanFlowResult = {
  planId: string | null;
  planText: string;
};

export function usePlanFlow() {
  const { t } = useI18n();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const createPlan = async (messages: ChatMessage[], workspace?: string): Promise<PlanFlowResult | null> => {
    if (!messages || messages.length === 0) {
      setError(t.messages.needDescribeTask);
      return null;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await assistantPlan({
        messages: [{ role: "system", content: t.prompts.systemLanguage }, ...messages],
        workspace
      });
      const planId = res.plan_id || res.planId || null;
      let planText = "";
      if (planId) {
        const detail = await getPlan(planId);
        const tasks = detail?.snapshot?.tasks || detail?.plan?.raw_plan?.tasks || [];
        const lines = tasks.map((task, idx) => {
          const stepId = task.step_id || task.id || `task-${idx + 1}`;
          const title = task.title || `${t.labels.task} ${idx + 1}`;
          return `${idx + 1}. ${title} [${stepId}]`;
        });
        planText =
          detail?.task_chain_text ||
          detail?.plan?.task_chain_text ||
          [`${t.labels.taskChain}:`, ...lines].join("\n");
      }
      return { planId, planText };
    } catch (err) {
      const message = err instanceof Error ? err.message : t.messages.planFailed;
      setError(message || t.messages.planFailed);
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
      const message = err instanceof Error ? err.message : t.messages.startRunFailedNoId;
      setError(message || t.messages.startRunFailedNoId);
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
