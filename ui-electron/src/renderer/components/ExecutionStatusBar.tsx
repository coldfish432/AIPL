/**
 * ExecutionStatusBar - 全局执行状态栏
 * 
 * 功能：
 * 1. 显示当前执行状态
 * 2. 终止执行按钮（统一替代暂停/解锁）
 * 3. 待审核时显示应用/丢弃按钮
 */

import React, { useState } from "react";
import { Play, Square, Check, X, AlertTriangle } from "lucide-react";
import { useExecution } from "@/contexts/ExecutionContext";
import { useI18n } from "@/hooks/useI18n";

export default function ExecutionStatusBar() {
  const { t } = useI18n();
  const {
    execution,
    status,
    isExecuting,
    isAwaitingReview,
    terminateExecution,
    applyChanges,
    discardChanges,
  } = useExecution();

  const [loading, setLoading] = useState(false);

  // 空闲状态不显示
  if (status === "idle" || !execution) {
    return null;
  }

  // 终止执行
  const handleTerminate = async () => {
    if (!window.confirm("确定要终止当前执行吗？执行将被标记为强制终止状态。")) {
      return;
    }
    setLoading(true);
    await terminateExecution();
    setLoading(false);
  };

  // 应用变更
  const handleApply = async () => {
    if (!window.confirm("确定要应用变更吗？")) {
      return;
    }
    setLoading(true);
    await applyChanges();
    setLoading(false);
  };

  // 丢弃变更
  const handleDiscard = async () => {
    if (!window.confirm("确定要丢弃变更吗？所有修改将被撤销。")) {
      return;
    }
    setLoading(true);
    await discardChanges();
    setLoading(false);
  };

  // 状态文本
  const statusText = {
    executing: "执行中",
    awaiting_review: "待审核",
    terminated: "已终止",
    idle: "",
  }[status] || status;

  // 状态图标
  const StatusIcon = {
    executing: Play,
    awaiting_review: AlertTriangle,
    terminated: Square,
    idle: Play,
  }[status] || Play;

  return (
    <div className={`execution-status-bar status-${status}`}>
      {/* 状态信息 */}
      <div className="execution-status-info">
        <span className={`execution-status-indicator ${status}`}>
          <StatusIcon size={14} />
        </span>
        <span className="execution-status-text">{statusText}</span>
        {execution.planId && (
          <span className="execution-status-plan">
            Plan: {execution.planId.slice(0, 12)}...
          </span>
        )}
        {execution.task && (
          <span className="execution-status-task" title={execution.task}>
            {execution.task.length > 30 ? execution.task.slice(0, 30) + "..." : execution.task}
          </span>
        )}
      </div>

      {/* 操作按钮 */}
      <div className="execution-status-actions">
        {isExecuting && (
          <button
            type="button"
            className="execution-btn terminate"
            onClick={handleTerminate}
            disabled={loading}
            title="终止执行"
          >
            <Square size={14} />
            {loading ? "终止中..." : "终止"}
          </button>
        )}

        {isAwaitingReview && (
          <>
            <button
              type="button"
              className="execution-btn apply"
              onClick={handleApply}
              disabled={loading}
              title="应用变更"
            >
              <Check size={14} />
              {loading ? "处理中..." : "应用"}
            </button>
            <button
              type="button"
              className="execution-btn discard"
              onClick={handleDiscard}
              disabled={loading}
              title="丢弃变更"
            >
              <X size={14} />
              丢弃
            </button>
            <button
              type="button"
              className="execution-btn terminate"
              onClick={handleTerminate}
              disabled={loading}
              title="终止执行"
            >
              <Square size={14} />
              终止
            </button>
          </>
        )}
      </div>
    </div>
  );
}
