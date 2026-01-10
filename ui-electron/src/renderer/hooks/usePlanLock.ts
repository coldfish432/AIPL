import { useCallback, useEffect, useState } from "react";
import { loadJson, saveJson } from "../lib/storage";

export type PlanLockStatus = "idle" | "executing" | "paused" | "awaiting_review";

export type PlanLockState = {
  activePlanId: string | null;
  activeRunId: string | null;
  status: PlanLockStatus;
  pendingReviewRuns: string[];
  lockedAt: number | null;
};

const LOCK_KEY = "aipl.planLock";

const initialState: PlanLockState = {
  activePlanId: null,
  activeRunId: null,
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

  const canStartNewPlan = useCallback(() => {
    if (lock.status === "idle") {
      return { allowed: true };
    }
    if (lock.status === "executing") {
      return {
        allowed: false,
        reason: `任务链 ${lock.activePlanId ?? "-"} 正在执行中`
      };
    }
    if (lock.status === "paused") {
      return {
        allowed: false,
        reason: `任务链 ${lock.activePlanId ?? "-"} 已暂停`
      };
    }
    if (lock.status === "awaiting_review") {
      return {
        allowed: false,
        reason: `任务链 ${lock.activePlanId ?? "-"} 有 ${lock.pendingReviewRuns.length} 个待审核`
      };
    }
    return { allowed: true };
  }, [lock]);

  const lockForPlan = useCallback((planId: string, runId?: string) => {
    setLock({
      activePlanId: planId,
      activeRunId: runId ?? null,
      status: "executing",
      pendingReviewRuns: [],
      lockedAt: Date.now()
    });
  }, []);

  const setActiveRunId = useCallback((runId: string | null) => {
    setLock((prev) => {
      if (!prev.activePlanId) {
        return prev;
      }
      if (prev.activeRunId === runId) {
        return prev;
      }
      return { ...prev, activeRunId: runId };
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

  const resetLock = useCallback(() => {
    setLock(initialState);
  }, []);

  const forceUnlock = useCallback(() => {
    resetLock();
  }, [resetLock]);

  const forceUnlockLocal = useCallback(() => {
    resetLock();
  }, [resetLock]);

  const cancelExecution = useCallback(async (): Promise<boolean> => {
    if (!lock.activePlanId) return false;
    try {
      const res = await fetch("/api/cancel-plan-runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ planId: lock.activePlanId })
      });
      if (!res.ok) {
        console.error("Cancel failed:", await res.text());
        return false;
      }
      resetLock();
      return true;
    } catch (err) {
      console.error("Cancel error:", err);
      return false;
    }
  }, [lock.activePlanId, resetLock]);

  const pauseExecution = useCallback(async (): Promise<boolean> => {
    if (!lock.activeRunId || !lock.activePlanId) return false;
    try {
      const res = await fetch("/api/pause", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          planId: lock.activePlanId,
          runId: lock.activeRunId
        })
      });
      if (!res.ok) {
        console.error("Pause failed:", await res.text());
        return false;
      }
      setLock((prev) => ({ ...prev, status: "paused" }));
      return true;
    } catch (err) {
      console.error("Pause error:", err);
      return false;
    }
  }, [lock.activePlanId, lock.activeRunId]);

  const resumeExecution = useCallback(async (): Promise<boolean> => {
    if (!lock.activeRunId || !lock.activePlanId) return false;
    try {
      const res = await fetch("/api/resume", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          planId: lock.activePlanId,
          runId: lock.activeRunId
        })
      });
      if (!res.ok) {
        console.error("Resume failed:", await res.text());
        return false;
      }
      setLock((prev) => ({ ...prev, status: "executing" }));
      return true;
    } catch (err) {
      console.error("Resume error:", err);
      return false;
    }
  }, [lock.activePlanId, lock.activeRunId]);

  const getStatusText = useCallback((): string => {
    switch (lock.status) {
      case "idle":
        return "空闲";
      case "executing":
        return "执行中";
      case "paused":
        return "已暂停";
      case "awaiting_review":
        return `待审核 (${lock.pendingReviewRuns.length})`;
      default:
        return "未知";
    }
  }, [lock.status, lock.pendingReviewRuns.length]);

  return {
    lock,
    canStartNewPlan,
    lockForPlan,
    setActiveRunId,
    setAwaitingReview,
    addPendingReview,
    removePendingReview,
    completeWithoutReview,
    cancelExecution,
    pauseExecution,
    resumeExecution,
    forceUnlock,
    forceUnlockLocal,
    getStatusText
  };
}
