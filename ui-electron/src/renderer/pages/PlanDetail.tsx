import React, { useEffect, useMemo, useState } from "react";
import { getPlan } from "../apiclient";

type Props = {
  planId: string;
  onBack: () => void;
};

function formatDeps(deps: any) {
  if (!Array.isArray(deps) || deps.length === 0) return "-";
  return deps.join(", ");
}

export default function PlanDetail({ planId, onBack }: Props) {
  const [planData, setPlanData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = await getPlan(planId);
      setPlanData(data);
    } catch (err: any) {
      setError(err?.message || "Failed to load plan");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [planId]);

  const planInfo = planData?.plan || null;
  const snapshotTasks = planData?.snapshot?.tasks || [];
  const rawTasks = planInfo?.raw_plan?.tasks || [];
  const tasks = useMemo(() => (snapshotTasks.length > 0 ? snapshotTasks : rawTasks), [snapshotTasks, rawTasks]);

  return (
    <section className="stack">
      <div className="row">
        <button onClick={onBack}>Back</button>
        <button onClick={load} disabled={loading}>{loading ? "Loading..." : "Refresh"}</button>
        {error && <span className="error">{error}</span>}
      </div>
      <div className="grid">
        <div className="card">
          <h2>Plan Info</h2>
          <div className="list">
            <div className="list-item">
              <div className="title">Plan ID</div>
              <div className="meta">{planId}</div>
            </div>
            <div className="list-item">
              <div className="title">Input Task</div>
              <div className="meta">{planInfo?.input_task || "-"}</div>
            </div>
          </div>
        </div>
        <div className="card">
          <h2>Task Chain</h2>
          <div className="list">
            {tasks.length === 0 && <div className="muted">No tasks found for this plan.</div>}
            {tasks.map((task: any, idx: number) => {
              const taskId = task.id || task.task_id || `task-${idx + 1}`;
              const title = task.title || task.name || `Task ${idx + 1}`;
              const status = task.status || "pending";
              return (
                <div key={taskId} className="list-item task-item">
                  <div>
                    <div className="title">{title}</div>
                    <div className="meta">id {taskId}</div>
                    <div className="meta">deps {formatDeps(task.dependencies)}</div>
                  </div>
                  <div className={`pill ${status}`}>{status}</div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
      {planInfo && (
        <div className="card">
          <h2>Plan Raw</h2>
          <pre className="pre">{JSON.stringify(planInfo, null, 2)}</pre>
        </div>
      )}
    </section>
  );
}
