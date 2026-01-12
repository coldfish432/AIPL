/**
 * Run Action Bar 组件
 * 显示 Run 操作按钮
 */

import React from "react";
import { ArrowLeft, MoreVertical, RefreshCw, X, Trash2 } from "lucide-react";
import { useI18n } from "@/hooks/useI18n";
import type { StreamState } from "@/lib/events";
import type { RetryOptions } from "@/apis/types";

interface RunActionBarProps {
  onBack: () => void;
  onDelete: () => Promise<void>;
  onCancel: () => Promise<void>;
  onRetry: (options?: RetryOptions) => Promise<void>;
  loading: boolean;
  isRunning: boolean;
  canRetry: boolean;
  retryMenuOpen: boolean;
  onToggleRetryMenu: () => void;
  streamState: StreamState;
  error: string | null;
  inlineNotice: string | null;
}

export function RunActionBar({
  onBack,
  onDelete,
  onCancel,
  onRetry,
  loading,
  isRunning,
  canRetry,
  retryMenuOpen,
  onToggleRetryMenu,
  streamState,
  error,
  inlineNotice,
}: RunActionBarProps) {
  const { t } = useI18n();

  const handleDelete = async () => {
    if (!window.confirm(t.messages.confirmDeleteRun)) return;
    await onDelete();
  };

  const handleCancel = async () => {
    if (!window.confirm(t.messages.confirmCancelRun)) return;
    await onCancel();
  };

  return (
    <div className="run-action-bar">
      <div className="run-action-bar-left">
        <button className="button-icon" onClick={onBack} title={t.buttons.back}>
          <ArrowLeft size={18} />
        </button>

        <div className="stream-status">
          <span className={`stream-indicator ${streamState}`} />
          <span className="stream-label">{t.status[streamState]}</span>
        </div>

        {error && <span className="inline-error">{error}</span>}
        {inlineNotice && <span className="inline-notice">{inlineNotice}</span>}
      </div>

      <div className="run-action-bar-right">
        {isRunning && (
          <button
            className="button-secondary"
            onClick={handleCancel}
            disabled={loading}
          >
            <X size={14} />
            {t.buttons.cancelRun}
          </button>
        )}

        {canRetry && (
          <div className="dropdown">
            <button
              className="button-primary"
              onClick={() => onRetry()}
              disabled={loading}
            >
              <RefreshCw size={14} />
              {t.buttons.retry}
            </button>
            <button
              className="button-icon"
              onClick={onToggleRetryMenu}
              disabled={loading}
            >
              <MoreVertical size={14} />
            </button>

            {retryMenuOpen && (
              <div className="dropdown-menu">
                <button
                  className="dropdown-item"
                  onClick={() => onRetry({ resetAll: false })}
                >
                  {t.buttons.retryWithDeps}
                </button>
                <button
                  className="dropdown-item"
                  onClick={() => onRetry({ resetAll: true })}
                >
                  {t.buttons.retryForce}
                </button>
              </div>
            )}
          </div>
        )}

        <button
          className="button-danger"
          onClick={handleDelete}
          disabled={loading}
        >
          <Trash2 size={14} />
          {t.buttons.deleteRun}
        </button>
      </div>
    </div>
  );
}
