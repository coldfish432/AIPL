import React, { useEffect, useRef } from "react";
import { RunEvent } from "../apiClient";
import {
  StreamState,
  formatEventMessage,
  formatStepSummary,
  formatTimestamp,
  getEventKey,
  getEventLevel,
  getEventStepId,
  getEventTypeLabel,
  formatEventType
} from "../lib/events";
import { useI18n } from "../lib/useI18n";

type Props = {
  events: RunEvent[];
  streamState?: StreamState;
  autoScroll?: boolean;
  emptyLabel?: string;
  onRework?: (stepId: string | null) => void;
};

export default function EventTimeline({ events, streamState, autoScroll, emptyLabel, onRework }: Props) {
  const { language, t } = useI18n();
  const logRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!autoScroll || !logRef.current) return;
    logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [autoScroll, events]);

  return (
    <div className="timeline" ref={logRef}>
      {streamState === "disconnected" && <div className="timeline-banner">{t.messages.eventStreamReconnecting}</div>}
      {events.length === 0 && (
        <div className="muted">{emptyLabel || t.messages.eventStreamWaiting}</div>
      )}
      {events.map((evt, idx) => {
        const time = formatTimestamp(evt.ts ?? evt.time ?? evt.timestamp ?? evt.created_at);
        const label = language === "zh" ? getEventTypeLabel(evt) : formatEventType(evt);
        const summary = language === "zh" ? formatStepSummary(evt) : formatEventMessage(evt);
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
                {t.buttons.rework}
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
