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
    <section className="page">
      <div className="page-header">
      <div>
        <p className="page-subtitle">{t.labels.planId}: {planId}</p>
      </div>
        <div className="page-actions">
          <button className="button-secondary" onClick={onBack}>{t.buttons.back}</button>
          <button className="button-secondary" onClick={load} disabled={loading}>{loading ? t.messages.loading : t.buttons.refresh}</button>
          <button className="button-danger" onClick={handleDeletePlan} disabled={loading}>{t.buttons.deletePlan}</button>
        </div>
      </div>
      {error && <div className="page-alert">{error}</div>}
      <div className="panel-grid">
        <div className="panel">
          <div className="panel-header">
            <h2 className="panel-title">{t.titles.planInfo}</h2>
          </div>
          <div className="info-grid">
            <div className="info-item">
              <div className="info-label">{t.labels.planId}</div>
              <div className="info-value">{planId}</div>
            </div>
            <div className="info-item">
              <div className="info-label">{t.labels.inputTask}</div>
              <div className="info-value">{planInfo?.input_task || planInfo?.inputTask || "-"}</div>
            </div>
          </div>
        </div>
        <div className="panel">
          <div className="panel-header">
            <h2 className="panel-title">{t.titles.taskChain}</h2>
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
            <div className="card-list">
              {tasks.length === 0 && <div className="page-muted">{t.messages.taskChainEmptyData}</div>}
              {tasks.map((task: PlanTask, idx: number) => {
                const taskId = task.step_id || task.id || task.task_id || `task-${idx + 1}`;
                const title = task.title || task.name || `${t.labels.task} ${idx + 1}`;
                const status = String(task.status || "pending").toLowerCase();
                const statusLabel = t.status[status as keyof typeof t.status] || status;
                return (
                  <div key={taskId} className="card-item">
                    <div className="card-item-main">
                      <div className="card-item-title">{title}</div>
                      <div className="card-item-meta">{t.labels.taskId} {taskId}</div>
                      {task.description && <div className="card-item-meta">{task.description}</div>}
                      <div className="card-item-meta">{t.labels.dependencies} {formatDeps(task.dependencies)}</div>
                      {task.capabilities && task.capabilities.length > 0 && (
                        <div className="card-item-meta">{t.labels.capabilities} {task.capabilities.join(", ")}</div>
                      )}
                    </div>
                    <div className={`status-pill ${status}`}>{statusLabel}</div>
                  </div>
                );
              })}
            </div>
          ) : (
            <TaskGraph tasks={tasks} />
          )}
        </div>
      </div>
      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">{t.titles.planText}</h2>
        </div>
        <pre className="pre">{planText || t.messages.planEmpty}</pre>
      </div>
    </section>
  );
}
