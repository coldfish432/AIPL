import React from "react";
import { QueueItem } from "../hooks/useQueue";
import { getStatusClassName, getStatusDisplayText } from "../lib/status";
import { useI18n } from "../lib/useI18n";

type Props = {
  queue: QueueItem[];
  paused: boolean;
  onPauseToggle: () => void;
  onTerminate: () => void;
  onClear: () => void;
};

function getPreview(item: QueueItem): string {
  if (item.planText) {
    const firstLine = item.planText.split("\n").find((line) => line.trim()) || "";
    if (firstLine) return firstLine.trim();
  }
  return item.planId;
}

export default function QueuePanel({ queue, paused, onPauseToggle, onTerminate, onClear }: Props) {
  const { t } = useI18n();

  const getStatusLabel = (item: QueueItem) => {
    const review = item.reviewStatus ?? null;
    if (item.status === "completed" && review) {
      return t.status[review] || getStatusDisplayText({ execution: item.status, review });
    }
    return t.status[item.status] || getStatusDisplayText({ execution: item.status, review });
  };

  return (
    <div className="pilot-queue">
      <div className="pilot-queue-header">
        <div className="pilot-queue-title">{t.labels.queueStatusGlobal}</div>
        <select
          className="pilot-queue-select"
          value=""
          onChange={(e) => {
            const value = e.target.value;
            if (value === "toggle") onPauseToggle();
            if (value === "terminate") onTerminate();
            if (value === "clear") onClear();
          }}
          disabled={queue.length === 0}
        >
          <option value="">{t.labels.queueActions}</option>
          <option value="toggle">{paused ? t.buttons.resumeQueue : t.buttons.pauseQueue}</option>
          <option value="terminate">{t.buttons.terminateQueue}</option>
          <option value="clear">{t.buttons.clearQueue}</option>
        </select>
      </div>
      {queue.length === 0 ? (
        <div className="muted">{t.messages.queueEmpty}</div>
      ) : (
        <div className="pilot-queue-list">
          {queue.map((item, idx) => (
            <div
              key={item.id}
              className={`pilot-queue-item ${getStatusClassName({
                execution: item.status,
                review: item.reviewStatus ?? null
              })}`}
            >
              <div className="pilot-queue-meta">
                <span className="pilot-queue-index">#{idx + 1}</span>
                <span className="pilot-queue-status">
                  {getStatusLabel(item)}
                </span>
                {item.chatTitle && <span className="pilot-queue-chat">{item.chatTitle}</span>}
              </div>
              <div className="pilot-queue-text">{getPreview(item)}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
