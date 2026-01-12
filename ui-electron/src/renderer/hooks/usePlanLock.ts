/**
 * Plan Lock Hook
 * 管理任务链执行锁状态
 */

import { useCallback, useEffect, useState } from "react";
import { STORAGE_KEYS } from "@/config/settings";

// ============================================================
// Types
// ============================================================

export type LockStatus = "idle" | "planning" | "running" | "reviewing";

export interface PlanLock {
  status: LockStatus;
  activePlanId: string | null;
  activeRunId: string | null;
  pendingReviewRuns: string[];
  lockedAt: number | null;
}

export interface UsePlanLockReturn {
  lock: PlanLock;
  canStartNewPlan: () => { allowed: boolean; reason?: string };
  lockForPlan: (planId: string) => void;
  setActiveRunId: (runId: string) => void;
  addPendingReview: (runId: string) => void;
  removePendingReview: (runId: string) => void;
  completeWithoutReview: () => void;
  forceUnlock: () => void;
}

// ============================================================
// Default State
// ============================================================

const DEFAULT_LOCK: PlanLock = {
  status: "idle",
  activePlanId: null,
  activeRunId: null,
  pendingReviewRuns: [],
  lockedAt: null,
};

// ============================================================
// Storage Helpers
// ============================================================

function loadLock(): PlanLock {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.planLockKey);
    if (!raw) return DEFAULT_LOCK;
    
    const parsed = JSON.parse(raw);
    return {
      ...DEFAULT_LOCK,
      ...parsed,
      pendingReviewRuns: Array.isArray(parsed.pendingReviewRuns)
        ? parsed.pendingReviewRuns
        : [],
    };
  } catch {
    return DEFAULT_LOCK;
  }
}

function saveLock(lock: PlanLock): void {
  try {
    localStorage.setItem(STORAGE_KEYS.planLockKey, JSON.stringify(lock));
  } catch {
    // Ignore storage errors
  }
}

// ============================================================
// Hook
// ============================================================

export function usePlanLock(): UsePlanLockReturn {
  const [lock, setLock] = useState<PlanLock>(() => loadLock());

  // Persist to storage
  useEffect(() => {
    saveLock(lock);
  }, [lock]);

  // Sync across tabs
  useEffect(() => {
    const handleStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEYS.planLockKey && e.newValue) {
        try {
          setLock(JSON.parse(e.newValue));
        } catch {
          // Ignore parse errors
        }
      }
    };

    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, []);

  /**
   * 检查是否可以开始新的计划
   */
  const canStartNewPlan = useCallback((): { allowed: boolean; reason?: string } => {
    if (lock.status === "idle") {
      return { allowed: true };
    }

    if (lock.status === "reviewing" && lock.pendingReviewRuns.length > 0) {
      return {
        allowed: false,
        reason: `有 ${lock.pendingReviewRuns.length} 个任务等待审核`,
      };
    }

    if (lock.status === "running") {
      return {
        allowed: false,
        reason: "有任务正在执行中",
      };
    }

    if (lock.status === "planning") {
      return {
        allowed: false,
        reason: "正在生成计划",
      };
    }

    return { allowed: false, reason: "任务链被锁定" };
  }, [lock]);

  /**
   * 锁定用于计划生成
   */
  const lockForPlan = useCallback((planId: string) => {
    setLock((prev) => ({
      ...prev,
      status: "planning",
      activePlanId: planId,
      lockedAt: Date.now(),
    }));
  }, []);

  /**
   * 设置活跃的运行 ID
   */
  const setActiveRunId = useCallback((runId: string) => {
    setLock((prev) => ({
      ...prev,
      status: "running",
      activeRunId: runId,
    }));
  }, []);

  /**
   * 添加待审核的运行
   */
  const addPendingReview = useCallback((runId: string) => {
    setLock((prev) => {
      if (prev.pendingReviewRuns.includes(runId)) {
        return prev;
      }
      return {
        ...prev,
        status: "reviewing",
        activeRunId: null,
        pendingReviewRuns: [...prev.pendingReviewRuns, runId],
      };
    });
  }, []);

  /**
   * 移除待审核的运行
   */
  const removePendingReview = useCallback((runId: string) => {
    setLock((prev) => {
      const updated = prev.pendingReviewRuns.filter((id) => id !== runId);
      return {
        ...prev,
        pendingReviewRuns: updated,
        status: updated.length === 0 ? "idle" : "reviewing",
        activePlanId: updated.length === 0 ? null : prev.activePlanId,
        lockedAt: updated.length === 0 ? null : prev.lockedAt,
      };
    });
  }, []);

  /**
   * 完成但无需审核
   */
  const completeWithoutReview = useCallback(() => {
    setLock((prev) => {
      if (prev.pendingReviewRuns.length > 0) {
        return {
          ...prev,
          status: "reviewing",
          activeRunId: null,
        };
      }
      return DEFAULT_LOCK;
    });
  }, []);

  /**
   * 强制解锁
   */
  const forceUnlock = useCallback(() => {
    setLock(DEFAULT_LOCK);
  }, []);

  return {
    lock,
    canStartNewPlan,
    lockForPlan,
    setActiveRunId,
    addPendingReview,
    removePendingReview,
    completeWithoutReview,
    forceUnlock,
  };
}
