import React, { useEffect, useRef } from "react";
import { RunEvent } from "../apiClient";
import {
  StreamState,
  formatStepSummary,
  formatTimestamp,
  getEventKey,
  getEventLevel,
  getEventStepId,
  getEventTypeLabel
} from "../lib/events";

type Props = {
  events: RunEvent[];
  streamState?: StreamState;
  autoScroll?: boolean;
  emptyLabel?: string;
  onRework?: (stepId: string | null) => void;
};

export default function EventTimeline({ events, streamState, autoScroll, emptyLabel, onRework }: Props) {
  const logRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!autoScroll || !logRef.current) return;
    logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [autoScroll, events]);

  return (
    <div className="timeline" ref={logRef}>
      {streamState === "disconnected" && <div className="timeline-banner">正在重连...</div>}
      {events.length === 0 && (
        <div className="muted">{emptyLabel || "等待事件中..."}</div>
      )}
      {events.map((evt, idx) => {
        const time = formatTimestamp(evt.ts ?? evt.time ?? evt.timestamp ?? evt.created_at);
        const label = getEventTypeLabel(evt);
        const summary = formatStepSummary(evt);
        const level = getEventLevel(evt);
        const stepId = getEventStepId(evt);
        
        return (
          <div key={`${getEventKey(evt)}-${idx}`} className={`timeline-item ${level ? `level-${level}` : ""}`}>
            <div className="timeline-time">{time || "-"}</div>
            <div className="timeline-label">[{label}]</div>
            <div className="timeline-summary">{summary || "-"}</div>
            {level === "error" && (
              <button
                className="link-button"
                onClick={() => onRework?.(stepId)}
                disabled={!onRework}
              >
                返工
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
