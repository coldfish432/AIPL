import React from "react";
import { PlanLockState } from "../hooks/usePlanLock";
import "./PlanLockStatus.css";

type Props = {
  lock: PlanLockState;
  onGoToReview?: () => void;
  onForceUnlock?: () => void;
};

export function PlanLockStatus({ lock, onGoToReview, onForceUnlock }: Props) {
  if (lock.status === "idle") {
    return (
      <div className="plan-lock-status idle">
        <span className="icon">[就绪]</span>
        <span className="text">系统就绪，可以创建新任务链</span>
      </div>
    );
  }

  if (lock.status === "executing") {
    return (
      <div className="plan-lock-status executing">
        <span className="icon">[执行中]</span>
        <span className="text">
          正在执行: <strong>{lock.activePlanId}</strong>
        </span>
        <span className="hint">请等待执行完成</span>
      </div>
    );
  }

  if (lock.status === "awaiting_review") {
    return (
      <div className="plan-lock-status awaiting-review">
        <span className="icon">[待审核]</span>
        <span className="text">
          任务链 <strong>{lock.activePlanId}</strong> 有{" "}
          <strong>{lock.pendingReviewRuns.length}</strong> 个任务待审核
        </span>
        <div className="actions">
          {onGoToReview && (
            <button className="btn primary" onClick={onGoToReview}>
              去审核
            </button>
          )}
          {onForceUnlock && (
            <button className="btn danger" onClick={onForceUnlock}>
              全部丢弃
            </button>
          )}
        </div>
      </div>
    );
  }

  return null;
}
