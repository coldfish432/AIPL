/**
 * Lock-related type definitions
 */

// ============================================================
// Execution Lock (mutex)
// ============================================================

export type ExecutionLockStatus =
  | "idle"
  | "planning"
  | "confirming"
  | "running"
  | "reviewing";

export interface ExecutionLock {
  status: ExecutionLockStatus;
  planId: string | null;
  runId: string | null;
  task: string | null;
  lockedAt: number | null;
  progress?: {
    currentStep: number;
    totalSteps: number;
    currentStepTitle?: string;
  };
}

// ============================================================
// Chat State (independent)
// ============================================================

export interface ChatState {
  isLoading: boolean;
  requestId: string | null;
  lastError: string | null;
}

// ============================================================
// Pending Request (for recovery)
// ============================================================

export interface PendingRequest {
  type: "chat" | "plan" | "confirm";
  requestId: string;
  startedAt: number;
  planId?: string;
  task?: string;
}

// ============================================================
// Execution Context (for conversation hints)
// ============================================================

export interface ExecutionContext {
  hasActiveExecution: boolean;
  executionStatus: ExecutionLockStatus;
  currentTask: string | null;
  planId: string | null;
  runId: string | null;
}

// ============================================================
// Helper Types
// ============================================================

export interface CanStartPlanResult {
  allowed: boolean;
  reason?: string;
  currentExecution?: {
    planId: string;
    task: string | null;
    status: ExecutionLockStatus;
  };
}

// ============================================================
// Default values
// ============================================================

export const DEFAULT_EXECUTION_LOCK: ExecutionLock = {
  status: "idle",
  planId: null,
  runId: null,
  task: null,
  lockedAt: null,
};

export const DEFAULT_CHAT_STATE: ChatState = {
  isLoading: false,
  requestId: null,
  lastError: null,
};
