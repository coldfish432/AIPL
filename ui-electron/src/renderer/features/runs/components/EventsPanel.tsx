/**
 * Events Panel 组件
 * 显示事件时间线
 */

import React from "react";
import { useI18n } from "@/hooks/useI18n";
import { EventTimeline } from "@/components/common/EventTimeline";
import type { RunEvent } from "@/apis/types";
import type { StreamState } from "@/lib/events";

interface EventsPanelProps {
  events: RunEvent[];
  streamState: StreamState;
  onRework?: (stepId: string, feedback: string) => void;
}

export function EventsPanel({
  events,
  streamState,
  onRework,
}: EventsPanelProps) {
  const { t } = useI18n();

  const emptyLabel =
    streamState === "disconnected"
      ? t.messages.eventStreamDisconnected
      : streamState === "connecting"
        ? t.messages.eventStreamWaiting
        : undefined;

  return (
    <div className="panel">
      <div className="panel-header">
        <h2 className="panel-title">{t.titles.events}</h2>
        <div className="stream-status small">
          <span className={`stream-indicator ${streamState}`} />
          <span>{t.status[streamState]}</span>
        </div>
      </div>

      <EventTimeline
        events={events}
        streamState={streamState}
        autoScroll
        emptyLabel={emptyLabel}
        onRework={onRework}
      />
    </div>
  );
}
