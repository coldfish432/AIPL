import { useRef, useState } from "react";
import { assistantConfirm, assistantPlan, ChatMessage, getPlan } from "../apiClient";
import { useI18n } from "../lib/useI18n";

type PlanFlowResult = {
  planId: string | null;
  planText: string;
};

type FlowState = "idle" | "planning" | "awaiting_confirm" | "executing" | "done" | "error";

export function usePlanFlow() {
  const { t } = useI18n();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [flowState, setFlowState] = useState<FlowState>("idle");
  const lockRef = useRef(false);

  const createPlan = async (messages: ChatMessage[], workspace?: string): Promise<PlanFlowResult | null> => {
    if (lockRef.current) {
      console.warn("[usePlanFlow] createPlan called while locked");
      return null;
    }

    if (!messages || messages.length === 0) {
      setError(t.messages.needDescribeTask);
      return null;
    }

    lockRef.current = true;
    setLoading(true);
    setError(null);
    setFlowState("planning");

    try {
      const res = await assistantPlan({
        messages: [{ role: "system", content: t.prompts.systemLanguage }, ...messages],
        workspace,
      });
      const planId = res.plan_id || res.planId || null;
      let planText = "";

      if (planId) {
        const detail = await getPlan(planId);
        const tasks = detail?.snapshot?.tasks || detail?.plan?.raw_plan?.tasks || [];
        const lines = tasks.map((task, idx) => {
          const stepId = task.step_id || task.id || 	ask-;
          const title = task.title || ${t.labels.task} ;
          return ${idx + 1}.  [];
        });
        planText =
          detail?.task_chain_text ||
          detail?.plan?.task_chain_text ||
          [${t.labels.taskChain}:, ...lines].join("\n");
      }

      setFlowState("awaiting_confirm");
      return { planId, planText };
    } catch (err) {
      const message = err instanceof Error ? err.message : t.messages.planFailed;
      setError(message || t.messages.planFailed);
      setFlowState("error");
      return null;
    } finally {
      setLoading(false);
      lockRef.current = false;
    }
  };

  const confirmPlan = async (planId: string, workspace?: string, policy?: string) => {
    if (flowState !== "awaiting_confirm") {
      console.warn([usePlanFlow] confirmPlan called in wrong state: );
      setError(t.messages.needCreatePlanFirst || "请先生成计划");
      return null;
    }

    if (lockRef.current) {
      console.warn("[usePlanFlow] confirmPlan called while locked");
      return null;
    }

    lockRef.current = true;
    setLoading(true);
    setError(null);
    setFlowState("executing");

    try {
      const result = await assistantConfirm({ planId, workspace, mode: "autopilot", policy });
      setFlowState("done");
      return result;
    } catch (err) {
      const message = err instanceof Error ? err.message : t.messages.startRunFailedNoId;
      setError(message || t.messages.startRunFailedNoId);
      setFlowState("error");
      return null;
    } finally {
      setLoading(false);
      lockRef.current = false;
    }
  };

  const resetFlow = () => {
    setFlowState("idle");
    setError(null);
    lockRef.current = false;
  };

  return {
    loading,
    error,
    setError,
    flowState,
    createPlan,
    confirmPlan,
    resetFlow,
    canCreatePlan: flowState === "idle" || flowState === "done" || flowState === "error",
    canConfirmPlan: flowState === "awaiting_confirm",
  };
}
