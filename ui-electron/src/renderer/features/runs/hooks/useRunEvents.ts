/**
 * Run Events Hook
 * 管理 Run 事件流
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { getRunEvents, streamRunEvents } from "@/apis";
import { extractEvents, getEventKey, StreamState } from "@/lib/events";
import type { RunEvent } from "@/apis/types";

interface UseRunEventsOptions {
  runId: string;
  planId?: string;
  enabled?: boolean;
  historyLimit?: number;
}

interface UseRunEventsReturn {
  events: RunEvent[];
  streamState: StreamState;
  reconnect: () => void;
  clearEvents: () => void;
}

export function useRunEvents({
  runId,
  planId,
  enabled = true,
  historyLimit = 500,
}: UseRunEventsOptions): UseRunEventsReturn {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [streamState, setStreamState] = useState<StreamState>("connecting");
  
  const seenRef = useRef<Set<string>>(new Set());
  const esRef = useRef<EventSource | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const activeRef = useRef(true);

  // 合并新事件，去重
  const mergeEvents = useCallback((newEvents: RunEvent[]) => {
    setEvents((prev) => {
      const merged = [...prev];
      const seen = seenRef.current;

      for (const item of newEvents) {
        const key = getEventKey(item);
        if (seen.has(key)) continue;
        seen.add(key);
        merged.push(item);
      }

      return merged;
    });
  }, []);

  // 清除事件
  const clearEvents = useCallback(() => {
    setEvents([]);
    seenRef.current = new Set();
  }, []);

  // 加载历史事件
  useEffect(() => {
    if (!enabled) return;

    async function loadHistory() {
      try {
        const history = await getRunEvents(runId, planId, 0, historyLimit);
        const extracted = extractEvents(history);
        if (extracted.length > 0) {
          mergeEvents(extracted);
        }
      } catch {
        // 忽略历史加载错误
      }
    }

    loadHistory();
  }, [runId, planId, enabled, historyLimit, mergeEvents]);

  // SSE 连接管理
  const connect = useCallback(() => {
    if (!enabled || !activeRef.current) return;

    setStreamState("connecting");
    esRef.current?.close();

    const es = streamRunEvents(runId, planId);
    esRef.current = es;

    es.onopen = () => {
      if (!activeRef.current) return;
      setStreamState("connected");
    };

    es.onmessage = (evt) => {
      try {
        const payload = JSON.parse(evt.data);
        const newEvents = extractEvents(payload);
        if (newEvents.length > 0) {
          mergeEvents(newEvents);
        }
      } catch {
        // 忽略解析错误
      }
    };

    es.onerror = () => {
      if (!activeRef.current) return;
      setStreamState("disconnected");
      es.close();
      
      // 自动重连
      if (reconnectTimerRef.current) {
        window.clearTimeout(reconnectTimerRef.current);
      }
      reconnectTimerRef.current = window.setTimeout(connect, 1500);
    };
  }, [runId, planId, enabled, mergeEvents]);

  // 初始化连接
  useEffect(() => {
    activeRef.current = true;
    connect();

    return () => {
      activeRef.current = false;
      if (reconnectTimerRef.current) {
        window.clearTimeout(reconnectTimerRef.current);
      }
      esRef.current?.close();
    };
  }, [connect]);

  // runId 或 planId 变化时重置
  useEffect(() => {
    clearEvents();
    setStreamState("connecting");
  }, [runId, planId, clearEvents]);

  return {
    events,
    streamState,
    reconnect: connect,
    clearEvents,
  };
}
