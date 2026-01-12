/**
 * Plan Detail Hook
 * 管理计划详情
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { getPlan, deletePlan, runPlan } from "@/apis";
import type { PlanDetailResponse, PlanTask } from "@/apis/types";

interface UsePlanDetailOptions {
  planId: string;
}

interface UsePlanDetailReturn {
  plan: PlanDetailResponse | null;
  planInfo: Record<string, unknown> | null;
  tasks: PlanTask[];
  taskChainText: string;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  deletePlan: () => Promise<void>;
  runPlan: (mode?: string) => Promise<string | null>;
}

export function usePlanDetail({ planId }: UsePlanDetailOptions): UsePlanDetailReturn {
  const [plan, setPlan] = useState<PlanDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await getPlan(planId);
      setPlan(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : "加载计划失败";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [planId]);

  useEffect(() => {
    load();
  }, [load]);

  const planInfo = useMemo(() => {
    return plan?.plan || plan || null;
  }, [plan]);

  const tasks = useMemo(() => {
    return (
      plan?.snapshot?.tasks ||
      (plan?.plan as any)?.raw_plan?.tasks ||
      []
    );
  }, [plan]);

  const taskChainText = useMemo(() => {
    return (
      plan?.task_chain_text ||
      (plan?.plan as any)?.task_chain_text ||
      ""
    );
  }, [plan]);

  const handleDelete = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      await deletePlan(planId);
    } catch (err) {
      const message = err instanceof Error ? err.message : "删除计划失败";
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [planId]);

  const handleRun = useCallback(
    async (mode?: string): Promise<string | null> => {
      setLoading(true);
      setError(null);

      try {
        const response = await runPlan(planId, { mode });
        return response.run_id || response.runId || null;
      } catch (err) {
        const message = err instanceof Error ? err.message : "启动运行失败";
        setError(message);
        return null;
      } finally {
        setLoading(false);
      }
    },
    [planId]
  );

  return {
    plan,
    planInfo,
    tasks,
    taskChainText,
    loading,
    error,
    refresh: load,
    deletePlan: handleDelete,
    runPlan: handleRun,
  };
}
