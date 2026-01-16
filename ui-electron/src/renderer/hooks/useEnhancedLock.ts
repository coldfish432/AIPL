/**
 * useEnhancedLock - enhanced lock management hook
 *
 * Responsibilities:
 * 1. ExecutionLock: manage plan -> run -> review flow (mutual exclusion)
 * 2. ChatState: track standalone conversation requests
 * 3. PendingRequest: remember in-flight requests for recovery
 * 4. Automatic recovery after reload
 * 5. Cross-tab synchronization
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useWorkspace } from "@/contexts/WorkspaceContext";
import { STORAGE_KEYS, REQUEST_TIMEOUT_MS } from "@/config/settings";
import { getPlan, getRun, listRuns } from "@/services/api";
import type {
  ExecutionLock,
  ExecutionLockStatus,
  ChatState,
  PendingRequest,
  ExecutionContext,
  CanStartPlanResult,
} from "@/types/lock";
import { DEFAULT_CHAT_STATE, DEFAULT_EXECUTION_LOCK } from "@/types/lock";

// ============================================================
// Storage helpers
// ============================================================

function getStorageKey(base: string, workspace: string): string {
  return `${base}_${workspace.replace(/[^a-zA-Z0-9]/g, "_")}`;
}

function loadFromStorage<T>(key: string, defaultValue: T): T {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return defaultValue;
    return { ...defaultValue, ...JSON.parse(raw) };
  } catch {
    return defaultValue;
  }
}

function saveToStorage<T>(key: string, value: T): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Ignore storage errors
  }
}

// ============================================================
// Hook return type
// ============================================================

export interface UseEnhancedLockReturn {
  executionLock: ExecutionLock;
  chatState: ChatState;
  pendingRequest: PendingRequest | null;
  canStartNewPlan: CanStartPlanResult;
  canChat: boolean;
  executionContext: ExecutionContext;
  isRecovering: boolean;

  lockForPlanning: (planId: string, task: string) => void;
  updatePlanId: (planId: string) => void;
  transitionToConfirming: () => void;
  transitionToRunning: (runId: string) => void;
  transitionToReviewing: () => void;
  updateProgress: (current: number, total: number, title?: string) => void;
  releaseExecutionLock: () => void;
  forceUnlockExecution: () => void;

  startChatRequest: () => string;
  finishChatRequest: (requestId: string, error?: string) => void;
  cancelChatRequest: () => void;
  clearChatError: () => void;

  setPendingPlanRequest: (planId: string, task: string) => string;
  setPendingConfirmRequest: (planId: string) => string;
  clearPendingRequest: () => void;

  recoverFromPending: () => Promise<void>;
}

// ============================================================
// Hook implementation
// ============================================================

export function useEnhancedLock(): UseEnhancedLockReturn {
  const { workspace } = useWorkspace();

  const execKey = workspace ? getStorageKey(STORAGE_KEYS.executionLockKey, workspace) : "";
  const chatKey = workspace ? getStorageKey(STORAGE_KEYS.chatStateKey, workspace) : "";
  const pendingKey = workspace ? getStorageKey(STORAGE_KEYS.pendingRequestKey, workspace) : "";

  const [executionLock, setExecutionLock] = useState<ExecutionLock>(DEFAULT_EXECUTION_LOCK);
  const [chatState, setChatState] = useState<ChatState>(DEFAULT_CHAT_STATE);
  const [pendingRequest, setPendingRequest] = useState<PendingRequest | null>(null);
  const [isRecovering, setIsRecovering] = useState(false);

  const recoveryAttemptedRef = useRef(false);
  const prevWorkspaceRef = useRef<string | null>(null);
  const isInitializedRef = useRef(false);

  useEffect(() => {
    if (!workspace) {
      console.log("[Lock] workspace is empty, skip initialization");
      return;
    }

    if (prevWorkspaceRef.current === workspace && isInitializedRef.current) {
      console.log("[Lock] workspace unchanged, skip initialization");
      return;
    }

    console.log("[Lock] loading state for workspace:", workspace);
    prevWorkspaceRef.current = workspace;
    isInitializedRef.current = true;

    const execLoadKey = getStorageKey(STORAGE_KEYS.executionLockKey, workspace);
    const chatLoadKey = getStorageKey(STORAGE_KEYS.chatStateKey, workspace);
    const pendingLoadKey = getStorageKey(STORAGE_KEYS.pendingRequestKey, workspace);

    const loadedExec = loadFromStorage(execLoadKey, DEFAULT_EXECUTION_LOCK);
    const loadedChat = loadFromStorage(chatLoadKey, DEFAULT_CHAT_STATE);
    const loadedPending = loadFromStorage<PendingRequest | null>(pendingLoadKey, null);

    console.log("[Lock] loaded executionLock:", loadedExec);

    setExecutionLock(loadedExec);
    setChatState({ ...loadedChat, isLoading: false });
    setPendingRequest(loadedPending);
    recoveryAttemptedRef.current = false;
  }, [workspace]);

  useEffect(() => {
    if (workspace && execKey) {
      saveToStorage(execKey, executionLock);
      window.dispatchEvent(
        new CustomEvent("aipl-lock-changed", { detail: { workspace, executionLock } })
      );
    }
  }, [workspace, execKey, executionLock]);

  useEffect(() => {
    if (workspace && chatKey) {
      saveToStorage(chatKey, chatState);
    }
  }, [workspace, chatKey, chatState]);

  useEffect(() => {
    if (workspace && pendingKey) {
      if (pendingRequest) {
        saveToStorage(pendingKey, pendingRequest);
      } else {
        localStorage.removeItem(pendingKey);
      }
    }
  }, [workspace, pendingKey, pendingRequest]);

  useEffect(() => {
    const handleStorage = (event: StorageEvent) => {
      if (!workspace) return;

      if (event.key === execKey && event.newValue) {
        try {
          setExecutionLock(JSON.parse(event.newValue));
        } catch {
          // ignore
        }
      }

      if (event.key === chatKey && event.newValue) {
        try {
          setChatState({ ...JSON.parse(event.newValue), isLoading: false });
        } catch {
          // ignore
        }
      }

      if (event.key === pendingKey) {
        try {
          setPendingRequest(event.newValue ? JSON.parse(event.newValue) : null);
        } catch {
          // ignore
        }
      }
    };

    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, [workspace, execKey, chatKey, pendingKey]);

  const recoverFromPending = useCallback(async () => {
    if (!workspace || !pendingRequest || isRecovering) {
      return;
    }

    const elapsed = Date.now() - pendingRequest.startedAt;
    if (elapsed > REQUEST_TIMEOUT_MS) {
      setPendingRequest(null);
      if (executionLock.status === "planning") {
        setExecutionLock(DEFAULT_EXECUTION_LOCK);
      }
      return;
    }

    setIsRecovering(true);

    try {
      if (pendingRequest.type === "plan" && pendingRequest.planId) {
        try {
          const planData = await getPlan(pendingRequest.planId);
          if (planData?.plan) {
            setExecutionLock((prev) => ({
              ...prev,
              status: "confirming",
              planId: pendingRequest.planId,
              task: pendingRequest.task || prev.task,
            }));
            setPendingRequest(null);
          }
        } catch {
          console.log("[Lock Recovery] Plan not found, keeping state");
        }
      } else if (pendingRequest.type === "confirm" && pendingRequest.planId) {
        try {
          let runId: string | null = null;
          let status: string | null = null;

          try {
            const runs = await listRuns(workspace);
            const related = runs.find(
              (run) => (run.plan_id || run.planId) === pendingRequest.planId
            );
            if (related) {
              runId = related.run_id || related.runId || related.id || null;
              status = related.status || related.state || status;
            }
          } catch {
            // ignore
          }

          if (!runId) {
            console.log("[Lock Recovery] No run found for plan");
            return;
          }

          const runData = await getRun(runId, pendingRequest.planId);
          const normalized = (runData?.run?.status || runData?.status || status || "")
            .toLowerCase()
            .replace(/-/g, "_");

          if (normalized === "awaiting_review" || normalized.includes("awaiting_review")) {
            setExecutionLock((prev) => ({ ...prev, status: "reviewing", runId }));
          } else if (
            ["running", "executing", "queued", "starting"].some((key) =>
              normalized.includes(key)
            )
          ) {
            setExecutionLock((prev) => ({ ...prev, status: "running", runId }));
          } else if (
            ["completed", "done", "applied", "discarded", "failed", "canceled", "cancelled"].some(
              (key) => normalized.includes(key)
            )
          ) {
            setExecutionLock(DEFAULT_EXECUTION_LOCK);
          } else {
            setExecutionLock((prev) => ({ ...prev, runId }));
          }

          setPendingRequest(null);
        } catch {
          console.log("[Lock Recovery] Run not found");
        }
      }
    } catch (err) {
      console.error("[Lock Recovery] Error:", err);
    } finally {
      setIsRecovering(false);
    }
  }, [workspace, pendingRequest, isRecovering, executionLock.status]);

  useEffect(() => {
    if (workspace && pendingRequest && !recoveryAttemptedRef.current) {
      recoveryAttemptedRef.current = true;
      recoverFromPending();
    }
  }, [workspace, pendingRequest, recoverFromPending]);

  const canStartNewPlan = useMemo<CanStartPlanResult>(() => {
    if (executionLock.status === "idle") {
      return { allowed: true };
    }

    const reasons: Record<ExecutionLockStatus, string> = {
      idle: "",
      planning: "正在生成计划中",
      confirming: "有待确认的计划",
      running: "有任务正在运行中",
      reviewing: "有任务等待审查",
    };

    return {
      allowed: false,
      reason: reasons[executionLock.status],
      currentExecution: executionLock.planId
        ? {
            planId: executionLock.planId,
            task: executionLock.task,
            status: executionLock.status,
          }
        : undefined,
    };
  }, [executionLock]);

  const canChat = useMemo(() => {
    return executionLock.status !== "planning" && !chatState.isLoading;
  }, [executionLock.status, chatState.isLoading]);

  const executionContext = useMemo<ExecutionContext>(
    () => ({
      hasActiveExecution: executionLock.status !== "idle",
      executionStatus: executionLock.status,
      currentTask: executionLock.task,
      planId: executionLock.planId,
      runId: executionLock.runId,
    }),
    [executionLock]
  );

  const lockForPlanning = useCallback((planId: string, task: string) => {
    setExecutionLock({
      status: "planning",
      planId,
      runId: null,
      task,
      lockedAt: Date.now(),
    });
  }, []);

  const updatePlanId = useCallback((planId: string) => {
    setExecutionLock((prev) => ({ ...prev, planId }));
    setPendingRequest((prev) => {
      if (!prev) return prev;
      return { ...prev, planId };
    });
  }, []);

  const transitionToConfirming = useCallback(() => {
    setExecutionLock((prev) => ({ ...prev, status: "confirming" }));
    setPendingRequest(null);
  }, []);

  const transitionToRunning = useCallback((runId: string) => {
    setExecutionLock((prev) => ({ ...prev, status: "running", runId }));
    setPendingRequest(null);
  }, []);

  const transitionToReviewing = useCallback(() => {
    setExecutionLock((prev) => ({ ...prev, status: "reviewing" }));
  }, []);

  const updateProgress = useCallback(
    (current: number, total: number, title?: string) => {
      setExecutionLock((prev) => ({
        ...prev,
        progress: { currentStep: current, totalSteps: total, currentStepTitle: title },
      }));
    },
    []
  );

  const releaseExecutionLock = useCallback(() => {
    setExecutionLock(DEFAULT_EXECUTION_LOCK);
    setPendingRequest(null);
  }, []);

  const forceUnlockExecution = useCallback(() => {
    setExecutionLock(DEFAULT_EXECUTION_LOCK);
    setPendingRequest(null);
    setChatState(DEFAULT_CHAT_STATE);
  }, []);

  const startChatRequest = useCallback((): string => {
    const requestId = `chat_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    setChatState({ isLoading: true, requestId, lastError: null });
    return requestId;
  }, []);

  const finishChatRequest = useCallback((requestId: string, error?: string) => {
    setChatState((prev) => {
      if (prev.requestId !== requestId) return prev;
      return { isLoading: false, requestId: null, lastError: error || null };
    });
  }, []);

  const cancelChatRequest = useCallback(() => {
    setChatState(DEFAULT_CHAT_STATE);
  }, []);

  const clearChatError = useCallback(() => {
    setChatState((prev) => ({ ...prev, lastError: null }));
  }, []);

  const setPendingPlanRequest = useCallback((planId: string, task: string) => {
    const requestId = `plan_${Date.now()}`;
    setPendingRequest({ type: "plan", requestId, startedAt: Date.now(), planId, task });
    return requestId;
  }, []);

  const setPendingConfirmRequest = useCallback((planId: string) => {
    const requestId = `confirm_${Date.now()}`;
    setPendingRequest({ type: "confirm", requestId, startedAt: Date.now(), planId });
    return requestId;
  }, []);

  const clearPendingRequest = useCallback(() => {
    setPendingRequest(null);
  }, []);

  return {
    executionLock,
    chatState,
    pendingRequest,
    canStartNewPlan,
    canChat,
    executionContext,
    isRecovering,
    lockForPlanning,
    updatePlanId,
    transitionToConfirming,
    transitionToRunning,
    transitionToReviewing,
    updateProgress,
    releaseExecutionLock,
    forceUnlockExecution,
    startChatRequest,
    finishChatRequest,
    cancelChatRequest,
    clearChatError,
    setPendingPlanRequest,
    setPendingConfirmRequest,
    clearPendingRequest,
    recoverFromPending,
  };
}
