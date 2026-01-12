/**
 * Run Detail Hook
 * 管理 Run 详情数据加载
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { getRun, getPlan } from "@/apis";
import { resolveStatus } from "@/lib/status";
import type { RunDetailResponse, PlanTask, UnifiedStatus } from "@/apis/types";

interface UseRunDetailOptions {
  runId: string;
  planId?: string;
}

interface UseRunDetailReturn {
  run: RunDetailResponse | null;
  runInfo: Record<string, unknown> | null;
  planTasks: PlanTask[];
  unifiedStatus: UnifiedStatus;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export function useRunDetail({ runId, planId }: UseRunDetailOptions): UseRunDetailReturn {
  const [run, setRun] = useState<RunDetailResponse | null>(null);
  const [planTasks, setPlanTasks] = useState<PlanTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchRun = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await getRun(runId, planId);
      setRun(data);

      // 同时加载 plan tasks 用于状态计算
      const resolvedPlanId = planId || data?.run?.plan_id || (data as any)?.plan_id;
      if (resolvedPlanId) {
        try {
          const planData = await getPlan(resolvedPlanId);
          setPlanTasks(planData?.snapshot?.tasks || []);
        } catch {
          setPlanTasks([]);
        }
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "加载运行详情失败";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [runId, planId]);

  useEffect(() => {
    fetchRun();
  }, [fetchRun]);

  const runInfo = useMemo(() => {
    return run?.run || run || null;
  }, [run]);

  const unifiedStatus = useMemo(() => {
    const status = runInfo?.status || (runInfo as any)?.state || "unknown";
    return resolveStatus(status as string, planTasks);
  }, [runInfo, planTasks]);

  return {
    run,
    runInfo,
    planTasks,
    unifiedStatus,
    loading,
    error,
    refresh: fetchRun,
  };
}
