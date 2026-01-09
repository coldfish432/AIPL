import React from "react";
import { useI18n } from "../../lib/useI18n";
import { RetryOptions } from "../../apiClient";
import { StreamState } from "../../lib/events";

type Props = {
  onBack: () => void;
  onDeleteRun: () => void;
  onCancel: () => void;
  onRetry: (options?: RetryOptions) => void;
  actionLoading: boolean;
  isRunning: boolean;
  canRetry: boolean;
  retryMenuOpen: boolean;
  onToggleRetryMenu: () => void;
  streamState: StreamState;
  error: string | null;
  inlineNotice: string | null;
};

export default function RunActionBar({
  onBack,
  onDeleteRun,
  onCancel,
  onRetry,
  actionLoading,
  isRunning,
  canRetry,
  retryMenuOpen,
  onToggleRetryMenu,
  streamState,
  error,
  inlineNotice
}: Props) {
  const { t } = useI18n();
  const streamLabel = t.status[streamState as keyof typeof t.status] || streamState;

  return (
    <>
      <div className="run-action-bar">
        <div className="run-action-buttons">
          <button className="button-secondary" onClick={onBack}>{t.buttons.back}</button>
          <button className="button-danger" onClick={onDeleteRun} disabled={actionLoading}>{t.buttons.deleteRun}</button>
          {isRunning && (
            <button className="button-danger" onClick={onCancel} disabled={actionLoading}>
              {t.buttons.cancelRun}
            </button>
          )}
          {canRetry && (
            <div className="dropdown">
              <button className="button-secondary" onClick={onToggleRetryMenu} disabled={actionLoading}>
                {t.buttons.retry}
              </button>
              {retryMenuOpen && (
                <div className="dropdown-menu">
                  <button onClick={() => onRetry()}>{t.buttons.retry}</button>
                  <button onClick={() => onRetry({ retryDeps: true })}>{t.buttons.retryWithDeps}</button>
                  <button onClick={() => onRetry({ force: true })}>{t.buttons.retryForce}</button>
                </div>
              )}
            </div>
          )}
        </div>
        <div className="run-action-status">
          <span className={`status-pill ${streamState}`}>{t.labels.stream} {streamLabel}</span>
          {error && <span className="page-inline-error">{error}</span>}
        </div>
      </div>
      {inlineNotice && <div className="page-inline-note">{inlineNotice}</div>}
    </>
  );
}
