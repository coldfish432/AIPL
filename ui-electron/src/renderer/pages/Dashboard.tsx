import React, { useEffect, useMemo, useState } from "react";
import { createPlan, createRun, listPlans, listRuns } from "../apiclient";

type Props = {
  onSelectRun: (runId: string, planId?: string) => void;
  onSelectPlan: (planId: string) => void;
};

function formatId(item: any, key: string, fallbackKey?: string) {
  return item?.[key] || (fallbackKey ? item?.[fallbackKey] : null) || item?.id || "unknown";
}

function formatUpdated(updated: any) {
  if (!updated) return null;
  if (typeof updated === "number") {
    const dt = new Date(updated);
    if (!Number.isNaN(dt.getTime())) {
      return dt.toLocaleString();
    }
  }
  return String(updated);
}

export default function Dashboard({ onSelectRun, onSelectPlan }: Props) {
  const [plans, setPlans] = useState<any[]>([]);
  const [runs, setRuns] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [task, setTask] = useState("");
  const [planId, setPlanId] = useState("");
  const [workspace, setWorkspace] = useState(() => localStorage.getItem("aipl.workspace") || "");
  const [actionLoading, setActionLoading] = useState(false);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [p, r] = await Promise.all([listPlans(), listRuns()]);
      setPlans(p);
      setRuns(r);
    } catch (err: any) {
      setError(err?.message || "Failed to load");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const canSubmit = useMemo(() => task.trim().length > 0 && !actionLoading, [task, actionLoading]);

  async function handleCreate(kind: "plan" | "run") {
    if (!task.trim()) {
      setActionMsg("Please enter a task.");
      return;
    }
    setActionLoading(true);
    setActionMsg(null);
    try {
      const payload = {
        task: task.trim(),
        planId: planId.trim() || undefined,
        workspace: workspace.trim() || undefined
      };
      const res = kind === "plan" ? await createPlan(payload) : await createRun(payload);
      const resPlanId = res?.plan_id || res?.planId;
      const resRunId = res?.run_id || res?.runId;
      setActionMsg(kind === "plan" ? `Plan created: ${resPlanId || "unknown"}` : `Run created: ${resRunId || "unknown"}`);
      if (workspace.trim()) {
        localStorage.setItem("aipl.workspace", workspace.trim());
      }
      await load();
      if (kind === "plan" && resPlanId) {
        onSelectPlan(resPlanId);
      }
      if (kind === "run" && resRunId) {
        onSelectRun(resRunId, resPlanId);
      }
    } catch (err: any) {
      setActionMsg(err?.message || "Failed to create");
    } finally {
      setActionLoading(false);
    }
  }

  return (
    <section className="stack">
      <div className="row">
        <button onClick={load} disabled={loading}>{loading ? "Loading..." : "Refresh"}</button>
        {error && <span className="error">{error}</span>}
      </div>
      <div className="grid">
        <div className="card">
          <h2>New Task</h2>
          <div className="stack">
            <textarea
              className="textarea"
              placeholder="Describe the task you want to run"
              value={task}
              onChange={(e) => setTask(e.target.value)}
              rows={3}
            />
            <div className="row">
              <input
                className="input"
                placeholder="Plan ID (optional)"
                value={planId}
                onChange={(e) => setPlanId(e.target.value)}
              />
              <input
                className="input"
                placeholder="Workspace path (optional)"
                value={workspace}
                onChange={(e) => setWorkspace(e.target.value)}
              />
            </div>
            <div className="row">
              <button onClick={() => handleCreate("plan")} disabled={!canSubmit}>
                {actionLoading ? "Working..." : "Create Plan"}
              </button>
              <button onClick={() => handleCreate("run")} disabled={!canSubmit}>
                {actionLoading ? "Working..." : "Start Run"}
              </button>
              {actionMsg && <span className={actionMsg.startsWith("Failed") ? "error" : "muted"}>{actionMsg}</span>}
            </div>
          </div>
        </div>
        <div className="card">
          <h2>Plans</h2>
          <div className="list">
            {plans.length === 0 && <div className="muted">No plans found.</div>}
            {plans.map((plan) => {
              const planId = formatId(plan, "plan_id", "planId");
              const updated = formatUpdated(plan.updated_at || plan.updatedAt || plan.ts);
              const tasksCount = plan.tasks_count || plan.tasksCount;
              return (
                <button key={planId} className="list-item button" onClick={() => onSelectPlan(planId)}>
                  <div>
                    <div className="title">{planId}</div>
                    {updated && <div className="meta">updated {updated}</div>}
                  </div>
                  {typeof tasksCount === "number" && <div className="pill">{tasksCount} tasks</div>}
                </button>
              );
            })}
          </div>
        </div>
        <div className="card">
          <h2>Runs</h2>
          <div className="list">
            {runs.length === 0 && <div className="muted">No runs found.</div>}
            {runs.map((run) => {
              const runId = formatId(run, "run_id", "runId");
              const status = run.status || run.state || "unknown";
              const planId = run.plan_id || run.planId;
              return (
                <button key={runId} className="list-item button" onClick={() => onSelectRun(runId, planId)}>
                  <div className="title">{runId}</div>
                  <div className={`pill ${status}`}>{status}</div>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
