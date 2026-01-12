/**
 * ExecutionContext - 全局执行状态管理
 * 
 * 功能：
 * 1. Plan/Run 状态全局共享
 * 2. 每次只能有一个 plan 在执行/待审核
 * 3. Run 完成后才能进行下一个
 * 4. 中断恢复机制（重启UI后从断点恢复）
 * 5. 统一终止功能（删除暂停/解锁，改为终止）
 */

import React, { createContext, useCallback, useContext, useEffect, useState, useMemo, useRef } from "react";
import { STORAGE_KEYS } from "@/config/settings";
import { useWorkspace } from "./WorkspaceContext";
import {
  getRun,
  getPlan,
  listRuns,
  cancelRun,
  applyRun,
  discardRun,
} from "@/services/api";

// ============================================================
// Types
// ============================================================

export type ExecutionStatus = 
  | "idle"           // 空闲，可以开始新任务
  | "executing"      // 正在执行
  | "awaiting_review" // 待审核
  | "terminated";    // 已终止

export interface ActiveExecution {
  planId: string;
  runId: string | null;
  status: ExecutionStatus;
  startedAt: number;
  task?: string;
}

export interface ExecutionContextValue {
  // 当前执行状态
  execution: ActiveExecution | null;
  status: ExecutionStatus;
  
  // 状态检查
  canStartNewPlan: boolean;
  isExecuting: boolean;
  isAwaitingReview: boolean;
  
  // 操作
  startExecution: (planId: string, task?: string) => void;
  setRunId: (runId: string) => void;
  markAwaitingReview: () => void;
  markCompleted: () => void;
  terminateExecution: () => Promise<boolean>;
  applyChanges: () => Promise<boolean>;
  discardChanges: () => Promise<boolean>;
  
  // 恢复
  recoverExecution: () => Promise<void>;
}

const ExecutionContext = createContext<ExecutionContextValue | null>(null);

// ============================================================
// Storage Key (per workspace)
// ============================================================

function getExecutionStorageKey(workspace: string): string {
  return `aipl.execution.${workspace.replace(/[^a-zA-Z0-9]/g, "_")}`;
}

function loadExecution(workspace: string): ActiveExecution | null {
  if (!workspace) return null;
  try {
    const raw = localStorage.getItem(getExecutionStorageKey(workspace));
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function saveExecution(workspace: string, execution: ActiveExecution | null): void {
  if (!workspace) return;
  const key = getExecutionStorageKey(workspace);
  if (execution) {
    localStorage.setItem(key, JSON.stringify(execution));
  } else {
    localStorage.removeItem(key);
  }
}

// ============================================================
// Provider
// ============================================================

interface ExecutionProviderProps {
  children: React.ReactNode;
}

export function ExecutionProvider({ children }: ExecutionProviderProps) {
  const { workspace } = useWorkspace();
  const [execution, setExecution] = useState<ActiveExecution | null>(null);
  const pollIntervalRef = useRef<number | null>(null);

  // 计算派生状态
  const status = execution?.status || "idle";
  const canStartNewPlan = status === "idle";
  const isExecuting = status === "executing";
  const isAwaitingReview = status === "awaiting_review";

  // 工作区变更时加载对应的执行状态
  useEffect(() => {
    if (workspace) {
      const saved = loadExecution(workspace);
      setExecution(saved);
    } else {
      setExecution(null);
    }
  }, [workspace]);

  // 保存执行状态
  useEffect(() => {
    if (workspace) {
      saveExecution(workspace, execution);
    }
  }, [workspace, execution]);

  // 开始执行
  const startExecution = useCallback((planId: string, task?: string) => {
    setExecution({
      planId,
      runId: null,
      status: "executing",
      startedAt: Date.now(),
      task,
    });
  }, []);

  // 设置 Run ID
  const setRunId = useCallback((runId: string) => {
    setExecution((prev) => {
      if (!prev) return null;
      return { ...prev, runId };
    });
  }, []);

  // 标记为待审核
  const markAwaitingReview = useCallback(() => {
    setExecution((prev) => {
      if (!prev) return null;
      return { ...prev, status: "awaiting_review" };
    });
  }, []);

  // 标记完成
  const markCompleted = useCallback(() => {
    setExecution(null);
  }, []);

  // 终止执行
  const terminateExecution = useCallback(async (): Promise<boolean> => {
    if (!execution) return true;

    try {
      if (execution.runId) {
        await cancelRun(execution.runId, execution.planId);
      }
      setExecution({
        ...execution,
        status: "terminated",
      });
      // 短暂延迟后清除
      setTimeout(() => setExecution(null), 1000);
      return true;
    } catch (err) {
      console.error("终止执行失败:", err);
      return false;
    }
  }, [execution]);

  // 应用变更
  const applyChanges = useCallback(async (): Promise<boolean> => {
    if (!execution?.runId) return false;

    try {
      await applyRun(execution.runId, execution.planId);
      setExecution(null);
      return true;
    } catch (err) {
      console.error("应用变更失败:", err);
      return false;
    }
  }, [execution]);

  // 丢弃变更
  const discardChanges = useCallback(async (): Promise<boolean> => {
    if (!execution?.runId) return false;

    try {
      await discardRun(execution.runId, execution.planId);
      setExecution(null);
      return true;
    } catch (err) {
      console.error("丢弃变更失败:", err);
      return false;
    }
  }, [execution]);

  // 恢复执行（重启UI后从断点恢复）
  const recoverExecution = useCallback(async () => {
    if (!workspace || !execution) return;

    // 如果有 runId，检查 run 状态
    if (execution.runId) {
      try {
        const runData = await getRun(execution.runId, execution.planId);
        const runStatus = runData?.run?.status || runData?.status || "unknown";
        const normalizedStatus = runStatus.toLowerCase().replace(/-/g, "_");

        if (normalizedStatus === "awaiting_review") {
          setExecution((prev) => prev ? { ...prev, status: "awaiting_review" } : null);
        } else if (["completed", "done", "applied"].includes(normalizedStatus)) {
          setExecution(null);
        } else if (["failed", "canceled", "cancelled", "discarded", "terminated"].includes(normalizedStatus)) {
          setExecution(null);
        } else if (["running", "executing", "queued", "starting"].includes(normalizedStatus)) {
          setExecution((prev) => prev ? { ...prev, status: "executing" } : null);
        }
      } catch {
        // Run 不存在，清除状态
        setExecution(null);
      }
    } else if (execution.planId) {
      // 只有 planId，检查是否有关联的 run
      try {
        const runs = await listRuns(workspace);
        const relatedRun = runs.find(
          (r) => (r.plan_id || r.planId) === execution.planId
        );
        if (relatedRun) {
          const runId = relatedRun.run_id || relatedRun.runId || relatedRun.id;
          if (runId) {
            setExecution((prev) => prev ? { ...prev, runId: String(runId) } : null);
          }
        }
      } catch {
        // 忽略错误
      }
    }
  }, [workspace, execution]);

  // 轮询检查执行状态
  useEffect(() => {
    if (!execution || status !== "executing" || !execution.runId) {
      if (pollIntervalRef.current) {
        window.clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
      return;
    }

    const checkStatus = async () => {
      try {
        const runData = await getRun(execution.runId!, execution.planId);
        const runStatus = runData?.run?.status || runData?.status || "unknown";
        const normalizedStatus = runStatus.toLowerCase().replace(/-/g, "_");

        if (normalizedStatus === "awaiting_review") {
          markAwaitingReview();
        } else if (["completed", "done", "applied"].includes(normalizedStatus)) {
          markCompleted();
        } else if (["failed", "canceled", "cancelled", "discarded"].includes(normalizedStatus)) {
          markCompleted();
        }
      } catch {
        // 忽略临时错误
      }
    };

    pollIntervalRef.current = window.setInterval(checkStatus, 3000);

    return () => {
      if (pollIntervalRef.current) {
        window.clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    };
  }, [execution, status, markAwaitingReview, markCompleted]);

  // 初始化时尝试恢复
  useEffect(() => {
    if (workspace && execution && (execution.status === "executing" || execution.status === "awaiting_review")) {
      recoverExecution();
    }
  }, [workspace]);

  // 广播状态变更
  useEffect(() => {
    window.dispatchEvent(new CustomEvent("aipl-execution-changed", { detail: { execution, status } }));
  }, [execution, status]);

  const value = useMemo<ExecutionContextValue>(() => ({
    execution,
    status,
    canStartNewPlan,
    isExecuting,
    isAwaitingReview,
    startExecution,
    setRunId,
    markAwaitingReview,
    markCompleted,
    terminateExecution,
    applyChanges,
    discardChanges,
    recoverExecution,
  }), [
    execution,
    status,
    canStartNewPlan,
    isExecuting,
    isAwaitingReview,
    startExecution,
    setRunId,
    markAwaitingReview,
    markCompleted,
    terminateExecution,
    applyChanges,
    discardChanges,
    recoverExecution,
  ]);

  return (
    <ExecutionContext.Provider value={value}>
      {children}
    </ExecutionContext.Provider>
  );
}

// ============================================================
// Hook
// ============================================================

export function useExecution(): ExecutionContextValue {
  const context = useContext(ExecutionContext);
  if (!context) {
    throw new Error("useExecution must be used within ExecutionProvider");
  }
  return context;
}
