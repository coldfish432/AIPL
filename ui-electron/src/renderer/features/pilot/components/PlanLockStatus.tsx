/**
 * Plan Lock Status 组件
 * 显示任务链锁定状态
 */

import React from "react";
import { Lock, Unlock, AlertTriangle } from "lucide-react";
import { useI18n } from "@/hooks/useI18n";
import type { PlanLock } from "@/hooks/usePlanLock";

interface PlanLockStatusProps {
  lock: PlanLock;
  onForceUnlock: () => void;
}

export function PlanLockStatus({ lock, onForceUnlock }: PlanLockStatusProps) {
  const { t } = useI18n();

  if (lock.status === "idle") {
    return null;
  }

  const handleForceUnlock = () => {
    if (window.confirm(t.messages.forceUnlockHint)) {
      onForceUnlock();
    }
  };

  return (
    <div className={`plan-lock-status ${lock.status}`}>
      <div className="plan-lock-indicator">
        <Lock size={14} />
        <span className="plan-lock-label">
          {lock.status === "planning" && "正在生成计划"}
          {lock.status === "running" && "任务执行中"}
          {lock.status === "reviewing" && `${lock.pendingReviewRuns.length} 个待审核`}
        </span>
      </div>

      {lock.activePlanId && (
        <span className="plan-lock-id">Plan: {lock.activePlanId.slice(0, 8)}...</span>
      )}

      <button
        className="button-icon sm danger"
        onClick={handleForceUnlock}
        title={t.buttons.forceUnlock}
      >
        <Unlock size={12} />
      </button>
    </div>
  );
}
