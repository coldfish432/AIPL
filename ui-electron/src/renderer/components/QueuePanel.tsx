import React from "react";
import { QueueItem } from "../hooks/useQueue";
import { getStatusDisplayText, getStatusClassName } from "../lib/status";

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
  return (
    <div className="pilot-queue">
      <div className="pilot-queue-header">
        <div className="pilot-queue-title">队列状态（全局）</div>
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
          <option value="">队列操作</option>
          <option value="toggle">{paused ? "继续队列" : "暂停队列"}</option>
          <option value="terminate">终止队列</option>
          <option value="clear">清空队列</option>
        </select>
      </div>
      {queue.length === 0 ? (
        <div className="muted">暂无队列任务。</div>
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
                  {getStatusDisplayText({ execution: item.status, review: item.reviewStatus ?? null })}
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
