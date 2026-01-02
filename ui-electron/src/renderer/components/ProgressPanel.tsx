import React from "react";
import { RunEvent } from "../apiClient";
import { formatEventMessage, formatEventType, formatTimestamp } from "../lib/events";

type Props = {
  progress: number;
  currentStep: string;
  latestEvents: RunEvent[];
  warningCount: number;
  errorCount: number;
};

export default function ProgressPanel({ progress, currentStep, latestEvents, warningCount, errorCount }: Props) {
  return (
    <div className="progress-panel">
      <div className="progress large">
        <div className="progress-bar" style={{ width: `${progress}%` }} />
      </div>
      <div className="row">
        <span className="pill">{progress}%</span>
        <span className="pill subtle">步骤 {currentStep}</span>
        {errorCount > 0 && <span className="pill error">错误 {errorCount}</span>}
        {warningCount > 0 && <span className="pill warn">警告 {warningCount}</span>}
      </div>
      <div className="list compact">
        {latestEvents.map((evt, idx) => (
          <div key={`${formatEventType(evt)}-${idx}`} className="list-item">
            <div>
              <div className="title">{formatEventType(evt)}</div>
              <div className="meta">{formatTimestamp(evt.ts ?? evt.time ?? evt.timestamp ?? evt.created_at) || "-"}</div>
            </div>
            <div className="meta">{formatEventMessage(evt)}</div>
          </div>
        ))}
        {latestEvents.length === 0 && <div className="muted">暂无最近事件。</div>}
      </div>
    </div>
  );
}
