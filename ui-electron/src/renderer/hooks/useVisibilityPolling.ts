/**
 * Visibility Polling Hook
 * 基于页面可见性的轮询
 */

import { useCallback, useEffect, useRef } from "react";

/**
 * 当页面可见时执行轮询
 */
export function useVisibilityPolling(
  callback: () => void | Promise<void>,
  interval: number,
  enabled = true
): void {
  const callbackRef = useRef(callback);
  const timerRef = useRef<number | null>(null);

  // 保持 callback 最新
  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  // 执行回调
  const execute = useCallback(async () => {
    try {
      await callbackRef.current();
    } catch {
      // 忽略错误
    }
  }, []);

  // 启动轮询
  const startPolling = useCallback(() => {
    if (timerRef.current) return;

    timerRef.current = window.setInterval(execute, interval);
  }, [execute, interval]);

  // 停止轮询
  const stopPolling = useCallback(() => {
    if (timerRef.current) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  // 处理可见性变化
  useEffect(() => {
    if (!enabled) {
      stopPolling();
      return;
    }

    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        execute(); // 立即执行一次
        startPolling();
      } else {
        stopPolling();
      }
    };

    // 初始状态
    if (document.visibilityState === "visible") {
      startPolling();
    }

    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      stopPolling();
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [enabled, execute, startPolling, stopPolling]);
}
