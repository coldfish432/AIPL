import { useCallback, useEffect, useRef, useState } from "react";
import { loadJson, saveDebounced } from "../lib/storage";
import { STORAGE_KEYS } from "../config/settings";
import { ExecutionStatus, ReviewStatus } from "../lib/status";

export type QueueStatus = ExecutionStatus;

export type QueueItem = {
  id: string;
  planId: string;
  planText: string;
  status: QueueStatus;
  reviewStatus?: ReviewStatus | null;
  runId?: string;
  queuedAt: number;
  startedAt?: number;
  finishedAt?: number;
  baseWorkspace?: string;
  chatId?: string;
  chatTitle?: string;
};

const QUEUE_KEY = STORAGE_KEYS.queueKey;
const QUEUE_PAUSED_KEY = STORAGE_KEYS.queuePausedKey;

function loadQueue(): QueueItem[] {
  const items = loadJson<QueueItem[]>(QUEUE_KEY, []);
  if (!Array.isArray(items)) return [];
  return items.filter((item) => item && item.planId && item.id);
}

export function useQueue() {
  const [queue, setQueue] = useState<QueueItem[]>(() => loadQueue());
  const [paused, setPaused] = useState<boolean>(() => localStorage.getItem(QUEUE_PAUSED_KEY) === "true");
  const queueRef = useRef(queue);

  useEffect(() => {
    queueRef.current = queue;
    saveDebounced(QUEUE_KEY, queue);
  }, [queue]);

  useEffect(() => {
    localStorage.setItem(QUEUE_PAUSED_KEY, paused ? "true" : "false");
  }, [paused]);

  const updateQueue = useCallback((updater: (prev: QueueItem[]) => QueueItem[]) => {
    setQueue((prev) => updater(prev));
  }, []);

  const enqueue = useCallback((item: QueueItem) => {
    setQueue((prev) => prev.concat(item));
  }, []);

  const updateItem = useCallback((id: string, updater: (item: QueueItem) => QueueItem) => {
    setQueue((prev) => prev.map((item) => (item.id === id ? updater(item) : item)));
  }, []);

  const removeItem = useCallback((id: string) => {
    setQueue((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const clearQueue = useCallback(() => {
    setQueue([]);
  }, []);

  const cancelAll = useCallback(() => {
    const now = Date.now();
    setQueue((prev) =>
      prev.map((item) =>
        ["queued", "starting", "running", "retrying"].includes(item.status)
          ? { ...item, status: "canceled", finishedAt: now }
          : item
      )
    );
    setPaused(true);
  }, []);

  const getNextQueued = useCallback(() => {
    return queueRef.current.find((item) => item.status === "queued");
  }, []);

  const hasRunning = useCallback(() => {
    return queueRef.current.some((item) => ["running", "starting", "retrying"].includes(item.status));
  }, []);

  return {
    queue,
    paused,
    setPaused,
    enqueue,
    updateItem,
    removeItem,
    updateQueue,
    clearQueue,
    cancelAll,
    getNextQueued,
    hasRunning,
    queueRef
  };
}
