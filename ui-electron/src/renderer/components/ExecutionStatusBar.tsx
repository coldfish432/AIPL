import { useState } from "react";

import { useI18n } from "../lib/useI18n";
import { usePlanLock } from "../hooks/usePlanLock";

export default function ExecutionStatusBar() {
  const { lock, cancelExecution, pauseExecution, resumeExecution, forceUnlockLocal } = usePlanLock();
  const { t } = useI18n();
  const [loading, setLoading] = useState(false);

  if (lock.status === "idle") {
    return null;
  }

  const handleCancel = async () => {
    const confirmText = t.messages?.confirmCancel || "Confirm cancel?";
    if (!window.confirm(confirmText)) {
      return;
    }
    setLoading(true);
    try {
      const success = await cancelExecution();
      if (!success) {
        window.alert(t.messages?.cancelFailed || "Cancel failed, please try again");
      }
    } finally {
      setLoading(false);
    }
  };

  const handlePause = async () => {
    setLoading(true);
    try {
      await pauseExecution();
    } finally {
      setLoading(false);
    }
  };

  const handleResume = async () => {
    setLoading(true);
    try {
      await resumeExecution();
    } finally {
      setLoading(false);
    }
  };

  const statusTextMap: Record<string, string> = {
    executing: t.status?.running || "Running",
    paused: t.status?.paused || "Paused",
    awaiting_review: t.status?.awaiting_review || "Awaiting review"
  };
  const statusText = statusTextMap[lock.status] || lock.status;

  return (
    <div className="execution-status-bar">
      <span className="status-indicator">
        [{statusText}] {lock.activePlanId || "-"}
      </span>
      <div className="status-actions">
        {lock.status === "executing" && (
          <>
            <button
              className="btn btn-warning"
              onClick={handlePause}
              disabled={loading}
              type="button"
            >
              {t.buttons?.pauseRun || "Pause"}
            </button>
            <button
              className="btn btn-danger"
              onClick={handleCancel}
              disabled={loading}
              type="button"
            >
              {loading ? "..." : t.buttons?.cancelRun || "Cancel run"}
            </button>
          </>
        )}
        {lock.status === "paused" && (
          <>
            <button
              className="btn btn-primary"
              onClick={handleResume}
              disabled={loading}
              type="button"
            >
              {t.buttons?.resumeRun || "Resume"}
            </button>
            <button
              className="btn btn-danger"
              onClick={handleCancel}
              disabled={loading}
              type="button"
            >
              {t.buttons?.cancelRun || "Cancel run"}
            </button>
          </>
        )}
        <button
          className="btn btn-outline"
          onClick={forceUnlockLocal}
          type="button"
          title={t.messages?.forceUnlockHint || "Only clears frontend state, backend tasks may still be running"}
        >
          {t.buttons?.forceUnlock || "Force Unlock"}
        </button>
      </div>
    </div>
  );
}
