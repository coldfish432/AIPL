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
    <div className="row">
      <button onClick={onBack}>{t.buttons.back}</button>
      <button onClick={onDeleteRun} disabled={actionLoading}>{t.buttons.deleteRun}</button>
      {isRunning && (
        <button onClick={onCancel} disabled={actionLoading} className="danger">
          {t.buttons.cancelRun}
        </button>
      )}
      {canRetry && (
        <div className="dropdown">
          <button onClick={onToggleRetryMenu} disabled={actionLoading}>
            {t.buttons.retry} ?
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
      <span className={`pill ${streamState}`}>{t.labels.stream} {streamLabel}</span>
      {error && <span className="error">{error}</span>}
      {inlineNotice && <span className="muted">{inlineNotice}</span>}
    </div>
  );
}
