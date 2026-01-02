import React, { useEffect, useMemo, useState } from "react";
import { deletePlan, getPlan, PlanDetailResponse, PlanTask } from "../apiClient";
import TaskGraph from "../components/TaskGraph";

type Props = {
  planId: string;
  onBack: () => void;
};

function formatDeps(deps: string[] | undefined) {
  if (!Array.isArray(deps) || deps.length === 0) return "-";
  return deps.join(", ");
}

export default function PlanDetail({ planId, onBack }: Props) {
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
      const message = err instanceof Error ? err.message : "加载计划失败";
      setError(message || "加载计划失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleDeletePlan() {
    if (!window.confirm("确认删除这个 plan 吗？相关 runs 和 artifacts 也会被删除。")) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await deletePlan(planId);
      onBack();
    } catch (err) {
      const message = err instanceof Error ? err.message : "删除计划失败";
      setError(message || "删除计划失败");
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
        <button onClick={onBack}>返回</button>
        <button onClick={load} disabled={loading}>{loading ? "加载中..." : "刷新"}</button>
        <button onClick={handleDeletePlan} disabled={loading}>删除计划</button>
        {error && <span className="error">{error}</span>}
      </div>
      <div className="grid">
        <div className="card">
          <h2>计划信息</h2>
          <div className="list">
            <div className="list-item">
              <div className="title">计划 ID</div>
              <div className="meta">{planId}</div>
            </div>
            <div className="list-item">
              <div className="title">输入任务</div>
              <div className="meta">{planInfo?.input_task || planInfo?.inputTask || "-"}</div>
            </div>
          </div>
        </div>
        <div className="card">
          <div className="row">
            <h2>任务链</h2>
            <div className="mode-toggle">
              <button className={viewMode === "list" ? "active" : ""} onClick={() => setViewMode("list")}>
                列表
              </button>
              <button className={viewMode === "graph" ? "active" : ""} onClick={() => setViewMode("graph")}>
                图形
              </button>
            </div>
          </div>
          {viewMode === "list" ? (
            <div className="list">
              {tasks.length === 0 && <div className="muted">暂无任务数据。</div>}
              {tasks.map((task: PlanTask, idx: number) => {
                const taskId = task.step_id || task.id || task.task_id || `task-${idx + 1}`;
                const title = task.title || task.name || `任务 ${idx + 1}`;
                const status = task.status || "pending";
                return (
                  <div key={taskId} className="list-item task-item">
                    <div>
                      <div className="title">{title}</div>
                      <div className="meta">id {taskId}</div>
                      {task.description && <div className="meta">{task.description}</div>}
                      <div className="meta">依赖 {formatDeps(task.dependencies)}</div>
                      {task.capabilities && task.capabilities.length > 0 && (
                        <div className="meta">能力 {task.capabilities.join(", ")}</div>
                      )}
                    </div>
                    <div className={`pill ${status}`}>{status}</div>
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
        <h2>计划文本</h2>
        <pre className="pre">{planText || "暂无计划文本。"}</pre>
      </div>
    </section>
  );
}
