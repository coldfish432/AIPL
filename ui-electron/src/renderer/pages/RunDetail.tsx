import React, { useEffect, useRef, useState } from "react";
import { getRun, streamRunEvents } from "../apiclient";

type Props = {
  runId: string;
  planId?: string;
  onBack: () => void;
};

export default function RunDetail({ runId, planId, onBack }: Props) {
  const [run, setRun] = useState<any>(null);
  const [events, setEvents] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const logRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setEvents([]);
    setError(null);
    void (async () => {
      try {
        const data = await getRun(runId, planId);
        setRun(data);
      } catch (err: any) {
        setError(err?.message || "Failed to load run");
      }
    })();

    const es = streamRunEvents(runId, planId);
    es.onmessage = (evt) => {
      try {
        const payload = JSON.parse(evt.data);
        const data = payload?.data || payload;
        const next = Array.isArray(data?.events) ? data.events : [];
        if (next.length > 0) {
          setEvents((prev) => prev.concat(next));
        }
      } catch {
        // ignore parse errors
      }
    };
    es.onerror = () => {
      es.close();
    };

    return () => {
      es.close();
    };
  }, [runId, planId]);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [events]);

  return (
    <section className="stack">
      <div className="row">
        <button onClick={onBack}>Back</button>
        {error && <span className="error">{error}</span>}
      </div>
      <div className="card">
        <h2>Run Info</h2>
        <pre className="pre">{JSON.stringify(run, null, 2)}</pre>
      </div>
      <div className="card">
        <h2>Events</h2>
        <div className="log" ref={logRef}>
          {events.length === 0 && <div className="muted">Waiting for events...</div>}
          {events.map((evt, idx) => (
            <div key={idx} className="log-line">
              {JSON.stringify(evt)}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
