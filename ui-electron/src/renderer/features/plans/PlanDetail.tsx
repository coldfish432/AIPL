/**
 * PlanDetail - 计划详情页
 * 
 * 功能：
 * 1. 显示计划信息和任务链
 * 2. 返工功能（重置所有任务状态为 todo 并重新执行）
 * 3. 启动新执行
 * 4. 关联的 runs 列表
 */

import React, { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  Play,
  RefreshCw,
  RotateCcw,
  FileText,
  CheckCircle,
  Clock,
  XCircle,
  Loader2,
  AlertTriangle,
  List,
  Trash2,
} from "lucide-react";

import { useWorkspace } from "@/contexts/WorkspaceContext";
import { useExecution } from "@/contexts/ExecutionContext";
import { useI18n } from "@/hooks/useI18n";
import {
  getPlan,
  reworkPlan,
  startRun,
  deletePlan,
  listRuns,
  PlanDetailResponse,
  PlanTask,
  RunSummary,
} from "@/services/api";

// ============================================================
// Helpers
// ============================================================

function getTaskStatus(status: string | undefined): { text: string; icon: React.ElementType; className: string } {
  const normalized = status?.toLowerCase().replace(/-/g, "_") || "todo";
  
  switch (normalized) {
    case "done":
    case "completed":
      return { text: "已完成", icon: CheckCircle, className: "task-done" };
    case "doing":
    case "running":
      return { text: "执行中", icon: Play, className: "task-running" };
    case "failed":
    case "error":
      return { text: "失败", icon: XCircle, className: "task-failed" };
    case "todo":
    case "queued":
    default:
      return { text: "待执行", icon: Clock, className: "task-todo" };
  }
}

function getRunId(run: RunSummary): string {
  return String(run.run_id || run.runId || run.id || "");
}

function formatTimestamp(value: unknown): string {
  if (!value) return "-";
  const ts = typeof value === "number" ? value : Date.parse(String(value));
  if (Number.isNaN(ts)) return "-";
  return new Date(ts).toLocaleString();
}

// ============================================================
// Component
// ============================================================

export default function PlanDetail() {
  const { planId } = useParams<{ planId: string }>();
  const navigate = useNavigate();
  
  const { t } = useI18n();
  const { workspace } = useWorkspace();
  const { canStartNewPlan, startExecution, setRunId } = useExecution();

  const [planData, setPlanData] = useState<PlanDetailResponse | null>(null);
  const [relatedRuns, setRelatedRuns] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  // 加载计划数据
  const loadPlan = useCallback(async () => {
    if (!planId) return;

    setLoading(true);
    setError(null);

    try {
      const data = await getPlan(planId);
      setPlanData(data);

      // 加载关联的 runs
      if (workspace) {
        const runs = await listRuns(workspace);
        const related = runs.filter(
          (r) => (r.plan_id || r.planId) === planId
        );
        setRelatedRuns(related);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [planId, workspace]);

  // 初始加载
  useEffect(() => {
    loadPlan();
  }, [loadPlan]);

  // 启动执行
  const handleStartRun = async () => {
    if (!planId) return;

    if (!canStartNewPlan) {
      setError("当前有任务在执行中，请等待完成或终止后再开始新任务");
      return;
    }

    setActionLoading(true);
    setError(null);

    try {
      startExecution(planId);
      const res = await startRun(planId);
      const runId = res.run_id || res.runId;

      if (!runId) {
        throw new Error("启动执行失败：未返回运行ID");
      }

      setRunId(runId);
      navigate(`/runs/${runId}?planId=${encodeURIComponent(planId)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "启动失败");
    } finally {
      setActionLoading(false);
    }
  };

  // 返工（重置所有任务状态为 todo 并重新执行）
  const handleRework = async () => {
    if (!planId) return;

    if (!canStartNewPlan) {
      setError("当前有任务在执行中，请等待完成或终止后再开始新任务");
      return;
    }

    if (!window.confirm("确定要返工吗？这将重置所有任务状态并重新开始执行。")) {
      return;
    }

    setActionLoading(true);
    setError(null);

    try {
      startExecution(planId);
      const res = await reworkPlan(planId);
      const runId = res.run_id || res.runId;

      if (!runId) {
        throw new Error("返工失败：未返回运行ID");
      }

      setRunId(runId);
      navigate(`/runs/${runId}?planId=${encodeURIComponent(planId)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "返工失败");
    } finally {
      setActionLoading(false);
    }
  };

  // 返回
  const handleBack = () => {
    navigate("/dashboard");
  };

  const handleDeletePlan = async () => {
    if (!planId) return;

    if (
      !window.confirm(
        "确定要删除此计划吗？这将同时删除所有关联的执行记录，此操作不可恢复。"
      )
    ) {
      return;
    }

    setActionLoading(true);
    setError(null);

    try {
      await deletePlan(planId);
      navigate("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除失败");
      setActionLoading(false);
    }
  };

  // 跳转到 run
  const handleRunClick = (run: RunSummary) => {
    const runId = getRunId(run);
    if (runId) {
      navigate(`/runs/${runId}?planId=${encodeURIComponent(planId || "")}`);
    }
  };

  // 解析数据
  const plan = planData?.plan;
  const snapshot = planData?.snapshot;
  const tasks: PlanTask[] = snapshot?.tasks || plan?.raw_plan?.tasks || [];
  const inputTask = plan?.input_task || plan?.inputTask || "";
  const taskChainText = planData?.task_chain_text || plan?.task_chain_text || "";

  // 统计
  const taskStats = {
    total: tasks.length,
    done: tasks.filter((t) => t.status?.toLowerCase() === "done").length,
    running: tasks.filter((t) => ["doing", "running"].includes(t.status?.toLowerCase() || "")).length,
    failed: tasks.filter((t) => t.status?.toLowerCase() === "failed").length,
  };

  if (loading) {
    return (
      <div className="plan-detail-page loading">
        <Loader2 size={24} className="spin" />
        <p>加载中...</p>
      </div>
    );
  }

  return (
    <div className="plan-detail-page">
      {/* 头部 */}
      <header className="plan-detail-header">
        <button type="button" className="plan-detail-back" onClick={handleBack}>
          <ArrowLeft size={20} />
          返回
        </button>
        <div className="plan-detail-title">
          <h1>计划详情</h1>
          <span className="plan-detail-id">Plan: {planId?.slice(0, 16)}...</span>
        </div>
        <button
          type="button"
          className="plan-detail-refresh"
          onClick={loadPlan}
        >
          <RefreshCw size={16} />
        </button>
      </header>

      {/* 错误提示 */}
      {error && (
        <div className="plan-detail-error">
          {error}
          <button onClick={() => setError(null)}>×</button>
        </div>
      )}

      {/* 任务描述 */}
      {inputTask && (
        <div className="plan-detail-task-card">
          <h3>
            <FileText size={18} />
            任务描述
          </h3>
          <p>{inputTask}</p>
        </div>
      )}

      {/* 操作按钮 */}
      <div className="plan-detail-actions">
        <button
          type="button"
          className="plan-action-btn primary"
          onClick={handleStartRun}
          disabled={actionLoading || !canStartNewPlan}
          title={!canStartNewPlan ? "当前有任务在执行中" : "启动新执行"}
        >
          <Play size={16} />
          {actionLoading ? "启动中..." : "启动执行"}
        </button>
        <button
          type="button"
          className="plan-action-btn secondary"
          onClick={handleRework}
          disabled={actionLoading || !canStartNewPlan}
          title="重置所有任务状态并重新执行"
        >
          <RotateCcw size={16} />
          返工
        </button>
        <button
          type="button"
          className="plan-action-btn danger"
          onClick={handleDeletePlan}
          disabled={actionLoading}
          title="删除此计划和所有关联的执行记录"
        >
          <Trash2 size={16} />
          删除计划
        </button>
      </div>

      {/* 任务统计 */}
      <div className="plan-detail-stats">
        <div className="plan-stat">
          <span className="plan-stat-value">{taskStats.total}</span>
          <span className="plan-stat-label">总任务</span>
        </div>
        <div className="plan-stat done">
          <span className="plan-stat-value">{taskStats.done}</span>
          <span className="plan-stat-label">已完成</span>
        </div>
        <div className="plan-stat running">
          <span className="plan-stat-value">{taskStats.running}</span>
          <span className="plan-stat-label">执行中</span>
        </div>
        <div className="plan-stat failed">
          <span className="plan-stat-value">{taskStats.failed}</span>
          <span className="plan-stat-label">失败</span>
        </div>
      </div>

      {/* 任务链 */}
      <section className="plan-detail-tasks">
        <h2>
          <List size={18} />
          任务链
        </h2>
        
        {tasks.length === 0 ? (
          <div className="plan-tasks-empty">暂无任务</div>
        ) : (
          <div className="plan-tasks-list">
            {tasks.map((task, index) => {
              const taskId = task.step_id || task.task_id || task.id || `task-${index}`;
              const title = task.title || task.name || task.description || `任务 ${index + 1}`;
              const statusInfo = getTaskStatus(task.status);
              const StatusIcon = statusInfo.icon;
              const deps = task.dependencies || [];

              return (
                <div key={taskId} className={`plan-task-item ${statusInfo.className}`}>
                  <div className="plan-task-index">{index + 1}</div>
                  <div className="plan-task-status">
                    <StatusIcon size={16} />
                  </div>
                  <div className="plan-task-content">
                    <div className="plan-task-title">{title}</div>
                    <div className="plan-task-meta">
                      <span className="plan-task-id">{taskId}</span>
                      {deps.length > 0 && (
                        <span className="plan-task-deps">
                          依赖: {deps.join(", ")}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className={`plan-task-badge ${statusInfo.className}`}>
                    {statusInfo.text}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* 任务链文本 */}
        {taskChainText && (
          <div className="plan-task-chain-text">
            <h4>任务链原文</h4>
            <pre>{taskChainText}</pre>
          </div>
        )}
      </section>

      {/* 关联的 Runs */}
      {relatedRuns.length > 0 && (
        <section className="plan-detail-runs">
          <h2>
            <Play size={18} />
            执行记录
          </h2>
          <div className="plan-runs-list">
            {relatedRuns.map((run) => {
              const runId = getRunId(run);
              const status = run.status || run.state || "unknown";
              const statusNorm = status.toLowerCase().replace(/-/g, "_");
              const updated = run.updated_at || run.updatedAt || run.ts;

              let StatusIcon = Clock;
              let statusClass = "status-unknown";
              let statusText = status;

              if (["completed", "done", "applied"].includes(statusNorm)) {
                StatusIcon = CheckCircle;
                statusClass = "status-completed";
                statusText = "已完成";
              } else if (["failed", "error"].includes(statusNorm)) {
                StatusIcon = XCircle;
                statusClass = "status-failed";
                statusText = "失败";
              } else if (["running", "executing", "doing"].includes(statusNorm)) {
                StatusIcon = Play;
                statusClass = "status-running";
                statusText = "执行中";
              } else if (statusNorm === "awaiting_review") {
                StatusIcon = AlertTriangle;
                statusClass = "status-review";
                statusText = "待审核";
              }

              return (
                <div
                  key={runId}
                  className="plan-run-item clickable"
                  onClick={() => handleRunClick(run)}
                >
                  <div className={`plan-run-status ${statusClass}`}>
                    <StatusIcon size={16} />
                  </div>
                  <div className="plan-run-content">
                    <div className="plan-run-id">Run: {runId.slice(0, 12)}...</div>
                    <div className="plan-run-time">{formatTimestamp(updated)}</div>
                  </div>
                  <div className={`plan-run-badge ${statusClass}`}>
                    {statusText}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}
