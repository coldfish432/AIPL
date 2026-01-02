import { useCallback, useEffect, useRef } from "react";

export function useVisibilityPolling(
  pollFn: () => void | Promise<void>,
  intervalMs: number,
  enabled: boolean = true
) {
  const timerRef = useRef<number | null>(null);

  const start = useCallback(() => {
    if (timerRef.current) return;
    timerRef.current = window.setInterval(pollFn, intervalMs);
  }, [pollFn, intervalMs]);

  const stop = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!enabled) {
      stop();
      return;
    }

    const handleVisibility = () => {
      if (document.hidden) {
        stop();
      } else {
        pollFn();
        start();
      }
    };

    document.addEventListener("visibilitychange", handleVisibility);
    start();

    return () => {
      document.removeEventListener("visibilitychange", handleVisibility);
      stop();
    };
  }, [enabled, start, stop, pollFn]);
}
