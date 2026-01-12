/**
 * Task Chain Progress 组件
 * 显示任务链进度
 */

import React, { useMemo } from "react";
import { useI18n } from "@/hooks/useI18n";
import type { PlanTask } from "@/apis/types";

interface TaskChainProgressProps {
  planId: string;
  tasks: PlanTask[];
  loading?: boolean;
  error?: string | null;
}

export function TaskChainProgress({
  planId,
  tasks,
  loading,
  error,
}: TaskChainProgressProps) {
  const { t } = useI18n();

  const stats = useMemo(() => {
    const total = tasks.length;
    const done = tasks.filter(
      (task) => String(task.status || "").toLowerCase() === "done"
    ).length;
    const doing = tasks.filter(
      (task) => String(task.status || "").toLowerCase() === "doing"
    ).length;
    const failed = tasks.filter(
      (task) => String(task.status || "").toLowerCase() === "failed"
    ).length;

    return {
      total,
      done,
      doing,
      failed,
      progress: total > 0 ? Math.round((done / total) * 100) : 0,
    };
  }, [tasks]);

  if (loading) {
    return (
      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">{t.titles.taskChainProgress}</h2>
        </div>
        <div className="page-muted">{t.messages.taskChainLoading}</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">{t.titles.taskChainProgress}</h2>
        </div>
        <div className="page-alert">{error}</div>
      </div>
    );
  }

  if (tasks.length === 0) {
    return (
      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">{t.titles.taskChainProgress}</h2>
        </div>
        <div className="page-muted">{t.messages.taskChainEmptyData}</div>
      </div>
    );
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <h2 className="panel-title">{t.titles.taskChainProgress}</h2>
      </div>

      {/* Progress Bar */}
      <div className="progress large">
        <div
          className="progress-bar"
          style={{ width: `${stats.progress}%` }}
        />
      </div>

      {/* Status Tags */}
      <div className="status-tags">
        <span className="status-pill">{stats.progress}%</span>
        <span className="status-pill subtle">
          {t.labels.tasksDone} {stats.done}/{stats.total}
        </span>
        {stats.doing > 0 && (
          <span className="status-pill warn">
            {t.labels.tasksDoing} {stats.doing}
          </span>
        )}
        {stats.failed > 0 && (
          <span className="status-pill error">
            {t.labels.tasksFailed} {stats.failed}
          </span>
        )}
      </div>

      {/* Task List */}
      <div className="card-list">
        {tasks.map((task, idx) => {
          const taskId =
            task.step_id || task.id || task.task_id || `task-${idx + 1}`;
          const title = task.title || task.name || `${t.labels.task} ${idx + 1}`;
          const status = String(task.status || "todo").toLowerCase();
          const statusLabel =
            t.status[status as keyof typeof t.status] || status;

          return (
            <div key={taskId} className="card-item">
              <div className="card-item-main">
                <div className="card-item-title">{title}</div>
                <div className="card-item-meta">
                  {t.labels.taskId} {taskId}
                </div>
                {task.description && (
                  <div className="card-item-meta">{task.description}</div>
                )}
              </div>
              <div className={`status-pill ${status}`}>{statusLabel}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
