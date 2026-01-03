import React, { useEffect, useMemo, useState } from "react";
import { deletePlan, getPlan, PlanDetailResponse, PlanTask } from "../apiClient";
import TaskGraph from "../components/TaskGraph";
import { useI18n } from "../lib/useI18n";

type Props = {
  planId: string;
  onBack: () => void;
};

function formatDeps(deps: string[] | undefined) {
  if (!Array.isArray(deps) || deps.length === 0) return "-";
  return deps.join(", ");
}

export default function PlanDetail({ planId, onBack }: Props) {
  const { t } = useI18n();
  const [planData, setPlanData] = useState<PlanDetailResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"list" | "graph">("list");

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = await getPlan(planId);
      setPlanData(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : t.messages.loadPlanFailed;
      setError(message || t.messages.loadPlanFailed);
    } finally {
      setLoading(false);
    }
  }

  async function handleDeletePlan() {
    if (!window.confirm(t.messages.confirmDeletePlan)) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await deletePlan(planId);
      onBack();
    } catch (err) {
      const message = err instanceof Error ? err.message : t.messages.deleteFailed;
      setError(message || t.messages.deleteFailed);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [planId]);

  const planInfo = planData?.plan || null;
  const planText = planData?.task_chain_text || planInfo?.task_chain_text || "";
  const snapshotTasks = planData?.snapshot?.tasks || [];
  const rawTasks = planInfo?.raw_plan?.tasks || [];
  const tasks = useMemo(() => (snapshotTasks.length > 0 ? snapshotTasks : rawTasks), [snapshotTasks, rawTasks]);

  return (
    <section className="stack">
      <div className="row">
        <button onClick={onBack}>{t.buttons.back}</button>
        <button onClick={load} disabled={loading}>{loading ? t.messages.loading : t.buttons.refresh}</button>
        <button onClick={handleDeletePlan} disabled={loading}>{t.buttons.deletePlan}</button>
        {error && <span className="error">{error}</span>}
      </div>
      <div className="grid">
        <div className="card">
          <h2>{t.titles.planInfo}</h2>
          <div className="list">
            <div className="list-item">
              <div className="title">{t.labels.planId}</div>
              <div className="meta">{planId}</div>
            </div>
            <div className="list-item">
              <div className="title">{t.labels.inputTask}</div>
              <div className="meta">{planInfo?.input_task || planInfo?.inputTask || "-"}</div>
            </div>
          </div>
        </div>
        <div className="card">
          <div className="row">
            <h2>{t.titles.taskChain}</h2>
            <div className="mode-toggle">
              <button className={viewMode === "list" ? "active" : ""} onClick={() => setViewMode("list")}>
                {t.labels.listView}
              </button>
              <button className={viewMode === "graph" ? "active" : ""} onClick={() => setViewMode("graph")}>
                {t.labels.graphView}
              </button>
            </div>
          </div>
          {viewMode === "list" ? (
            <div className="list">
              {tasks.length === 0 && <div className="muted">{t.messages.taskChainEmptyData}</div>}
              {tasks.map((task: PlanTask, idx: number) => {
                const taskId = task.step_id || task.id || task.task_id || `task-${idx + 1}`;
                const title = task.title || task.name || `${t.labels.task} ${idx + 1}`;
                const status = String(task.status || "pending").toLowerCase();
                const statusLabel = t.status[status as keyof typeof t.status] || status;
                return (
                  <div key={taskId} className="list-item task-item">
                    <div>
                      <div className="title">{title}</div>
                      <div className="meta">{t.labels.taskId} {taskId}</div>
                      {task.description && <div className="meta">{task.description}</div>}
                      <div className="meta">{t.labels.dependencies} {formatDeps(task.dependencies)}</div>
                      {task.capabilities && task.capabilities.length > 0 && (
                        <div className="meta">{t.labels.capabilities} {task.capabilities.join(", ")}</div>
                      )}
                    </div>
                    <div className={`pill ${status}`}>{statusLabel}</div>
                  </div>
                );
              })}
            </div>
          ) : (
            <TaskGraph tasks={tasks} />
          )}
        </div>
      </div>
      <div className="card">
        <h2>{t.titles.planText}</h2>
        <pre className="pre">{planText || t.messages.planEmpty}</pre>
      </div>
    </section>
  );
}
