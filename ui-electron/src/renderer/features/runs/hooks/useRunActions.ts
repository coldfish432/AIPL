/**
 * Run Actions Hook
 * 管理 Run 操作（应用、取消、重试等）
 */

import { useCallback, useState } from "react";
import {
  applyRun,
  cancelRun,
  retryRun,
  reworkRun,
  discardRun,
  deleteRun,
} from "@/apis";
import type { RetryOptions, RunDetailResponse, CreateRunResponse } from "@/apis/types";

interface UseRunActionsOptions {
  runId: string;
  planId?: string;
  onSuccess?: (run: RunDetailResponse) => void;
  onNewRun?: (newRunId: string) => void;
  onDelete?: () => void;
}

interface UseRunActionsReturn {
  loading: boolean;
  error: string | null;
  clearError: () => void;

  // Actions
  handleApply: () => Promise<void>;
  handleCancel: () => Promise<void>;
  handleRetry: (options?: RetryOptions) => Promise<void>;
  handleRework: (feedback: string, stepId?: string) => Promise<void>;
  handleDiscard: () => Promise<void>;
  handleDelete: () => Promise<void>;
}

export function useRunActions({
  runId,
  planId,
  onSuccess,
  onNewRun,
  onDelete,
}: UseRunActionsOptions): UseRunActionsReturn {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wrapAction = useCallback(
    async <T>(
      action: () => Promise<T>,
      errorMessage: string,
      successHandler?: (result: T) => void
    ) => {
      setLoading(true);
      setError(null);

      try {
        const result = await action();
        successHandler?.(result);
      } catch (err) {
        const message = err instanceof Error ? err.message : errorMessage;
        setError(message);
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const handleApply = useCallback(async () => {
    await wrapAction(
      () => applyRun(runId, planId),
      "应用更改失败",
      onSuccess
    );
  }, [runId, planId, wrapAction, onSuccess]);

  const handleCancel = useCallback(async () => {
    await wrapAction(
      () => cancelRun(runId, planId),
      "取消运行失败",
      onSuccess
    );
  }, [runId, planId, wrapAction, onSuccess]);

  const handleRetry = useCallback(
    async (options?: RetryOptions) => {
      await wrapAction(
        () => retryRun(runId, options, planId),
        "重试失败",
        (res: CreateRunResponse) => {
          const newRunId = res.run_id || res.runId;
          if (newRunId && newRunId !== runId) {
            onNewRun?.(newRunId);
          } else {
            onSuccess?.(res as unknown as RunDetailResponse);
          }
        }
      );
    },
    [runId, planId, wrapAction, onSuccess, onNewRun]
  );

  const handleRework = useCallback(
    async (feedback: string, stepId?: string) => {
      await wrapAction(
        () => reworkRun(runId, { stepId, feedback }, planId),
        "返工失败",
        onSuccess
      );
    },
    [runId, planId, wrapAction, onSuccess]
  );

  const handleDiscard = useCallback(async () => {
    await wrapAction(
      () => discardRun(runId, planId),
      "丢弃更改失败",
      onSuccess
    );
  }, [runId, planId, wrapAction, onSuccess]);

  const handleDelete = useCallback(async () => {
    await wrapAction(() => deleteRun(runId, planId), "删除运行失败", onDelete);
  }, [runId, planId, wrapAction, onDelete]);

  return {
    loading,
    error,
    clearError: () => setError(null),
    handleApply,
    handleCancel,
    handleRetry,
    handleRework,
    handleDiscard,
    handleDelete,
  };
}
