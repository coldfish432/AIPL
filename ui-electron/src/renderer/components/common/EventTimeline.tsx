/**
 * Event Timeline 组件
 * 显示事件时间线
 */

import React, { useEffect, useRef } from "react";
import {
  AlertCircle,
  CheckCircle,
  Clock,
  Info,
  AlertTriangle,
  RefreshCw,
} from "lucide-react";
import { useI18n } from "@/hooks/useI18n";
import {
  formatEventType,
  formatEventTime,
  getEventMessage,
  getEventLevel,
  getEventProgress,
  getEventStepId,
  StreamState,
} from "@/lib/events";
import type { RunEvent } from "@/apis/types";

interface EventTimelineProps {
  events: RunEvent[];
  streamState: StreamState;
  autoScroll?: boolean;
  emptyLabel?: string;
  onRework?: (stepId: string, feedback: string) => void;
}

export function EventTimeline({
  events,
  streamState,
  autoScroll = true,
  emptyLabel,
  onRework,
}: EventTimelineProps) {
  const { t } = useI18n();
  const containerRef = useRef<HTMLDivElement>(null);
  const wasAtBottomRef = useRef(true);

  // 自动滚动
  useEffect(() => {
    if (!autoScroll || !containerRef.current) return;

    const container = containerRef.current;
    const isAtBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight < 50;

    if (wasAtBottomRef.current || isAtBottom) {
      container.scrollTop = container.scrollHeight;
    }

    wasAtBottomRef.current = isAtBottom;
  }, [events, autoScroll]);

  // 监听滚动
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleScroll = () => {
      const isAtBottom =
        container.scrollHeight - container.scrollTop - container.clientHeight < 50;
      wasAtBottomRef.current = isAtBottom;
    };

    container.addEventListener("scroll", handleScroll);
    return () => container.removeEventListener("scroll", handleScroll);
  }, []);

  if (events.length === 0) {
    return (
      <div className="timeline-empty">
        <Clock size={24} />
        <span>{emptyLabel || t.messages.noEvents}</span>
        {streamState === "connecting" && (
          <RefreshCw size={16} className="spin" />
        )}
      </div>
    );
  }

  return (
    <div className="timeline-container" ref={containerRef}>
      <div className="timeline">
        {events.map((event, idx) => (
          <EventItem
            key={`${formatEventType(event)}-${idx}`}
            event={event}
            onRework={onRework}
          />
        ))}

        {/* 流状态指示器 */}
        {streamState === "connecting" && (
          <div className="timeline-item connecting">
            <div className="timeline-icon">
              <RefreshCw size={14} className="spin" />
            </div>
            <div className="timeline-content">
              <div className="timeline-message">
                {t.messages.eventStreamReconnecting}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// 单个事件项
interface EventItemProps {
  event: RunEvent;
  onRework?: (stepId: string, feedback: string) => void;
}

function EventItem({ event, onRework }: EventItemProps) {
  const type = formatEventType(event);
  const time = formatEventTime(event);
  const message = getEventMessage(event);
  const level = getEventLevel(event);
  const progress = getEventProgress(event);
  const stepId = getEventStepId(event);

  const handleRework = () => {
    if (stepId && onRework) {
      const feedback = window.prompt("请输入返工反馈:");
      if (feedback) {
        onRework(stepId, feedback);
      }
    }
  };

  return (
    <div className={`timeline-item ${level}`}>
      <div className="timeline-icon">
        <EventIcon level={level} />
      </div>
      <div className="timeline-content">
        <div className="timeline-header">
          <span className="timeline-type">{type}</span>
          <span className="timeline-time">{time}</span>
        </div>
        {message && <div className="timeline-message">{message}</div>}
        {progress && (
          <div className="timeline-progress">
            <div className="progress small">
              <div
                className="progress-bar"
                style={{
                  width: `${Math.round((progress.current / progress.total) * 100)}%`,
                }}
              />
            </div>
            <span className="timeline-progress-text">
              {progress.current}/{progress.total}
            </span>
          </div>
        )}
        {stepId && event.status === "failed" && onRework && (
          <button className="timeline-action" onClick={handleRework}>
            返工此步骤
          </button>
        )}
      </div>
    </div>
  );
}

// 事件图标
function EventIcon({ level }: { level: string }) {
  switch (level) {
    case "error":
      return <AlertCircle size={14} />;
    case "warn":
      return <AlertTriangle size={14} />;
    case "success":
      return <CheckCircle size={14} />;
    default:
      return <Info size={14} />;
  }
}
