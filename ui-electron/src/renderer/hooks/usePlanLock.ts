import { useCallback, useEffect, useState } from "react";
import { loadJson, saveJson } from "../lib/storage";

export type PlanLockStatus = "idle" | "executing" | "awaiting_review";

export type PlanLockState = {
  activePlanId: string | null;
  status: PlanLockStatus;
  pendingReviewRuns: string[];
  lockedAt: number | null;
};

const LOCK_KEY = "aipl.planLock";

const initialState: PlanLockState = {
  activePlanId: null,
  status: "idle",
  pendingReviewRuns: [],
  lockedAt: null
};

export function usePlanLock() {
  const [lock, setLock] = useState<PlanLockState>(() =>
    loadJson<PlanLockState>(LOCK_KEY, initialState)
  );

  useEffect(() => {
    saveJson(LOCK_KEY, lock);
  }, [lock]);

  const canStartNewPlan = useCallback((): { allowed: boolean; reason?: string } => {
    if (lock.status === "idle") {
      return { allowed: true };
    }
    if (lock.status === "executing") {
      return {
        allowed: false,
        reason: `任务链 ${lock.activePlanId} 正在执行中`
      };
    }
    if (lock.status === "awaiting_review") {
      return {
        allowed: false,
        reason: `任务链 ${lock.activePlanId} 有 ${lock.pendingReviewRuns.length} 个任务待审核`
      };
    }
    return { allowed: true };
  }, [lock]);

  const lockForPlan = useCallback((planId: string) => {
    setLock({
      activePlanId: planId,
      status: "executing",
      pendingReviewRuns: [],
      lockedAt: Date.now()
    });
  }, []);

  const setAwaitingReview = useCallback((runIds: string[]) => {
    setLock((prev) => ({
      ...prev,
      status: "awaiting_review",
      pendingReviewRuns: runIds
    }));
  }, []);

  const addPendingReview = useCallback((runId: string) => {
    setLock((prev) => ({
      ...prev,
      status: "awaiting_review",
      pendingReviewRuns: prev.pendingReviewRuns.includes(runId)
        ? prev.pendingReviewRuns
        : prev.pendingReviewRuns.concat(runId)
    }));
  }, []);

  const removePendingReview = useCallback((runId: string) => {
    setLock((prev) => {
      const remaining = prev.pendingReviewRuns.filter((id) => id !== runId);
      if (remaining.length === 0) {
        return initialState;
      }
      return {
        ...prev,
        pendingReviewRuns: remaining
      };
    });
  }, []);

  const completeWithoutReview = useCallback(() => {
    setLock(initialState);
  }, []);

  const forceUnlock = useCallback(() => {
    setLock(initialState);
  }, []);

  const getStatusText = useCallback((): string => {
    switch (lock.status) {
      case "idle":
        return "就绪";
      case "executing":
        return "执行中";
      case "awaiting_review":
        return `待审核(${lock.pendingReviewRuns.length})`;
      default:
        return "未知";
    }
  }, [lock]);

  return {
    lock,
    canStartNewPlan,
    lockForPlan,
    setAwaitingReview,
    addPendingReview,
    removePendingReview,
    completeWithoutReview,
    forceUnlock,
    getStatusText
  };
}
